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

from dataclasses import replace

from .config import BASE, SCENARIOS, Config, scenario_config
from .design import build_design
from .estimate import (CellSample, ListSample, design_weights, e0_estimate, e1_estimate, e2_estimate,
                       e3_estimate, kish_deff, kish_deff_factors)
from .select import phase2_subsample, prn_values, rep_streams, select_smallest
from .synth import District, eta_cv, lognormal_noise, make_district, response_probability
from .fayherriot import fay_herriot
from .variance import (block_list_totals, bootstrap_e3, ci_t, lin_var_e1, lin_var_e2, lin_var_e3,
                       lin_var_p)

EST = ["E0", "E1", "E2", "E3"]          # E3 interval = bootstrap (primary); E3lin = linearised cross-check


def _cfg(ov: tuple) -> Config:
    """BASE with overrides (tuple of (field, value) pairs; hashable so the caches can key on it)."""
    return replace(BASE, **dict(ov))


@functools.lru_cache(maxsize=4)
def _base_ctx(ov: tuple = ()):
    BASE = _cfg(ov)
    dist = make_district(BASE)
    design = build_design(dist.listed, BASE)
    u = dist.listed
    # design.md v0.2 section 9 step 1: exactly log area, assisted, distance (no blocks, no tank)
    Z = np.column_stack([np.ones(len(u)), np.log(u["area"].values / BASE.mean_area_ha),
                         u["assisted"].values.astype(float), u["dist_km"].values / 10.0])
    cell_g = dist.cell_water_rich.astype(int)          # 0 = other, 1 = water-rich
    nol = dist.units.iloc[dist.n_listed:]
    return dist, design, Z, cell_g, nol


@functools.lru_cache(maxsize=4)
def _fh_ctx(ov: tuple = ()):
    """Block frame quantities for the Fay-Herriot test (design.md 21.4): frame water area A_b, covariates
    (intercept, log mean frame area, assisted share) and the list-frame truth theta_b = sum y / sum area."""
    cfg = _cfg(ov)
    u = _base_ctx(ov)[0].listed
    g = u.groupby("block")
    nb = cfg.n_blocks
    area_b = g["area"].sum().reindex(range(nb)).values
    X = np.column_stack([np.ones(nb), np.log(g["area"].mean().reindex(range(nb)).values),
                         g["assisted"].mean().reindex(range(nb)).values])
    theta = g["y"].sum().reindex(range(nb)).values / area_b
    return area_b, X, theta


@functools.lru_cache(maxsize=None)
def _scen_ctx(name: str, ov: tuple = ()):
    dist, design, Z, cell_g, nol = _base_ctx(ov)
    cfg = scenario_config(name, _cfg(ov))
    y = dist.units["y"].values
    return {
        "cfg": cfg,
        "p_resp": response_probability(dist, cfg),
        "cv_diary": eta_cv(y, dist.calib_group, cfg.rho_diary),
        "cv_recall": eta_cv(y, dist.calib_group, cfg.rho_recall),
    }


