"""Rotating panel and composite estimator, scenario S6 (design.md 12, 21.5). All values are SIMULATED.

    python -m d32.panel --reps 30 --pop-seed 1 --master-seed 1 --out results/tmp

Three years, one fixed frame. Productivity persists (rho_u) with a district trend. The sample rotates by
a PRN shift. Year t >= 2: composite = (1-K) direct_t + K (composite_{t-1} + matched change).
"""
from __future__ import annotations

import argparse
import functools
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from .config import BASE, Config, scenario_config
from .estimate import CellSample, ListSample, design_weights, e3_estimate
from .select import phase2_subsample, prn_values, rep_streams, select_smallest
from .simulate import _base_ctx, _cfg
from .synth import eta_cv, lognormal_noise, response_probability

YEARS = 3


# ---- population over years ---------------------------------------------------------------------
def year_production(dist, cfg: Config) -> np.ndarray:
    """(YEARS, n_units) true production y_it in tonnes.
    prod_it = base_i exp(s (sqrt(rho) z_i + sqrt(1-rho) eps_it) - s^2/2) (1+trend)^(t-1); z_i = z_prod."""
    u = dist.units
    s, rho = cfg.prod_noise_sigma, cfg.rho_u
    z = u["z_prod"].values
    base = u["prod"].values / np.exp(s * z - s**2 / 2)
    eps = np.random.default_rng(np.random.SeedSequence(cfg.pop_seed).spawn(4)[3]).standard_normal((YEARS, len(u)))
    prod = base * np.exp(s * (np.sqrt(rho) * z + np.sqrt(1 - rho) * eps) - s**2 / 2)
    prod = prod * (1 + cfg.trend) ** np.arange(YEARS)[:, None]
    return u["area"].values * prod


@functools.lru_cache(maxsize=2)
def _panel_ctx(ov: tuple):
    dist, design, Z, cell_g, nol = _base_ctx(ov)
    cfg = scenario_config("S1", _cfg(ov))
    y = year_production(dist, cfg)
    return {"cfg": cfg, "y": y, "p_resp": response_probability(dist, cfg),
            "cv_diary": eta_cv(y[0], dist.calib_group, cfg.rho_diary),
            "cv_recall": eta_cv(y[0], dist.calib_group, cfg.rho_recall)}


# ---- rotation ------------------------------------------------------------------------------------
def shifted_prn(prn: np.ndarray, stratum: np.ndarray, N_h, n_h, t: int) -> np.ndarray:
    """u^(t) = (u + t delta_h) mod 1, delta_h = n_h / (3 N_h) (design.md 12); t = 0 is year 1."""
    delta = (np.asarray(n_h, float) / (3.0 * np.asarray(N_h, float)))[stratum]
    return np.mod(prn + t * delta, 1.0)


# ---- bootstrap multiplicities shared by units that stay in the sample ------------------------------
def draw_counts(sel, prev_sel, prev_cnt, stratum, H, rng, size) -> np.ndarray:
    """Rao-Wu multiplicities t_i (n-1 draws per stratum) for the units in `sel`. Units also in
    `prev_sel` keep their previous count; the remaining n-1-K draws go to the new units uniformly. This
    keeps every year's counts an exact multinomial and gives the same unit the same count in both years."""
    cnt = np.zeros(size)
    in_prev = np.zeros(size, bool) if prev_sel is None else np.isin(np.arange(size), prev_sel)
    for h in range(H):
        idx = sel[stratum[sel] == h]
        n = idx.size
        if n < 2:
            cnt[idx] = 1.0
            continue
        old, new = idx[in_prev[idx]], idx[~in_prev[idx]]
        cnt[old] = prev_cnt[old] if prev_cnt is not None else 0.0
        k = int(cnt[old].sum())
        if new.size:
            cnt[new] = rng.multinomial(n - 1 - k, np.full(new.size, 1.0 / new.size))
        elif prev_sel is None:
            cnt[idx] = rng.multinomial(n - 1, np.full(n, 1.0 / n))
    return cnt


def rw_factor(counts, stratum_sel, N_h) -> np.ndarray:
    """Rao-Wu weight factor 1 - lam + lam n/(n-1) t_i, lam = sqrt(1 - n/N_h) (design.md 8.7)."""
    a = np.ones(stratum_sel.size)
    for h in range(N_h.size):
        m = stratum_sel == h
        n = int(m.sum())
        if n < 2:
            continue
        lam = np.sqrt(max(1.0 - n / N_h[h], 0.0))
        a[m] = 1 - lam + lam * (n / (n - 1)) * counts[m]
    return a


