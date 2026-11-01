"""Simulation runner: scenarios S1-S5, metrics, plots (design.md 15). S6 is not implemented.

    python -m d32.simulate --reps 1000 --out results
"""
from __future__ import annotations

import argparse
import functools
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from .config import BASE, SCENARIOS, Config, scenario_config
from .design import build_design
from .estimate import (CellSample, ListSample, design_weights, e0_estimate, e1_estimate, e2_estimate,
                       e3_estimate, kish_deff, kish_deff_factors)
from .select import phase2_subsample, prn_values, rep_streams, select_smallest
from .synth import District, eta_cv, lognormal_noise, make_district, response_probability
from .variance import bootstrap_e3, ci_t, lin_var_e1, lin_var_e2, lin_var_e3

EST = ["E0", "E1", "E2", "E3"]          # E3 interval = bootstrap (primary); E3lin = linearised cross-check


@functools.lru_cache(maxsize=1)
def _base_ctx():
    dist = make_district(BASE)
    design = build_design(dist.listed, BASE)
    u = dist.listed
    # design.md v0.2 section 9 step 1: exactly log area, assisted, distance (no blocks, no tank)
    Z = np.column_stack([np.ones(len(u)), np.log(u["area"].values / BASE.mean_area_ha),
                         u["assisted"].values.astype(float), u["dist_km"].values / 10.0])
    cell_g = dist.cell_water_rich.astype(int)          # 0 = other, 1 = water-rich
    nol = dist.units.iloc[dist.n_listed:]
    return dist, design, Z, cell_g, nol


@functools.lru_cache(maxsize=None)
def _scen_ctx(name: str):
    dist, design, Z, cell_g, nol = _base_ctx()
    cfg = scenario_config(name)
    y = dist.units["y"].values
    return {
        "cfg": cfg,
        "p_resp": response_probability(dist, cfg),
        "cv_diary": eta_cv(y, dist.calib_group, cfg.rho_diary),
        "cv_recall": eta_cv(y, dist.calib_group, cfg.rho_recall),
    }


