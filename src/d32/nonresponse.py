"""Response-propensity classes (design.md 9)."""
from __future__ import annotations

import numpy as np


def fit_logit(Z: np.ndarray, resp: np.ndarray, w: np.ndarray, ridge: float, iters: int = 50) -> np.ndarray:
    """Weighted logistic regression by Newton/IRLS. Z includes the intercept in column 0
    (not penalised). Weights are rescaled to mean 1. A tiny ridge keeps it finite under separation."""
    w = w / w.mean()
    p = Z.shape[1]
    pen = np.full(p, ridge)
    pen[0] = 0.0
    beta = np.zeros(p)
    yv = resp.astype(float)
    for _ in range(iters):
        eta = np.clip(Z @ beta, -30, 30)
        mu = 1 / (1 + np.exp(-eta))
        g = Z.T @ (w * (yv - mu)) - pen * beta
        H = (Z * (w * mu * (1 - mu))[:, None]).T @ Z + np.diag(pen) + 1e-10 * np.eye(p)
        step = np.linalg.solve(H, g)
        beta = beta + step
        if np.abs(step).max() < 1e-9:
            break
    return beta


def propensity_classes(phat: np.ndarray, k: int) -> np.ndarray:
    """Quintile-style classes by predicted propensity (equal counts, ties broken by order)."""
    order = np.argsort(phat, kind="stable")
    cls = np.empty(phat.size, int)
    cls[order] = np.minimum((np.arange(phat.size) * k) // phat.size, k - 1)
    return cls


def class_adjustment(w0: np.ndarray, resp: np.ndarray, cls: np.ndarray, cap: float):
    """phi_c = sum_c w0 / sum_{c,resp} w0, merging a class with its neighbour while phi_c > cap.
    Returns (phi per unit, final class labels). Classes are ordered by propensity, so the
    neighbour is the next-higher class (the previous one for the last class)."""
    cls = cls.copy()
    while True:
        labels = np.unique(cls)
        num = {c: w0[cls == c].sum() for c in labels}
        den = {c: w0[(cls == c) & resp].sum() for c in labels}
        phi = {c: (num[c] / den[c] if den[c] > 0 else np.inf) for c in labels}
        bad = [c for c in labels if phi[c] > cap]
        if not bad or labels.size == 1:
            break
        c = bad[0]
        i = int(np.where(labels == c)[0][0])
        nb = labels[i + 1] if i + 1 < labels.size else labels[i - 1]
        cls[cls == c] = nb
    return np.array([phi[c] for c in cls]), cls


def propensity_scores(Z: np.ndarray, resp: np.ndarray, ridge: float) -> np.ndarray:
    """Predicted response propensity from an UNWEIGHTED logit (design.md v0.2 section 9, step 1).
    Z must hold exactly: intercept, log area, assisted, distance."""
    beta = fit_logit(Z, resp, np.ones(Z.shape[0]), ridge)
    return 1 / (1 + np.exp(-np.clip(Z @ beta, -30, 30)))


def nonresponse_weights(w0: np.ndarray, resp: np.ndarray, Z: np.ndarray, k: int, cap: float, ridge: float):
    """w0 * phi for respondents, 0 otherwise (steps 1-4 of section 9).
    Returns (weights, final classes, phi per unit)."""
    phat = propensity_scores(Z, resp, ridge)
    cls = propensity_classes(phat, k)
    phi, cls = class_adjustment(w0, resp, cls, cap)
    return np.where(resp, w0 * phi, 0.0), cls, phi