def run_rep(args) -> list[dict]:
    rep, scen_names, do_boot, ov = args
    dist, design, Z, cell_g, nol = _base_ctx(ov)
    cfg0 = _cfg(ov)
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
        sc = _scen_ctx(name, ov)
        cfg = sc["cfg"]
        s0, s1, s2, s3, s4, s5 = rep_streams(cfg0.master_seed, rep)
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
                        area=listed["area"].values[sel], A_h=design.strata["A_h"].values,
                        tiebreak=prn[sel], block=listed["block"].values[sel] if cfg.fayherriot else None)
        r_nol = nol_y * (1 + cfg.beta_recall) * xi_nol
        cz = np.bincount(nol_cell, weights=r_nol, minlength=cfg0.n_cells)
        cn = np.bincount(nol_cell, minlength=cfg0.n_cells).astype(float)
        cza = None
        if cfg.productivity:
            cza = np.bincount(nol_cell, weights=nol["area"].values, minlength=cfg0.n_cells)[csel]
        cs = CellSample(cell_g[csel], C_g, c_g.astype(float), cz[csel], cn[csel], cza)

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
        bp = None
        if do_boot:
            if cfg.takeall_phase2 or cfg.productivity or cfg.fayherriot:       # v0.4 paths; s5 is a stream apart from s4
                bp = bootstrap_e3(ls, cs, cfg, s4, s5, full=True)
                bs = bp["Y"]
            else:
                bs = bootstrap_e3(ls, cs, cfg, s4)
            bse = float(np.nanstd(bs, ddof=1))
            row["E3_se"], row["E3_lo"], row["E3_hi"] = ci_t(e3["Y"], bse**2, lv["df"], cfg.ci_level)
            row["boot_nan"] = int(np.isnan(bs).sum())
        else:
            row.update(E3_se=np.nan, E3_lo=np.nan, E3_hi=np.nan, boot_nan=0)
        row.update(n_sel=n_sel, n_resp=int(resp.sum()), n_ver=int(ver.sum()),
                   deff_full=kish_deff(e3["w1"]),
                   deff_factors=kish_deff_factors(e3["phi"] * e3["g"], stratum, resp),
                   cal_failed=len(e3["cal_failed"]), cal_fallback=len(e3["cal"]["fallback"]),
                   cal_unmet_after=len(e3["cal"]["unmet_after"]), cal_zero_resp=len(e3["cal"]["zero_resp"]),
                   cal_at_bound=int(e3["g"][resp].min() <= cfg.cal_g_lo + 1e-9
                                    or e3["g"][resp].max() >= cfg.cal_g_hi - 1e-9), g_min=float(e3["g"][resp].min()),
                   g_max=float(e3["g"][resp].max()), var_fallbacks=lv["var_fallbacks"],
                   V_L=lv["V_L"], V_NL=lv["V_NL"], R_hat=e3["R"], Rrec_hat=e3["Rrec"],
                   YNL_hat=e3["YNL"], undercov_hat=e3["nol_units"] / (e3["nol_units"] + N_h.sum()),
                   n_np_classes=int(np.unique(e3["classes"]).size))
        if cfg.takeall_phase2:
            row["ta_phase2_skipped"] = len(bp["ta_skipped"]) if bp is not None else 0
        if cfg.productivity:
            P_truth = truth / float(dist.units["area"].sum())
            row.update(P_truth=P_truth, A_hat=e3["A"], P_est=e3["P"])
            vP = lin_var_p(ls, e3, cs, lv["V"])
            row["Plin_se"], row["Plin_lo"], row["Plin_hi"] = ci_t(e3["P"], vP, lv["df"], cfg.ci_level)
            if bp is not None:
                pse = float(np.nanstd(bp["P"], ddof=1))
                row["P_se"], row["P_lo"], row["P_hi"] = ci_t(e3["P"], pse**2, lv["df"], cfg.ci_level)
            else:
                row.update(P_se=np.nan, P_lo=np.nan, P_hi=np.nan)
        if cfg.fayherriot:
            fh = _fh_rows(ls, e3, bp, name, rep, ov, cfg)
            row.update(fh["row"])
            row["_fh"] = fh["blocks"]
        rows.append(row)
    return rows


def _fh_rows(ls, e3, bp, name, rep, ov, cfg) -> dict:
    """Direct block estimates, bootstrap variances, FH + benchmarking for one replication (design.md 21.4)."""
    area_b, X, theta_true = _fh_ctx(ov)
    nb = cfg.n_blocks
    n_b = np.bincount(ls.block[ls.resp], minlength=nb)
    Yb = block_list_totals(ls, e3, nb)
    direct = np.where(n_b > 0, Yb / area_b, np.nan)
    psi_raw = np.nanvar(bp["Yb"], axis=0, ddof=1) / area_b**2
    r = fay_herriot(direct, psi_raw, n_b, X, area_b, e3["YL"])
    half = 1.96 * np.sqrt(r["mse"])
    scale = np.where(r["fh"] != 0, r["fh_bm"] / r["fh"], 1.0)
    dhalf = 1.96 * np.sqrt(psi_raw)
    blocks = [dict(scenario=name, rep=rep, block=b, truth=theta_true[b], n_resp=int(n_b[b]), valid=bool(r["valid"][b]),
                   direct=direct[b], direct_lo=direct[b] - dhalf[b], direct_hi=direct[b] + dhalf[b],
                   psi_raw=psi_raw[b], psi_gvf=r["psi_gvf"][b], gamma=r["gamma"][b], fh=r["fh"][b],
                   fh_lo=r["fh"][b] - half[b], fh_hi=r["fh"][b] + half[b], fh_bm=r["fh_bm"][b],
                   fh_bm_lo=r["fh_bm"][b] - half[b] * scale[b], fh_bm_hi=r["fh_bm"][b] + half[b] * scale[b],
                   mse_pr=r["mse"][b]) for b in range(nb)]
    bench_err = abs(float(np.sum(r["fh_bm"] * area_b)) - e3["YL"]) / abs(e3["YL"])
    return {"blocks": blocks, "row": {"fh_sigma_v2": r["sigma_v2"], "fh_sigma_v2_unadj": r["sigma_v2_unadj"],
                                      "fh_bench_err": bench_err, "fh_blocks_valid": int(r["valid"].sum())}}