# ---- composite estimator -----------------------------------------------------------------------------
def estimate_K(a: np.ndarray, b: np.ndarray, kmax: float) -> float:
    """Variance-minimising weight on b in (1-K) a + K b: K = (V(a) - Cov(a, b)) / V(a - b), clipped [0, kmax]."""
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if a.size < 3:
        return 0.0
    v = np.var(a - b, ddof=1)
    if not v > 0:
        return 0.0
    k = (np.var(a, ddof=1) - np.cov(a, b, ddof=1)[0, 1]) / v
    return float(min(max(k, 0.0), kmax))


def composite_chain(Y, D, K) -> np.ndarray:
    """Y (..., 3) direct totals, D (..., 2) matched changes (years 2, 3), K two weights.
    Returns (..., 3): year 1 = direct; year t = (1-K_t) Y_t + K_t (composite_{t-1} + D_t)."""
    Y, D = np.asarray(Y, float), np.asarray(D, float)
    out = [Y[..., 0]]
    for t in (1, 2):
        out.append((1 - K[t - 1]) * Y[..., t] + K[t - 1] * (out[-1] + D[..., t - 1]))
    return np.stack(out, axis=-1)


def estimate_K_chain(Yrep, Drep, kmax: float) -> list[float]:
    """K_2, K_3 from bootstrap replicates, year by year (year 3 uses the year-2 composite replicates)."""
    K = []
    comp_prev = Yrep[:, 0]
    for t in (1, 2):
        b = comp_prev + Drep[:, t - 1]
        K.append(estimate_K(Yrep[:, t], b, kmax))
        comp_prev = (1 - K[-1]) * Yrep[:, t] + K[-1] * b
    return K


# ---- one replication ---------------------------------------------------------------------------------
def _subset(ls: ListSample, pos: np.ndarray, N_h) -> ListSample:
    st = ls.stratum[pos]
    m_h = np.bincount(st, minlength=N_h.size).astype(float)
    w0 = (N_h / np.maximum(m_h, 1.0))[st]
    return ListSample(st, N_h, w0, ls.resp[pos], ls.ver[pos], ls.x[pos], ls.y[pos], ls.r[pos], ls.Z[pos],
                      ls.area[pos], ls.A_h, ls.tiebreak[pos])


def _estimates(ls, cs, pairs, factors, cfw, cfg) -> tuple[np.ndarray, np.ndarray]:
    """Direct totals (3,) and matched changes (2,) for the given weight factors (ones = point estimate)."""
    Y = np.array([e3_estimate(ls[t], ls[t].w0 * factors[t], cs[t], cs[t].cw * cfw, cfg)["Y"] for t in range(YEARS)])
    D = np.empty(2)
    for t in (1, 2):
        pp, pc = pairs[t]
        est = []
        for yr, pos in ((t - 1, pp), (t, pc)):
            sub = _subset(ls[yr], pos, ls[yr].N_h)
            est.append(e3_estimate(sub, sub.w0 * factors[yr][pos], cs[yr], cs[yr].cw * cfw, cfg)["Y"])
        D[t - 1] = est[1] - est[0]
    return Y, D


