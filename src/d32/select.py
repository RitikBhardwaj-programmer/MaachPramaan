"""Order-independent PRN selection and phase-2 subsampling (design.md 13, 8.2)."""
from __future__ import annotations

import hashlib
import hmac

import numpy as np


def seed_bytes(seed) -> bytes:
    return str(seed).encode("utf-8")


def prn_values(seed, unit_ids) -> np.ndarray:
    """u_i = int(HMAC-SHA256(seed, unit_id)[0:8]) / 2^64, kept to its top 53 bits so the
    float is exact. Depends only on (seed, unit_id): other units cannot change it."""
    key = seed_bytes(seed)
    out = np.empty(len(unit_ids))
    for i, uid in enumerate(unit_ids):
        d = hmac.digest(key, str(uid).encode("utf-8"), hashlib.sha256)
        out[i] = (int.from_bytes(d[:8], "big") >> 11) / 2.0**53
    return out


def select_smallest(prn: np.ndarray, stratum: np.ndarray, n_h: np.ndarray) -> np.ndarray:
    """Indices (sorted) of the n_h[h] smallest PRNs inside each stratum h (SRSWOR, Ohlsson 1995)."""
    chosen = []
    for h, k in enumerate(n_h):
        idx = np.where(stratum == h)[0]
        if k >= idx.size:
            chosen.append(idx)
        else:
            chosen.append(idx[np.argsort(prn[idx], kind="stable")[:k]])
    return np.sort(np.concatenate(chosen)) if chosen else np.array([], int)


def phase2_size(n_resp: int, nu: float, m_min: int) -> int:
    """m_h = max(m_min, round(nu * n'_h)), capped at n'_h."""
    return int(min(n_resp, max(m_min, np.floor(nu * n_resp + 0.5))))


def phase2_subsample(stratum: np.ndarray, resp: np.ndarray, H: int, nu: float, m_min: int,
                     rng: np.random.Generator) -> np.ndarray:
    """Random subsample of the respondents inside each stratum (bool mask over the sample)."""
    ver = np.zeros(stratum.size, bool)
    for h in range(H):
        idx = np.where((stratum == h) & resp)[0]
        if idx.size == 0:
            continue
        m = phase2_size(idx.size, nu, m_min)
        ver[rng.choice(idx, size=m, replace=False)] = True
    return ver


def rep_streams(master_seed: int, rep: int, k: int = 6):
    """Child generators, one per purpose, from SeedSequence(master).spawn-equivalent
    (spawn_key=(rep,)) then .spawn(k). Purposes never share a stream."""
    ss = np.random.SeedSequence(master_seed, spawn_key=(rep,))
    return [np.random.Generator(np.random.PCG64(c)) for c in ss.spawn(k)]
