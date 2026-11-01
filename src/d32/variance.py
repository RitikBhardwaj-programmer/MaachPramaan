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


def takeall_strata(s: ListSample) -> tuple[list[int], list[int]]:
    """Take-all strata (f_h = 1: every frame unit selected) split into (usable, skipped).
    Usable: m_h >= 2 verified and m_h < n'_h respondents. Skipped: m_h < 2 (design.md 21.1, recorded).
    Strata with m_h = n'_h need no draw: lambda = 0, the added term is zero."""
    n_h = np.bincount(s.stratum, minlength=s.H)
    use, skipped = [], []
    for h in range(s.H):
        if n_h[h] == 0 or n_h[h] < s.N_h[h]:
            continue
        m = int((s.ver & (s.stratum == h)).sum())
        n1 = int((s.resp & (s.stratum == h)).sum())
        if m < 2:
            skipped.append(h)
        elif m < n1:
            use.append(h)
    return use, skipped


def takeall_phase2_mult(s: ListSample, strata: list[int], rng: np.random.Generator) -> np.ndarray:
    """Rao-Wu multiplier on the phase-2 weights of verified units in take-all strata (design.md 21.1):
    draw m_h - 1 of the m_h verified units with replacement, lambda = sqrt(1 - m_h / n'_h),
    mult = 1 - lambda + lambda * m_h / (m_h - 1) * t_i. Everything else keeps multiplier 1."""
    mult = np.ones(s.stratum.size)
    for h in strata:
        idx = np.where(s.ver & (s.stratum == h))[0]
        m = idx.size
        n1 = int((s.resp & (s.stratum == h)).sum())
        lam = np.sqrt(1.0 - m / n1)
        t = rng.multinomial(m - 1, np.full(m, 1.0 / m))
        mult[idx] = 1 - lam + lam * (m / (m - 1)) * t
    return mult


def bootstrap_e3(s: ListSample, cells: CellSample, cfg: Config, rng: np.random.Generator,
                 rng_ph2: np.random.Generator | None = None, full: bool = False):
    """B replicates of the whole E3 pipeline (propensity fit, classes, R, R_rec, Y_NL).
    cfg.takeall_phase2 (needs rng_ph2, a stream apart from rng so the base draws do not move) adds the
    phase-2 resampling of take-all strata (21.1). full=True returns a dict with Y, and A, P when the
    cells carry area (21.2), instead of the array of Y."""
    out = np.full(cfg.n_boot, np.nan)
    outA = np.full(cfg.n_boot, np.nan)
    cw0 = cells.cw
    use, skipped = takeall_strata(s) if cfg.takeall_phase2 else ([], [])
    for b in range(cfg.n_boot):
        w0 = rao_wu(s.w0, s.stratum, s.N_h, rng)
        cw = rao_wu(cw0, cells.gstratum, cells.C_g, rng)
        mult = takeall_phase2_mult(s, use, rng_ph2) if use else None
        try:
            e = e3_estimate(s, w0, cells, cw, cfg, mult)
            out[b] = e["Y"]
            outA[b] = e.get("A", np.nan)
        except np.linalg.LinAlgError:
            pass
    if not full:
        return out
    return {"Y": out, "A": outA, "P": out / outA, "ta_skipped": skipped, "ta_used": use}


def lin_var_p(s: ListSample, est: dict, cells: CellSample, V_Y: float) -> float:
    """Linearised variance of P = Y/A (design.md 8.8). A = frame area (fixed) + estimated not-on-list
    area, so V(A) and Cov(Y, A) come from the area-frame cells only: Cov(Y, A) ~ R_rec Cov(H, A_NL)
    (the variation of R_rec itself is ignored in the covariance)."""
    V_A = C_ZA = 0.0
    for g in range(cells.C_g.size):
        k = cells.gstratum == g
        c = int(k.sum())
        if c >= 2:
            fac = cells.C_g[g] ** 2 * (1 - c / cells.C_g[g]) / c
            V_A += fac * _s2(cells.za[k])
            C_ZA += fac * float(np.cov(cells.z[k], cells.za[k], ddof=1)[0, 1])
    A, P = est["A"], est["P"]
    return float((V_Y + P**2 * V_A - 2 * P * est["Rrec"] * C_ZA) / A**2)