def run_rep(args) -> list[dict]:
    rep, scen_names, do_boot = args
    dist, design, Z, cell_g, nol = _base_ctx()
    cfg0 = BASE
    key = f"{cfg0.master_seed}/{rep}"
    listed = dist.listed
    prn = prn_values(key, listed["unit_id"].values)
    sel = select_smallest(prn, design.unit_stratum, design.n_h)
    cprn = prn_values(key, dist.cell_ids)
    C_g = np.bincount(cell_g, minlength=2).astype(float)
    c_g = np.array([cfg0.cells_other, cfg0.cells_water_rich])
    csel = select_smallest(cprn, cell_g, c_g)
    n_sel = sel.size
    stratum = design.unit_stratum[sel]
    N_h = design.N_h.astype(float)
    n_act = np.bincount(stratum, minlength=N_h.size).astype(float)
    w0 = design_weights(stratum, N_h, n_act)
    ysel = listed["y"].values[sel]
    ass = listed["assisted"].values[sel]
    ev = listed["n_events"].values[sel]
    frame_area = float(listed["area"].sum())
    truth = dist.truth_total
    nol_y = nol["y"].values
    nol_cell = nol["cell"].values
    rows = []
    for name in scen_names:
        sc = _scen_ctx(name)
        cfg = sc["cfg"]
        s0, s1, s2, s3, s4, _ = rep_streams(cfg0.master_seed, rep)
        eta = lognormal_noise(s0.standard_normal(n_sel), sc["cv_diary"])
        xi = lognormal_noise(s0.standard_normal(n_sel), sc["cv_recall"])
        xi_nol = lognormal_noise(s0.standard_normal(nol_y.size), sc["cv_recall"])
        beta_d = np.where(ass == 1, cfg.beta_diary_assisted, cfg.beta_diary_plain)
        x_all = ysel * (1 + beta_d) * eta
        r_all = ysel * (1 + cfg.beta_recall) * xi
        resp = s1.random(n_sel) < sc["p_resp"][sel]
        ver = phase2_subsample(stratum, resp, N_h.size, cfg.phase2_rate, cfg.phase2_min, s2)
        y_obs = np.full(n_sel, np.nan)
        for i in np.where(ver)[0]:
            k = int(ev[i])
            share = s3.dirichlet(np.ones(k))
            b = s3.random(k) < cfg.verify_prob
            sv = float(np.sum(share * b))
            y_obs[i] = ysel[i] * sv + x_all[i] * (1 - sv)   # unverified events fall back to the diary
        x = np.where(resp, x_all, np.nan)
        ls = ListSample(stratum, N_h, w0, resp, ver, x, y_obs, r_all, Z[sel],
                        area=listed["area"].values[sel], A_h=design.strata["A_h"].values)
        r_nol = nol_y * (1 + cfg.beta_recall) * xi_nol
        cz = np.bincount(nol_cell, weights=r_nol, minlength=cfg0.n_cells)
        cn = np.bincount(nol_cell, minlength=cfg0.n_cells).astype(float)
        cs = CellSample(cell_g[csel], C_g, c_g.astype(float), cz[csel], cn[csel])

        row = {"scenario": name, "rep": rep, "truth": truth}
        row["E0_est"] = e0_estimate(frame_area, cfg.e0_norm_productivity)
        for k_ in ("se", "lo", "hi"):
            row[f"E0_{k_}"] = np.nan
        row["E1_est"] = e1_estimate(ls)
        V, df = lin_var_e1(ls)
        row["E1_se"], row["E1_lo"], row["E1_hi"] = ci_t(row["E1_est"], V, df, cfg.ci_level)
        e3 = e3_estimate(ls, w0, cs, cs.cw, cfg)
        row["E2_est"] = e2_estimate(ls, e3["w1"])
        V, df = lin_var_e2(ls)
        row["E2_se"], row["E2_lo"], row["E2_hi"] = ci_t(row["E2_est"], V, df, cfg.ci_level)
        lv = lin_var_e3(ls, e3, cs)
        row["E3_est"] = e3["Y"]
        _, row["E3lin_lo"], row["E3lin_hi"] = ci_t(e3["Y"], lv["V"], lv["df"], cfg.ci_level)
        row["E3lin_se"] = float(np.sqrt(max(lv["V"], 0.0)))
        if do_boot:
            bs = bootstrap_e3(ls, cs, cfg, s4)
            bse = float(np.nanstd(bs, ddof=1))
            row["E3_se"], row["E3_lo"], row["E3_hi"] = ci_t(e3["Y"], bse**2, lv["df"], cfg.ci_level)
            row["boot_nan"] = int(np.isnan(bs).sum())
        else:
            row.update(E3_se=np.nan, E3_lo=np.nan, E3_hi=np.nan, boot_nan=0)
        row.update(n_sel=n_sel, n_resp=int(resp.sum()), n_ver=int(ver.sum()),
                   deff_full=kish_deff(e3["w1"]),
                   deff_factors=kish_deff_factors(e3["phi"] * e3["g"], stratum, resp),
                   cal_failed=len(e3["cal_failed"]), g_min=float(e3["g"][resp].min()),
                   g_max=float(e3["g"][resp].max()), var_fallbacks=lv["var_fallbacks"],
                   V_L=lv["V_L"], V_NL=lv["V_NL"], R_hat=e3["R"], Rrec_hat=e3["Rrec"],
                   YNL_hat=e3["YNL"], undercov_hat=e3["nol_units"] / (e3["nol_units"] + N_h.sum()),
                   n_np_classes=int(np.unique(e3["classes"]).size))
        rows.append(row)
    return rows


