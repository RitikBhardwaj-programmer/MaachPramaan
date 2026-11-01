"""Linearised variance (design.md 8.6, 3.4) and Rao-Wu rescaled bootstrap (8.7)."""
from __future__ import annotations

import numpy as np
from scipy import stats

from .config import Config
from .estimate import CellSample, ListSample, e3_estimate


def _pooled_fill(s2: np.ndarray) -> tuple[np.ndarray, int]:
    """Strata with <2 units have no sample variance: use the mean of the others (counted)."""
    bad = np.isnan(s2)
    if bad.all():
        return np.zeros_like(s2), int(bad.sum())
    out = s2.copy()
    out[bad] = np.nanmean(s2)
    return out, int(bad.sum())


def _s2(v: np.ndarray) -> float:
    return float(np.var(v, ddof=1)) if v.size >= 2 else np.nan


def lin_var_e3(s: ListSample, est: dict, cells: CellSample) -> dict:
    """Closed-form variance of E3. Phase 1 + phase 2 terms of 8.6 on the verified units;
    R_rec and the area-frame term as in 3.4 / 8.4 (see REPORT.md for the simplifications)."""
    H = s.H
    R, Rrec, Hhat = est["R"], est["Rrec"], est["H"]
    w2 = est["w2"]
    n1 = np.array([(s.resp & (s.stratum == h)).sum() for h in range(H)], float)
    m = np.array([(s.ver & (s.stratum == h)).sum() for h in range(H)], float)
    s2y = np.full(H, np.nan)
    s2e = np.full(H, np.nan)
    s2u = np.full(H, np.nan)
    for h in range(H):
        v = s.ver & (s.stratum == h)
        if v.sum() >= 2:
            s2y[h] = _s2(s.y[v])
            s2e[h] = _s2(s.y[v] - R * s.x[v])
            s2u[h] = _s2(s.y[v] - Rrec * s.r[v])
    s2y, nfb = _pooled_fill(s2y)
    s2e, _ = _pooled_fill(s2e)
    s2u, _ = _pooled_fill(s2u)
    N = s.N_h.astype(float)
    ok = n1 > 0
    t1 = np.where(ok, N**2 * (1 / np.where(ok, n1, 1) - 1 / N) * s2y, 0.0)
    okm = m > 0
    t2 = np.where(okm, N**2 * (1 / np.where(okm, m, 1) - 1 / np.where(ok, n1, 1)) * s2e, 0.0)
    V_L = float(t1.sum() + t2.sum())

    wr = float(np.sum(w2[s.ver] * s.r[s.ver]))
    tu = np.where(okm, N**2 * (1 / np.where(okm, m, 1) - 1 / N) * s2u, 0.0)
    V_Rrec = float(tu.sum() / wr**2) if wr > 0 else np.nan

    V_H = 0.0
    for g in range(cells.C_g.size):
        k = cells.gstratum == g
        c = int(k.sum())
        if c >= 2:
            V_H += cells.C_g[g] ** 2 * (1 - c / cells.C_g[g]) * _s2(cells.z[k]) / c
    V_NL = float(Rrec**2 * V_H + Hhat**2 * V_Rrec)
    V = V_L + V_NL
    H_ver = int((m > 0).sum())
    df = float(m.sum() - H_ver)
    return {"V": V, "V_L": V_L, "V_NL": V_NL, "df": df, "var_fallbacks": nfb}


def ci_t(est: float, V: float, df: float, level: float) -> tuple[float, float, float]:
    se = float(np.sqrt(max(V, 0.0)))
    q = stats.t.ppf(0.5 + level / 2, df) if df > 0 else np.nan
    return se, est - q * se, est + q * se


def lin_var_e1(s: ListSample) -> tuple[float, float]:
    H = s.H
    n_h = np.bincount(s.stratum, minlength=H).astype(float)
    s2 = np.array([_s2(s.r[s.stratum == h]) for h in range(H)])
    s2, _ = _pooled_fill(s2)
    N = s.N_h.astype(float)
    V = float(np.sum(N**2 * (1 - n_h / N) * s2 / n_h))
    return V, float(n_h.sum() - H)


def lin_var_e2(s: ListSample) -> tuple[float, float]:
    H = s.H
    n1 = np.array([(s.resp & (s.stratum == h)).sum() for h in range(H)], float)
    s2 = np.array([_s2(s.x[s.resp & (s.stratum == h)]) for h in range(H)])
    s2, _ = _pooled_fill(s2)
    N = s.N_h.astype(float)
    ok = n1 > 0
    V = float(np.sum(np.where(ok, N**2 * (1 / np.where(ok, n1, 1) - 1 / N) * s2, 0.0)))
    return V, float(n1.sum() - H)


def rao_wu(base_w: np.ndarray, stratum: np.ndarray, N_h: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Rao-Wu rescaled bootstrap weights: per stratum draw m = n-1 units with replacement;
    w* = w (1 - lam + lam * n/m * t), lam = sqrt(m (1-f) / (n-1)), f = n / N."""
    w = base_w.copy()
    for h in range(N_h.size):
        idx = np.where(stratum == h)[0]
        n = idx.size
        if n < 2:
            continue
        m = n - 1
        f = min(n / N_h[h], 1.0)
        lam = np.sqrt(m * (1 - f) / (n - 1))
        t = rng.multinomial(m, np.full(n, 1.0 / n))
        w[idx] = base_w[idx] * (1 - lam + lam * (n / m) * t)
    return w


def bootstrap_e3(s: ListSample, cells: CellSample, cfg: Config, rng: np.random.Generator) -> np.ndarray:
    """B replicates of the whole E3 pipeline (propensity fit, classes, R, R_rec, Y_NL)."""
    out = np.full(cfg.n_boot, np.nan)
    cw0 = cells.cw
    for b in range(cfg.n_boot):
        w0 = rao_wu(s.w0, s.stratum, s.N_h, rng)
        cw = rao_wu(cw0, cells.gstratum, cells.C_g, rng)
        try:
            out[b] = e3_estimate(s, w0, cells, cw, cfg)["Y"]
        except np.linalg.LinAlgError:
            pass
    return out
