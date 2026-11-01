"""Fay-Herriot small-area estimation for development blocks (design.md 11, 21.4). numpy/scipy only.

Pipeline per replication (all functions work on arrays over the blocks that have a direct estimate):
GVF smoothing of the direct variances, Li-Lahiri adjusted REML for sigma_v^2, shrinkage, ratio
benchmarking to the direct district total, Prasad-Rao MSE.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize_scalar


def gvf_smooth(psi: np.ndarray, n: np.ndarray, theta: np.ndarray) -> np.ndarray:
    """Generalised variance function: OLS of log psi on (1, log n, log theta), back-transformed and
    rescaled so that the mean smoothed variance equals the mean direct variance (a ratio correction
    for the log-scale bias). Blocks whose raw psi or theta is not positive are not used in the fit
    but still receive the fitted value. Fewer than 5 usable blocks: the raw variances are returned."""
    ok = (psi > 0) & (theta > 0) & (n > 0) & np.isfinite(psi) & np.isfinite(theta)
    if ok.sum() < 5:
        return psi.copy()
    D = np.column_stack([np.ones(psi.size), np.log(np.where(n > 0, n, 1)), np.log(np.where(theta > 0, theta, 1))])
    coef, *_ = np.linalg.lstsq(D[ok], np.log(psi[ok]), rcond=None)
    fit = np.exp(D @ coef)
    fit *= psi[ok].mean() / fit[ok].mean()
    return fit


def _neg_loglik(A: float, theta, psi, X, adjusted: bool) -> float:
    """Minus the (adjusted) REML log-likelihood, constants dropped. Adjustment factor h(A) = A."""
    v = A + psi
    W = 1.0 / v
    XtWX = (X.T * W) @ X
    beta = np.linalg.solve(XtWX, (X.T * W) @ theta)
    r = theta - X @ beta
    ll = -0.5 * np.sum(np.log(v)) - 0.5 * np.linalg.slogdet(XtWX)[1] - 0.5 * np.sum(W * r * r)
    if adjusted:
        ll += np.log(A)
    return -ll


def sigma_v2(theta, psi, X, adjusted: bool = True) -> float:
    """REML estimate of sigma_v^2 on [0, inf). adjusted=True multiplies the REML likelihood by A
    (Li-Lahiri), so the maximiser is strictly positive. adjusted=False can return exactly 0."""
    scale = max(float(np.var(theta, ddof=1)), float(np.mean(psi)), 1e-12)
    grid = np.geomspace(1e-8 * scale, 100 * scale, 400)
    if not adjusted:
        grid = np.concatenate([[0.0], grid])
    f = np.array([_neg_loglik(a, theta, psi, X, adjusted) for a in grid])
    i = int(np.argmin(f))
    if i == 0 and not adjusted:
        return 0.0
    lo, hi = np.log(grid[max(i - 1, 1 if not adjusted else 0)]), np.log(grid[min(i + 1, grid.size - 1)])
    res = minimize_scalar(lambda t: _neg_loglik(np.exp(t), theta, psi, X, adjusted), bounds=(lo, hi), method="bounded",
                          options={"xatol": 1e-10})
    return float(np.exp(res.x)) if res.fun <= f[i] else float(grid[i])


def shrink(theta, psi, X, s2: float) -> dict:
    """Best predictor for a given sigma_v^2: gamma_b, beta (weighted LS), prediction, Prasad-Rao MSE
    g1 + g2 + 2 g3 (design.md 11)."""
    v = s2 + psi
    W = 1.0 / v
    XtWX = (X.T * W) @ X
    inv = np.linalg.inv(XtWX)
    beta = inv @ ((X.T * W) @ theta)
    gamma = s2 / v
    synth = X @ beta
    pred = gamma * theta + (1 - gamma) * synth
    g1 = gamma * psi
    g2 = (1 - gamma) ** 2 * np.einsum("ij,jk,ik->i", X, inv, X)
    var_s2 = 2.0 / np.sum(W**2)
    g3 = psi**2 / v**3 * var_s2
    return {"gamma": gamma, "beta": beta, "pred": pred, "mse": g1 + g2 + 2 * g3}


def benchmark(pred: np.ndarray, area: np.ndarray, district_total: float) -> np.ndarray:
    """Ratio benchmarking: scale the block productivities so that sum(pred_b * A_b) = district_total."""
    return pred * (district_total / float(np.sum(pred * area)))


def fay_herriot(theta, psi_raw, n_b, X, area, district_total: float) -> dict:
    """All blocks in: theta (direct t/ha; nan if the block has no respondent), raw bootstrap variances
    psi_raw, respondents per block n_b, covariates X (blocks x p), frame water area per block, and the
    direct district total to benchmark to. Blocks with no direct estimate get gamma = 0 (synthetic)."""
    m = len(theta)
    ok = np.isfinite(theta) & np.isfinite(psi_raw) & (n_b > 0)
    psi = np.full(m, np.inf)
    psi[ok] = gvf_smooth(psi_raw[ok], n_b[ok], theta[ok])
    s2_adj = sigma_v2(theta[ok], psi[ok], X[ok], True)
    s2_raw = sigma_v2(theta[ok], psi[ok], X[ok], False)
    sh = shrink(theta[ok], psi[ok], X[ok], s2_adj)
    pred = X @ sh["beta"]
    gamma = np.zeros(m)
    mse = np.full(m, np.nan)
    inv = np.linalg.inv((X[ok].T / (s2_adj + psi[ok])) @ X[ok])
    gamma[ok] = sh["gamma"]
    pred[ok] = sh["pred"]
    mse[ok] = sh["mse"]
    mse[~ok] = s2_adj + np.einsum("ij,jk,ik->i", X[~ok], inv, X[~ok])
    return {"psi_gvf": psi, "sigma_v2": s2_adj, "sigma_v2_unadj": s2_raw, "gamma": gamma, "fh": pred,
            "fh_bm": benchmark(pred, area, district_total), "mse": mse, "valid": ok}