def run(reps: int, scenarios: list[str], workers: int, do_boot: bool, boot_reps: int | None = None) -> pd.DataFrame:
    tasks = [(r, scenarios, do_boot and (boot_reps is None or r < boot_reps)) for r in range(reps)]
    if workers <= 1:
        res = [run_rep(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            res = list(ex.map(run_rep, tasks, chunksize=4))
    return pd.DataFrame([row for rr in res for row in rr])


def metrics(df: pd.DataFrame, level: float = 0.95) -> pd.DataFrame:
    out = []
    for scen, d in df.groupby("scenario", sort=True):
        T = d["truth"].iloc[0]
        for e in EST + ["E3lin"]:
            if e == "E3lin":
                est = d["E3_est"].values
            else:
                est = d[f"{e}_est"].values
            lo, hi, se = d[f"{e}_lo"].values, d[f"{e}_hi"].values, d[f"{e}_se"].values
            has_ci = not np.isnan(lo).all()
            ok = ~np.isnan(lo)
            cov = float(np.mean((lo[ok] <= T) & (T <= hi[ok]))) if has_ci else np.nan
            n = int(ok.sum())
            out.append({
                "scenario": scen, "estimator": e, "reps": len(d), "truth_t_simulated": T,
                "rel_bias": float(np.mean(est - T) / T),
                "rel_bias_mc_se": float(np.std(est, ddof=1) / np.sqrt(len(est)) / T) if len(est) > 1 else np.nan,
                "rmse_t": float(np.sqrt(np.mean((est - T) ** 2))),
                "rel_rmse": float(np.sqrt(np.mean((est - T) ** 2)) / T),
                "coverage": cov,
                "coverage_mc_se": float(np.sqrt(cov * (1 - cov) / n)) if has_ci and n else np.nan,
                "mean_ci_width_t": float(np.mean(hi[ok] - lo[ok])) if has_ci else np.nan,
                "rel_ci_width": float(np.mean(hi[ok] - lo[ok]) / T) if has_ci else np.nan,
                "rse_empirical": float(np.std(est, ddof=1) / T) if len(est) > 1 else np.nan,
                "rse_mean_estimated": float(np.nanmean(se) / np.mean(est)) if has_ci else np.nan,
            })
    m = pd.DataFrame(out)
    return m[~((m["estimator"] == "E3lin") & m["coverage"].isna())].reset_index(drop=True)


def ac4_ratio(df: pd.DataFrame, scen: str = "S1") -> dict:
    """AC4 (v0.2): mean bootstrap SE vs the empirical SD of E3; linearised SE reported beside it."""
    d = df[df.scenario == scen].dropna(subset=["E3_se"])
    if d.empty:
        return {"n": 0}
    emp = float(df[df.scenario == scen]["E3_est"].std(ddof=1))
    return {"n": int(len(d)), "empirical_sd_t": emp, "mean_boot_se_t": float(d["E3_se"].mean()),
            "mean_lin_se_t": float(d["E3lin_se"].mean()),
            "boot_over_empirical": float(d["E3_se"].mean() / emp),
            "lin_over_empirical": float(d["E3lin_se"].mean() / emp)}


def make_plots(df: pd.DataFrame, met: pd.DataFrame, out: Path, n_show: int = 100) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    scens = sorted(df.scenario.unique())
    fig, axes = plt.subplots(1, len(scens), figsize=(4.2 * len(scens), 6), sharey=False, squeeze=False)
    for ax, sc in zip(axes[0], scens):
        d = df[df.scenario == sc].head(n_show).reset_index(drop=True)
        T = d["truth"].iloc[0]
        cov = (d.E3_lo <= T) & (T <= d.E3_hi)
        for i, r in d.iterrows():
            ax.plot([r.E3_lo, r.E3_hi], [i, i], color="tab:green" if cov[i] else "tab:red", lw=1.2)
        ax.axvline(T, color="k", ls="--", lw=1)
        full = df[df.scenario == sc]
        c = ((full.E3_lo <= T) & (T <= full.E3_hi)).mean()
        ax.set_title(f"{sc}: E3 bootstrap 95% CI, first {len(d)} reps\ncoverage over all {len(full)} reps = {c:.1%} (SIMULATED)", fontsize=9)
        ax.set_xlabel("district production, t (SIMULATED)")
        ax.set_ylabel("replication")
    fig.suptitle("Coverage of E3 intervals: green covers the simulated truth, red misses (SIMULATED data)")
    fig.tight_layout()
    fig.savefig(out / "coverage_plot.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    width = 0.2
    cols = {"E0": "tab:gray", "E1": "tab:orange", "E2": "tab:blue", "E3": "tab:green"}
    for j, e in enumerate(EST):
        m = met[met.estimator == e].set_index("scenario").reindex(scens)
        ax.bar(np.arange(len(scens)) + (j - 1.5) * width, m["rel_bias"] * 100, width, yerr=1.96 * m["rel_bias_mc_se"] * 100,
               color=cols[e], label=e, capsize=2)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(np.arange(len(scens)))
    ax.set_xticklabels(scens)
    ax.set_ylabel("relative bias of district total, % (SIMULATED)")
    ax.set_title("Relative bias of E0-E3 by scenario (SIMULATED); bars show +-1.96 Monte Carlo SE")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "bias_plot.png", dpi=130)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=1000)
    ap.add_argument("--scenarios", default="S1,S2,S3,S4,S5")
    ap.add_argument("--out", default="results")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--no-boot", action="store_true")
    ap.add_argument("--boot-reps", type=int, default=None, help="bootstrap only the first k replications")
    ap.add_argument("--no-plots", action="store_true")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    scens = a.scenarios.split(",")
    df = run(a.reps, scens, a.workers, not a.no_boot, a.boot_reps)
    df.to_csv(out / "replications.csv", index=False)
    met = metrics(df)
    met.to_csv(out / "metrics.csv", index=False)
    (out / "config_used.json").write_text(BASE.to_json() + "\n", encoding="utf-8")
    if not a.no_plots:
        make_plots(df, met, out)
    print(met.to_string(float_format=lambda v: f"{v:.4f}"))
    print("AC4 (S1):", ac4_ratio(df))


if __name__ == "__main__":
    main()