def run(reps: int, scenarios: list[str], workers: int, do_boot: bool, boot_reps: int | None = None,
        overrides: dict | None = None) -> pd.DataFrame:
    ov = tuple(sorted((overrides or {}).items()))
    tasks = [(r, scenarios, do_boot and (boot_reps is None or r < boot_reps), ov) for r in range(reps)]
    if workers <= 1:
        res = [run_rep(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            res = list(ex.map(run_rep, tasks, chunksize=4))
    fh = [b for rr in res for row in rr for b in row.get("_fh", [])]
    df = pd.DataFrame([{k: v for k, v in row.items() if k != "_fh"} for rr in res for row in rr])
    if fh:
        df.attrs["fh_blocks"] = pd.DataFrame(fh)
    return df


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
    if "P_est" in df.columns:        # v0.4 productivity rows; truth_t_simulated and *_t columns are in t/ha
        for scen, d in df.groupby("scenario", sort=True):
            T = d["P_truth"].iloc[0]
            for e in ("P", "Plin"):
                est = d["P_est"].values
                lo, hi, se = d[f"{e}_lo"].values, d[f"{e}_hi"].values, d[f"{e}_se"].values
                ok = ~np.isnan(lo)
                if not ok.any():
                    continue
                cov = float(np.mean((lo[ok] <= T) & (T <= hi[ok])))
                out.append({
                    "scenario": scen, "estimator": e, "reps": len(d), "truth_t_simulated": T,
                    "rel_bias": float(np.mean(est - T) / T),
                    "rel_bias_mc_se": float(np.std(est, ddof=1) / np.sqrt(len(est)) / T),
                    "rmse_t": float(np.sqrt(np.mean((est - T) ** 2))),
                    "rel_rmse": float(np.sqrt(np.mean((est - T) ** 2)) / T),
                    "coverage": cov, "coverage_mc_se": float(np.sqrt(cov * (1 - cov) / ok.sum())),
                    "mean_ci_width_t": float(np.mean(hi[ok] - lo[ok])),
                    "rel_ci_width": float(np.mean(hi[ok] - lo[ok]) / T),
                    "rse_empirical": float(np.std(est, ddof=1) / T),
                    "rse_mean_estimated": float(np.nanmean(se) / np.mean(est)),
                })
    m = pd.DataFrame(out)
    return m[~((m["estimator"] == "E3lin") & m["coverage"].isna())].reset_index(drop=True)


def fh_metrics(b: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """Design.md 21.4 criteria from the per-block table: F1/F5 mean over blocks of MSE(FH)/MSE(direct), F2 mean
    coverage of the Prasad-Rao interval, F4 share of replications with unadjusted REML sigma_v^2 = 0, F3 max
    benchmark error. Blocks without a direct estimate in a replication are left out of that replication."""
    b = b[b.valid]
    rows = []
    for scen, d in b.groupby("scenario", sort=True):
        per = pd.DataFrame({"block": sorted(d.block.unique())}).set_index("block")
        for blk, x in d.groupby("block"):
            per.loc[blk, "mse_direct"] = np.mean((x.direct - x.truth) ** 2)
            per.loc[blk, "mse_fh"] = np.mean((x.fh - x.truth) ** 2)
            per.loc[blk, "mse_fh_bm"] = np.mean((x.fh_bm - x.truth) ** 2)
            per.loc[blk, "cov_direct"] = np.mean((x.direct_lo <= x.truth) & (x.truth <= x.direct_hi))
            per.loc[blk, "cov_fh"] = np.mean((x.fh_lo <= x.truth) & (x.truth <= x.fh_hi))
            per.loc[blk, "cov_fh_bm"] = np.mean((x.fh_bm_lo <= x.truth) & (x.truth <= x.fh_bm_hi))
            per.loc[blk, "gamma_mean"] = x.gamma.mean()
            per.loc[blk, "n_resp_mean"] = x.n_resp.mean()
        per["ratio_fh"] = per.mse_fh / per.mse_direct
        per["ratio_fh_bm"] = per.mse_fh_bm / per.mse_direct
        per.insert(0, "scenario", scen)
        rows.append(per.reset_index())
    out = pd.concat(rows, ignore_index=True)
    summ = []
    for scen, d in out.groupby("scenario"):
        r = df[df.scenario == scen]
        summ.append({"scenario": scen, "block": "ALL", "reps": len(r),
                     "F1_ratio_fh_bm": d.ratio_fh_bm.mean(), "ratio_fh_unbenchmarked": d.ratio_fh.mean(),
                     "F2_cov_fh_bm": d.cov_fh_bm.mean(), "cov_fh": d.cov_fh.mean(), "cov_direct": d.cov_direct.mean(),
                     "F3_max_bench_err": r.fh_bench_err.max(),
                     "F4_share_unadj_reml_zero": float((r.fh_sigma_v2_unadj == 0).mean()),
                     "sigma_v2_mean": r.fh_sigma_v2.mean(), "gamma_mean": d.gamma_mean.mean()})
    return pd.concat([out.astype({"block": object}), pd.DataFrame(summ)], ignore_index=True)


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
    ap.add_argument("--pop-seed", type=int, default=None, help="override Config.pop_seed")
    ap.add_argument("--master-seed", type=int, default=None, help="override Config.master_seed")
    ap.add_argument("--cal-rule", choices=["v0.2", "v0.3"], default="v0.3",
                    help="v0.2 = threshold 4, no N_h-only fallback (design.md section 19)")
    ap.add_argument("--takeall-phase2", action="store_true", help="v0.4 (21.1): phase-2 resampling in take-all strata")
    ap.add_argument("--productivity", action="store_true", help="v0.4 (21.2): estimate P = Y/A")
    ap.add_argument("--fh", action="store_true", help="v0.4 (21.4): Fay-Herriot block estimates (needs bootstrap)")
    ap.add_argument("--sigma-b", type=float, default=None, help="block effect sd on productivity (Config.sigma_b)")
    ap.add_argument("--n-blocks", type=int, default=None, help="blocks per district (Config.n_blocks)")
    ap.add_argument("--v04", action="store_true", help="shorthand for --takeall-phase2 --productivity")
    a = ap.parse_args(argv)
    overrides = {}
    if a.takeall_phase2 or a.v04:
        overrides["takeall_phase2"] = True
    if a.fh:
        overrides["fayherriot"] = True
    if a.sigma_b is not None:
        overrides["sigma_b"] = a.sigma_b
    if a.n_blocks is not None:
        overrides["n_blocks"] = a.n_blocks
    if a.productivity or a.v04:
        overrides["productivity"] = True
    if a.pop_seed is not None:
        overrides["pop_seed"] = a.pop_seed
    if a.master_seed is not None:
        overrides["master_seed"] = a.master_seed
    if a.cal_rule == "v0.2":
        overrides.update(cal_min_resp=4, cal_fallback=False)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    scens = a.scenarios.split(",")
    df = run(a.reps, scens, a.workers, not a.no_boot, a.boot_reps, overrides)
    df.to_csv(out / "replications.csv", index=False)
    met = metrics(df)
    met.to_csv(out / "metrics.csv", index=False)
    if "fh_blocks" in df.attrs:
        df.attrs["fh_blocks"].to_csv(out / "fh_blocks.csv", index=False)
        fhm = fh_metrics(df.attrs["fh_blocks"], df)
        fhm.to_csv(out / "fh_metrics.csv", index=False)
        print(fhm[fhm.block == "ALL"].to_string())
    (out / "config_used.json").write_text(_cfg(tuple(sorted(overrides.items()))).to_json() + "\n", encoding="utf-8")
    if not a.no_plots:
        make_plots(df, met, out)
    print(met.to_string(float_format=lambda v: f"{v:.4f}"))
    print("AC4 (S1):", ac4_ratio(df))


if __name__ == "__main__":
    main()
