"""Estimators E0-E3 (design.md 8, 15.2). Pure functions on arrays."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import Config
from .nonresponse import nonresponse_weights


@dataclass
class ListSample:
    stratum: np.ndarray   # int stratum index per selected unit
    N_h: np.ndarray       # frame count per stratum
    w0: np.ndarray        # design weight N_h / n_h
    resp: np.ndarray      # bool: completed the diary year
    ver: np.ndarray       # bool: phase-2 verified (subset of resp)
    x: np.ndarray         # diary total (nan unless resp)
    y: np.ndarray         # verified total (nan unless ver)
    r: np.ndarray         # recall total (all selected units answer recall)
    Z: np.ndarray         # propensity covariates: intercept, log area, assisted, distance
    area: np.ndarray | None = None   # water area (ha) of each selected unit; None = no calibration
    A_h: np.ndarray | None = None    # frame water area per stratum (ha)
    tiebreak: np.ndarray | None = None   # PRN per selected unit; orders equal propensities (design.md 20.1)

    @property
    def H(self) -> int:
        return self.N_h.size


@dataclass
class CellSample:
    gstratum: np.ndarray  # cell stratum per sampled cell
    C_g: np.ndarray       # cells per stratum
    c_g: np.ndarray       # sampled cells per stratum
    z: np.ndarray         # raw recall total of the not-on-list units found in the cell
    n_nol: np.ndarray     # number of not-on-list units found in the cell

    @property
    def cw(self) -> np.ndarray:
        return (self.C_g / self.c_g)[self.gstratum]


def design_weights(stratum: np.ndarray, N_h: np.ndarray, n_h: np.ndarray) -> np.ndarray:
    """w0 = N_h / n_h (design.md 8.2)."""
    return (N_h / n_h)[stratum]


def _greg_stratum(w, a, N, A, lo, hi, max_iter, area_too):
    """Linear (GREG) calibration of one stratum's respondent weights to N (and A), g bounded to
    [lo, hi] by iterative truncation. Returns (g, ok). z_i = (1, a_i) or (1,)."""
    z = np.column_stack([np.ones_like(a), a]) if area_too else np.ones((a.size, 1))
    tx = np.array([N, A]) if area_too else np.array([N])
    g = np.ones(a.size)
    fixed = np.zeros(a.size, bool)
    converged = False
    for _ in range(max_iter):
        free = ~fixed
        if free.sum() < z.shape[1]:
            break
        resid = tx - (w[fixed] * g[fixed]) @ z[fixed]
        T = (z[free].T * w[free]) @ z[free]
        t_free = w[free] @ z[free]
        try:
            lam = np.linalg.solve(T, resid - t_free)
        except np.linalg.LinAlgError:
            break
        g[free] = 1 + z[free] @ lam
        vlo, vhi = free & (g < lo), free & (g > hi)
        if not (vlo | vhi).any():
            converged = True
            break
        g[vlo], g[vhi] = lo, hi
        fixed |= vlo | vhi
    got = (w * g) @ z
    ok = converged and bool(np.all(np.abs(got - tx) <= 1e-6 * np.abs(tx)))
    return g, ok


def calibrate_detail(w, stratum, area, N_h, A_h, resp, cfg: Config):
    """Step 5 of design.md section 9 (v0.3). Respondents of each stratum are calibrated to the frame
    count N_h and water area A_h; a stratum with fewer than cfg.cal_min_resp respondents to N_h only.
    If cfg.cal_fallback and a both-constraint calibration still misses after cfg.cal_max_iter
    iterations, the stratum is redone with N_h only. With cal_min_resp=4 and cal_fallback=False this
    is the v0.2 rule.

    Returns (g per unit, info) with info lists of stratum indices:
      miss_before   strata whose first attempt missed (v0.2 definition; includes zero respondents)
      fallback      strata redone with N_h only
      unmet_after   strata with an attempted constraint still unmet at the end (V1; no zero-respondent)
      zero_resp     strata with no respondents (no weights, recorded)
    """
    g = np.ones(w.size)
    info = {"miss_before": [], "fallback": [], "unmet_after": [], "zero_resp": []}
    args = (cfg.cal_g_lo, cfg.cal_g_hi, cfg.cal_max_iter)
    for h in range(N_h.size):
        idx = np.where(resp & (stratum == h))[0]
        if idx.size == 0:
            info["miss_before"].append(h)
            info["zero_resp"].append(h)
            continue
        both = idx.size >= cfg.cal_min_resp
        gh, ok = _greg_stratum(w[idx], area[idx], N_h[h], A_h[h], *args, both)
        if not ok:
            info["miss_before"].append(h)
            if both and cfg.cal_fallback:
                gh, ok = _greg_stratum(w[idx], area[idx], N_h[h], A_h[h], *args, False)
                info["fallback"].append(h)
        g[idx] = gh
        if not ok:
            info["unmet_after"].append(h)
    return g, info


def calibrate(w, stratum, area, N_h, A_h, resp, cfg: Config):
    """As calibrate_detail; returns (g, strata that end with an unmet constraint, or no respondents)."""
    g, info = calibrate_detail(w, stratum, area, N_h, A_h, resp, cfg)
    return g, sorted(info["unmet_after"] + info["zero_resp"])


def phase2_weights(w0, w1, stratum, resp, ver, H) -> np.ndarray:
    """w2 = w1 * n'_h / m_h, written as w1 * sum_resp(w0) / sum_ver(w0) in the stratum; with a
    constant w0 inside the stratum this is exactly n'_h / m_h (design.md 8.2)."""
    sr = np.bincount(stratum, weights=w0 * resp, minlength=H)
    sv = np.bincount(stratum, weights=w0 * ver, minlength=H)
    f = np.where(sv > 0, sr / np.where(sv > 0, sv, 1), 0.0)
    return np.where(ver, w1 * f[stratum], 0.0)