def run_rep(args) -> list[dict]:
    rep, ov, do_boot = args
    dist, design, Z, cell_g, nol = _base_ctx(ov)
    pc = _panel_ctx(ov)
    cfg, cfg0 = pc["cfg"], _cfg(ov)
    listed = dist.listed
    N_h = design.N_h.astype(float)
    H = N_h.size
    key = f"{cfg0.master_seed}/{rep}"
    prn = prn_values(key, listed["unit_id"].values)
    sels = [select_smallest(shifted_prn(prn, design.unit_stratum, design.N_h, design.n_h, t), design.unit_stratum, design.n_h)
            for t in range(YEARS)]
    horizon = [select_smallest(shifted_prn(prn, design.unit_stratum, design.N_h, design.n_h, t), design.unit_stratum, design.n_h)
               for t in range(6)]
    seen = np.zeros(len(listed), int)
    run_len = np.zeros(len(listed), int)
    max_run = np.zeros(len(listed), int)
    for s_ in horizon:
        inn = np.zeros(len(listed), bool)
        inn[s_] = True
        seen[s_] += 1
        run_len = np.where(inn, run_len + 1, 0)
        max_run = np.maximum(max_run, run_len)
    take_all = design.unit_stratum >= 0
    take_all &= np.isin(design.unit_stratum, np.where(design.strata["take_all"].values)[0])
    max_years = int(max_run[~take_all].max())
    max_total = int(seen[~take_all].max())
    n_over3 = int((max_run[~take_all] > 3).sum())
    n_ever = int((seen[~take_all] > 0).sum())
    cprn = prn_values(key, dist.cell_ids)
    C_g = np.bincount(cell_g, minlength=2).astype(float)
    c_g = np.array([cfg0.cells_other, cfg0.cells_water_rich])
    csel = select_smallest(cprn, cell_g, c_g)
    nol_cell = nol["cell"].values
    ls, cs, truth = [], [], []
    for t in range(YEARS):
        s0, s1, s2, s3, _, _ = rep_streams(cfg0.master_seed, rep * 4 + t + 1)
        sel = sels[t]
        yall = pc["y"][t]
        ysel, nol_y = yall[: len(listed)][sel], yall[len(listed):]
        stratum = design.unit_stratum[sel]
        n_act = np.bincount(stratum, minlength=H).astype(float)
        w0 = design_weights(stratum, N_h, n_act)
        ev = listed["n_events"].values[sel]
        n = sel.size
        eta = lognormal_noise(s0.standard_normal(n), pc["cv_diary"])
        xi = lognormal_noise(s0.standard_normal(n), pc["cv_recall"])
        xi_nol = lognormal_noise(s0.standard_normal(nol_y.size), pc["cv_recall"])
        beta_d = np.where(listed["assisted"].values[sel] == 1, cfg.beta_diary_assisted, cfg.beta_diary_plain)
        x_all = ysel * (1 + beta_d) * eta
        r_all = ysel * (1 + cfg.beta_recall) * xi
        resp = s1.random(n) < pc["p_resp"][sel]
        ver = phase2_subsample(stratum, resp, H, cfg.phase2_rate, cfg.phase2_min, s2)
        y_obs = np.full(n, np.nan)
        for i in np.where(ver)[0]:
            k = int(ev[i])
            share = s3.dirichlet(np.ones(k))
            sv = float(np.sum(share * (s3.random(k) < cfg.verify_prob)))
            y_obs[i] = ysel[i] * sv + x_all[i] * (1 - sv)
        ls.append(ListSample(stratum, N_h, w0, resp, ver, np.where(resp, x_all, np.nan), y_obs, r_all, Z[sel],
                             area=listed["area"].values[sel], A_h=design.strata["A_h"].values, tiebreak=prn[sel]))
        r_nol = nol_y * (1 + cfg.beta_recall) * xi_nol
        cz = np.bincount(nol_cell, weights=r_nol, minlength=cfg0.n_cells)
        cn = np.bincount(nol_cell, minlength=cfg0.n_cells).astype(float)
        cs.append(CellSample(cell_g[csel], C_g, c_g.astype(float), cz[csel], cn[csel]))
        truth.append(float(yall.sum()))
    pairs = {}
    shares = [np.nan]
    for t in (1, 2):
        common = np.intersect1d(sels[t - 1], sels[t])
        pairs[t] = (np.searchsorted(sels[t - 1], common), np.searchsorted(sels[t], common))
        shares.append(common.size / sels[t].size)
    ones = [np.ones(sels[t].size) for t in range(YEARS)]
    Y0, D0 = _estimates(ls, cs, pairs, ones, 1.0, cfg)
    if do_boot:
        rng = rep_streams(cfg0.master_seed, rep * 4)[4]
        Yb = np.full((cfg.n_boot, YEARS), np.nan)
        Db = np.full((cfg.n_boot, 2), np.nan)
        from .variance import rao_wu
        for b in range(cfg.n_boot):
            cnt, prev, prev_cnt, fac = None, None, None, []
            for t in range(YEARS):
                cnt = draw_counts(sels[t], prev, prev_cnt, design.unit_stratum, H, rng, len(listed))
                fac.append(rw_factor(cnt[sels[t]], design.unit_stratum[sels[t]], N_h))
                prev, prev_cnt = sels[t], cnt
            cfw = rao_wu(np.ones(csel.size), cs[0].gstratum, cs[0].C_g, rng)
            try:
                Yb[b], Db[b] = _estimates(ls, cs, pairs, fac, cfw, cfg)
            except np.linalg.LinAlgError:
                pass
        good = np.isfinite(Yb).all(1) & np.isfinite(Db).all(1)
        K = estimate_K_chain(Yb[good], Db[good], cfg.k_max)
        Cb = composite_chain(Yb[good], Db[good], K)
        dse, cse = Yb[good].std(0, ddof=1), Cb.std(0, ddof=1)
    else:
        K, Cb, dse, cse = [0.0, 0.0], None, np.full(YEARS, np.nan), np.full(YEARS, np.nan)
    C0 = composite_chain(Y0, D0, K)
    rows = []
    for t in range(YEARS):
        v = ls[t].ver
        df_t = float(v.sum() - np.unique(ls[t].stratum[v]).size)
        q = stats.t.ppf(0.975, df_t) if df_t > 0 else np.nan
        rows.append({"year": t + 1, "rep": rep, "rho_u": cfg.rho_u, "truth": truth[t], "direct": Y0[t],
                     "direct_se": dse[t], "direct_lo": Y0[t] - q * dse[t], "direct_hi": Y0[t] + q * dse[t],
                     "composite": C0[t], "composite_se": cse[t], "composite_lo": C0[t] - q * cse[t],
                     "composite_hi": C0[t] + q * cse[t], "K": 0.0 if t == 0 else K[t - 1],
                     "delta": np.nan if t == 0 else D0[t - 1], "matched_share": shares[t],
                     "max_consecutive_years_6y": max_years, "max_total_years_6y": max_total,
                     "units_over3_consecutive": n_over3, "units_sampled_6y": n_ever, "n_sel": sels[t].size, "n_resp": int(ls[t].resp.sum()),
                     "n_ver": int(v.sum())})
    return rows


