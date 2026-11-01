"""Simulated harvest-event table (design.md 21.3). All values are SIMULATED.

One row per harvest event. Event quantities split each unit total with
Dirichlet(1) shares, so event sums reproduce the unit totals (criterion C3).
Random numbers come from their own SeedSequence child, so no stream of
`synth.py` or `simulate.py` moves.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .synth import District

REF_START = pd.Timestamp("2026-04-01")      # [DOC] reference year 2026-04-01..2027-03-31
REF_DAYS = 365
SEED_SURVIVAL = 0.5       # [ASSUMPTION] survival from stocked seed to harvest
SEED_MEAN_WT_KG = 0.8     # [ASSUMPTION] mean harvest weight per fish (kg)
SEED_NOISE_SIGMA = 0.3    # [ASSUMPTION] lognormal noise sd of the stocked count
EVENT_STREAM_KEY = 4096   # spawn_key of the event stream (the synth streams use 0 and 1)

EVENT_COLUMNS = ["event_id", "unit_id", "date", "q_diary", "q_ver", "seed_count"]


def unit_table(dist: District) -> pd.DataFrame:
    """Copy of `dist.units` with unique `unit_id`.

    `make_district` stores ids in a fixed-width string array (<U9), which cuts the
    not-on-list ids ("D1-NOL00000" -> "D1-NOL00") so they collide. Here the not-on-list
    ids are rebuilt from the row position. The district itself is not changed.
    """
    u = dist.units.copy()
    if not u["unit_id"].is_unique:
        nol = ~u["on_list"].to_numpy()
        u["unit_id"] = u["unit_id"].astype(object)
        u.loc[nol, "unit_id"] = [f"D1-NOL{i:05d}" for i in range(int(nol.sum()))]
    return u


def build_events(dist: District, x: np.ndarray | None = None,
                 verified: np.ndarray | None = None,
                 verify_prob: float | None = None,
                 seed: int | None = None) -> pd.DataFrame:
    """Build the event table for every unit of `dist.units`.

    x: unit diary totals (tonnes), aligned with `dist.units`; default x = y (no diary error).
    verified: bool mask per unit, True = phase-2 unit; default None = every unit is eligible.
        Eligible events are verified with probability `verify_prob` (default `cfg.verify_prob`).
        q_ver is NaN for unverified events.
    seed: entropy of the event stream; default `cfg.pop_seed`.
    Quantities are tonnes. `seed_count` is a unit-year attribute (fingerlings stocked),
    repeated on each event row of the unit.
    """
    u = unit_table(dist)
    n = len(u)
    y = u["y"].to_numpy(float)
    x = y if x is None else np.asarray(x, float)
    if x.shape != (n,):
        raise ValueError("x must have one value per unit")
    mask = np.ones(n, bool) if verified is None else np.asarray(verified, bool)
    if mask.shape != (n,):
        raise ValueError("verified must have one value per unit")
    vp = dist.cfg.verify_prob if verify_prob is None else verify_prob
    entropy = dist.cfg.pop_seed if seed is None else seed
    rng = np.random.default_rng(np.random.SeedSequence(entropy, spawn_key=(EVENT_STREAM_KEY,)))

    k = u["n_events"].to_numpy(int)
    idx = np.repeat(np.arange(n), k)                       # unit index per event
    total = idx.size
    w = rng.exponential(1.0, total)                        # Dirichlet(1) = normalised Exp(1)
    share = w / np.bincount(idx, weights=w, minlength=n)[idx]
    day = rng.integers(0, REF_DAYS, total)
    ver = (rng.random(total) < vp) & mask[idx]
    seed_noise = np.exp(SEED_NOISE_SIGMA * rng.standard_normal(n) - SEED_NOISE_SIGMA**2 / 2)
    seed_unit = y * 1000.0 / (SEED_SURVIVAL * SEED_MEAN_WT_KG) * seed_noise

    first = np.cumsum(k) - k
    seq = np.arange(total) - np.repeat(first, k)
    uid = u["unit_id"].to_numpy()
    return pd.DataFrame({
        "event_id": [f"{uid[i]}-E{s}" for i, s in zip(idx, seq)],
        "unit_id": uid[idx],
        "date": REF_START + pd.to_timedelta(day, unit="D"),
        "q_diary": x[idx] * share,
        "q_ver": np.where(ver, y[idx] * share, np.nan),
        "seed_count": seed_unit[idx],
    })[EVENT_COLUMNS]