def ratio_total(w1, w2, x, y, r, resp, ver):
    X = float(np.sum(w1[resp] * x[resp]))
    wy = float(np.sum(w2[ver] * y[ver]))
    wx = float(np.sum(w2[ver] * x[ver]))
    wr = float(np.sum(w2[ver] * r[ver]))
    R = wy / wx if wx > 0 else np.nan
    Rrec = wy / wr if wr > 0 else np.nan
    return X, R, Rrec


def e3_estimate(s: ListSample, w0: np.ndarray, cells: CellSample, cw: np.ndarray, cfg: Config) -> dict:
    """Proposed estimator: two-phase combined ratio + propensity classes + not-on-list domain."""
    wa, cls, phi = nonresponse_weights(w0, s.resp, s.Z, cfg.n_np_classes, cfg.phi_cap, cfg.logit_ridge,
                                       s.tiebreak)
    if s.area is not None and s.A_h is not None:
        g, cal = calibrate_detail(wa, s.stratum, s.area, s.N_h, s.A_h, s.resp, cfg)
    else:                                   # no frame totals supplied: classes only
        g, cal = np.ones_like(wa), {"miss_before": [], "fallback": [], "unmet_after": [], "zero_resp": []}
    cal_failed = cal["miss_before"]
    w1 = wa * g
    w2 = phase2_weights(w0, w1, s.stratum, s.resp, s.ver, s.H)
    X, R, Rrec = ratio_total(w1, w2, s.x, s.y, s.r, s.resp, s.ver)
    YL = R * X
    Hhat = float(np.sum(cw * cells.z))
    YNL = Rrec * Hhat
    nol_units = float(np.sum(cw * cells.n_nol))
    return {"Y": YL + YNL, "YL": YL, "YNL": YNL, "X": X, "R": R, "Rrec": Rrec, "H": Hhat,
            "nol_units": nol_units, "w1": w1, "w2": w2, "classes": cls, "phi": phi, "g": g,
            "cal_failed": cal_failed, "cal": cal}


def e2_estimate(s: ListSample, w1: np.ndarray) -> float:
    """E2: diary-only stratified expansion (same nonresponse classes, no verification, list only)."""
    return float(np.sum(w1[s.resp] * s.x[s.resp]))


def e1_estimate(s: ListSample) -> float:
    """E1: recall-only stratified expansion over all selected units (list only)."""
    return float(np.sum(s.w0 * s.r))


def e0_estimate(frame_area_ha: float, norm_t_per_ha: float) -> float:
    """E0: frame area x one productivity figure."""
    return frame_area_ha * norm_t_per_ha


def kish_deff(w: np.ndarray) -> float:
    """Kish design effect from weights (design.md 8.9)."""
    w = w[w > 0]
    return float(w.size * np.sum(w**2) / np.sum(w) ** 2)


def kish_deff_factors(f: np.ndarray, stratum: np.ndarray, resp: np.ndarray) -> float:
    """Form (b) of design.md 8.9: Kish deff of the factors phi*g only, computed inside each
    stratum and pooled with the respondent counts as weights."""
    num = den = 0.0
    for h in np.unique(stratum[resp]):
        v = f[resp & (stratum == h)]
        num += v.size * kish_deff(v)
        den += v.size
    return float(num / den)