def run(reps: int, workers: int = 1, do_boot: bool = True, overrides: dict | None = None) -> pd.DataFrame:
    ov = tuple(sorted((overrides or {}).items()))
    tasks = [(r, ov, do_boot) for r in range(reps)]
    if workers <= 1:
        res = [run_rep(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            res = list(ex.map(run_rep, tasks, chunksize=2))
    return pd.DataFrame([r for rr in res for r in rr])


def metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Per year: relative bias, RMSE and coverage of direct and composite, RMSE ratio, mean K, matched share."""
    out = []
    for yr, d in df.groupby("year"):
        T = d["truth"].values
        row = {"year": yr, "rho_u": d["rho_u"].iloc[0], "reps": len(d)}
        for name in ("direct", "composite"):
            e = d[name].values
            row[f"{name}_rel_bias"] = float(np.mean(e - T) / np.mean(T))
            row[f"{name}_rel_bias_mc_se"] = float(np.std(e - T, ddof=1) / np.sqrt(len(e)) / np.mean(T))
            row[f"{name}_rmse_t"] = float(np.sqrt(np.mean((e - T) ** 2)))
            ok = d[f"{name}_se"].notna()
            cov = ((d[f"{name}_lo"] <= T) & (T <= d[f"{name}_hi"]))[ok].mean() if ok.any() else np.nan
            row[f"{name}_coverage"] = float(cov)
            row[f"{name}_coverage_mc_se"] = float(np.sqrt(cov * (1 - cov) / ok.sum())) if ok.any() else np.nan
        row["rmse_ratio"] = row["composite_rmse_t"] / row["direct_rmse_t"]
        row["K_mean"] = float(d["K"].mean())
        row["matched_share_mean"] = float(d["matched_share"].mean()) if yr > 1 else np.nan
        row["matched_share_min"] = float(d["matched_share"].min()) if yr > 1 else np.nan
        row["matched_share_max"] = float(d["matched_share"].max()) if yr > 1 else np.nan
        row["max_consecutive_years_6y"] = int(d["max_consecutive_years_6y"].max())
        row["max_total_years_6y"] = int(d["max_total_years_6y"].max())
        row["share_units_over3_years"] = float(d["units_over3_consecutive"].sum() / d["units_sampled_6y"].sum())
        out.append(row)
    return pd.DataFrame(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=1000)
    ap.add_argument("--out", default="results/s6")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--no-boot", action="store_true")
    ap.add_argument("--pop-seed", type=int, default=None)
    ap.add_argument("--master-seed", type=int, default=None)
    ap.add_argument("--rho-u", type=float, default=None)
    a = ap.parse_args(argv)
    ov = {k: v for k, v in (("pop_seed", a.pop_seed), ("master_seed", a.master_seed), ("rho_u", a.rho_u)) if v is not None}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    df = run(a.reps, a.workers, not a.no_boot, ov)
    df.to_csv(out / "replications.csv", index=False)
    met = metrics(df)
    met.to_csv(out / "metrics.csv", index=False)
    (out / "config_used.json").write_text(_cfg(tuple(sorted(ov.items()))).to_json() + "\n", encoding="utf-8")
    print(met.T.to_string())


if __name__ == "__main__":
    main()
