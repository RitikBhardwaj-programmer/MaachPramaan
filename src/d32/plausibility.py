"""Plausibility checks of design.md section 10 (flag, never overwrite). SIMULATED data.

`run_checks` is read-only: it returns a flag table and changes no input. `inject_faults`
works on a copy and returns the injected ids, for testing recall (criterion C1).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FLAG_COLUMNS = ["unit_id", "event_id", "check", "value", "threshold"]
CHECKS = ["yield_outlier", "event_size", "seed_consistency", "duplicate", "diary_vs_verified"]

MZ_THRESHOLD = 3.5        # [DOC] Iglewicz-Hoaglin
MIN_STRATUM_UNITS = 5     # [ASSUMPTION] a stratum smaller than this gets no yield flags
X10_LOG_LR_CUT = 0.5      # [DOC] 21.3b: 95th percentile of clean scores on the throw-away seeds, rounded
SURVIVAL_UPPER = 0.9      # [ASSUMPTION] upper survival rate for the seed check
WEIGHT_UPPER_KG = 1.5     # [ASSUMPTION] upper mean harvest weight (kg) for the seed check
DUP_TOL = 0.05            # [DOC] same quantity within 5%
GAP_THRESHOLD = 0.5       # [DOC] diary vs verified gap above 50%


def _strata(units: pd.DataFrame) -> pd.Series:
    """Stratum label per unit: `stratum` column, else type x assisted, else one stratum."""
    if "stratum" in units:
        s = units["stratum"].astype(str)
    elif {"type", "assisted"} <= set(units.columns):
        s = units["type"].astype(str) + "-" + units["assisted"].astype(str)
    else:
        s = pd.Series("all", index=units.index)
    return pd.Series(s.to_numpy(), index=units["unit_id"].to_numpy())


def _rows(unit_id, event_id, check, value, threshold) -> pd.DataFrame:
    return pd.DataFrame({"unit_id": unit_id, "event_id": event_id, "check": check,
                         "value": value, "threshold": threshold})


def x10_log_lr(units: pd.DataFrame, events: pd.DataFrame) -> np.ndarray:
    """log LR of "this event was entered x10" against "clean", per event row (design.md 21.3b).

    Share part: n log D - log 10, D = 10 / (10 - 9 s'), s' the event's share of the unit total.
    Total part: Gaussian test of log(total / anchor), anchor = stocked seed for assisted units
    with a seed count, else area; centre and spread are the median and 1.4826 x MAD within
    stratum and anchor type, pooled over the anchor type for small or flat groups.
    NaN where the score cannot be formed (no positive total or anchor, no usable spread).
    """
    st = _strata(units)
    ids = units["unit_id"].to_numpy()
    area = pd.Series(units["area"].to_numpy(float), index=ids)
    assisted = pd.Series(units["assisted"].to_numpy(bool) if "assisted" in units else False, index=ids)

    uid = events["unit_id"].to_numpy()
    q = events["q_diary"].to_numpy(float)
    grp = events.groupby("unit_id")["q_diary"]
    tot, n_ev = grp.sum(), grp.size()
    T = tot.reindex(uid).to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        s = np.where(T > 0, q / T, np.nan)
        log_d = np.log(10.0) - np.log(10.0 - 9.0 * s)
    share = n_ev.reindex(uid).to_numpy() * log_d - np.log(10.0)

    seed = events.groupby("unit_id")["seed_count"].median().reindex(tot.index)
    use_seed = assisted.reindex(tot.index, fill_value=False).to_numpy() & (seed.to_numpy() > 0)
    anchor = np.where(use_seed, seed.to_numpy(), area.reindex(tot.index).to_numpy())
    with np.errstate(divide="ignore", invalid="ignore"):
        ell = pd.Series(np.log(tot.to_numpy() / anchor), index=tot.index)
    keep = np.isfinite(ell.to_numpy())
    ell = ell[keep]
    kind = np.where(use_seed[keep], "seed", "area")
    key = st.reindex(ell.index).astype(str).to_numpy() + "|" + kind

    def centre_spread(by):
        mu = ell.groupby(by).transform("median")
        sd = 1.4826 * (ell - mu).abs().groupby(by).transform("median")
        return mu, sd, ell.groupby(by).transform("size")

    mu, sd, cnt = centre_spread(key)
    p_mu, p_sd, p_cnt = centre_spread(kind)
    small = (cnt < MIN_STRATUM_UNITS) | (sd <= 0)
    mu, sd = mu.where(~small, p_mu), sd.where(~small, p_sd)
    sd = sd.where((sd > 0) & ~(small & (p_cnt < MIN_STRATUM_UNITS)))

    l, m, sdv = ell.reindex(uid).to_numpy(), mu.reindex(uid).to_numpy(), sd.reindex(uid).to_numpy()
    z0, z1 = (l - m) / sdv, (l - log_d - m) / sdv
    return share + (z0**2 - z1**2) / 2


def unit_production_kg(events: pd.DataFrame) -> pd.Series:
    """Observed unit production: sum of the diary events, in kg (indexed by unit_id)."""
    return events.groupby("unit_id")["q_diary"].sum() * 1000.0


def run_checks(units: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Return the flag table (columns FLAG_COLUMNS). Inputs are not modified.

    units needs `unit_id`, `area` and, for strata, `stratum` or `type` + `assisted`.
    events is the table of `events.build_events`. Unit-level flags have `event_id` = None.
    """
    st = _strata(units)
    area = pd.Series(units["area"].to_numpy(float), index=units["unit_id"].to_numpy())
    out = []

    # 1. yield outlier: modified z-score of log(production/area) within stratum (unit level)
    prod = unit_production_kg(events)
    prod = prod[prod > 0]
    u = np.log(prod / 1000.0 / area.reindex(prod.index))
    for _, g in u.groupby(st.reindex(u.index)):
        if len(g) < MIN_STRATUM_UNITS:
            continue
        med = g.median()
        mad = (g - med).abs().median()
        if mad == 0:
            continue
        m = 0.6745 * (g - med) / mad
        f = m[m.abs() > MZ_THRESHOLD]
        out.append(_rows(f.index, None, "yield_outlier", f.to_numpy(), MZ_THRESHOLD))

    # 2. event size: likelihood ratio of a x10 entry slip (design.md 21.3b)
    score = x10_log_lr(units, events)
    hit = score > X10_LOG_LR_CUT
    out.append(_rows(events["unit_id"].to_numpy()[hit], events["event_id"].to_numpy()[hit],
                     "event_size", score[hit], X10_LOG_LR_CUT))

    # 3. seed consistency: production above what the stocked seed can give at upper rates
    seed = events.groupby("unit_id")["seed_count"].median()
    cap = seed * SURVIVAL_UPPER * WEIGHT_UPPER_KG
    bad = prod.reindex(cap.index).dropna()
    bad = bad[bad > cap.reindex(bad.index)]
    out.append(_rows(bad.index, None, "seed_consistency", bad.to_numpy(), cap.reindex(bad.index).to_numpy()))

    # 4. duplicates: same unit, same day, quantity within 5% (both members are flagged)
    d = events[["unit_id", "event_id", "date", "q_diary"]]
    d = d[d.duplicated(["unit_id", "date"], keep=False)].sort_values(["unit_id", "date", "q_diary"])
    if len(d):
        same = (d["unit_id"].to_numpy()[1:] == d["unit_id"].to_numpy()[:-1]) & \
               (d["date"].to_numpy()[1:] == d["date"].to_numpy()[:-1])
        a, b = d["q_diary"].to_numpy()[:-1], d["q_diary"].to_numpy()[1:]
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = np.where(b > 0, (b - a) / b, np.inf)
        rel = np.where(same, rel, np.inf)
        pair = np.flatnonzero(rel <= DUP_TOL)
        rows = np.unique(np.concatenate([pair, pair + 1]))
        relf = np.full(len(d), np.inf)
        relf[:-1] = rel
        relf[1:] = np.minimum(relf[1:], rel)   # smaller of the two neighbouring gaps
        r = d.iloc[rows]
        out.append(_rows(r["unit_id"].to_numpy(), r["event_id"].to_numpy(), "duplicate",
                         relf[rows], DUP_TOL))

    # 5. diary vs verified
    qv = events["q_ver"].to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        gap = np.where(qv > 0, np.abs(events["q_diary"].to_numpy() - qv) / qv, 0.0)
    hit = gap > GAP_THRESHOLD
    out.append(_rows(events["unit_id"].to_numpy()[hit], events["event_id"].to_numpy()[hit],
                     "diary_vs_verified", gap[hit], GAP_THRESHOLD))

    out = [o for o in out if len(o)]
    if not out:
        return pd.DataFrame({c: pd.Series(dtype=object) for c in FLAG_COLUMNS})
    flags = pd.concat(out, ignore_index=True)
    flags["event_id"] = flags["event_id"].astype(object).where(flags["event_id"].notna(), None)
    return flags[FLAG_COLUMNS]


def inject_faults(events: pd.DataFrame, rate: float = 0.02, seed: int = 0):
    """Return (copy of events with injected faults, dict of injected ids). Input is untouched.

    duplicate: new event rows copying a chosen event (same unit and day, quantity +-4%);
    x10: diary quantity of chosen events times 10;
    seed: all rows of chosen units get seed_count = 0.1 x need x U(0.3, 1), `need` being the seed
        that the clean production requires at the upper rates of the seed check;
    gap: diary quantity of chosen verified events set to 1.6-2.5x or 0.2-0.4x of q_ver.
    Duplicate, x10 and gap use disjoint events; seed units are drawn independently.
    """
    rng = np.random.default_rng(seed)
    ev = events.copy()
    n = len(ev)
    m = max(1, int(round(rate * n)))
    perm = rng.permutation(n)
    dup_pos, x10_pos = perm[:m], perm[m:2 * m]
    ver_pos = np.flatnonzero(ev["q_ver"].notna().to_numpy())
    ver_pos = rng.permutation(np.setdiff1d(ver_pos, np.concatenate([dup_pos, x10_pos])))
    gap_pos = ver_pos[:m]

    q = ev["q_diary"].to_numpy().copy()
    qv = ev["q_ver"].to_numpy()
    q[x10_pos] *= 10.0
    factor = np.where(rng.random(gap_pos.size) < 0.5, rng.uniform(1.6, 2.5, gap_pos.size),
                      rng.uniform(0.2, 0.4, gap_pos.size))
    q[gap_pos] = qv[gap_pos] * factor

    prod = unit_production_kg(events)
    units = prod.index.to_numpy()
    seed_units = units[rng.permutation(units.size)[:max(1, int(round(rate * units.size)))]]
    need = prod.reindex(seed_units) / (SURVIVAL_UPPER * WEIGHT_UPPER_KG)
    new_seed = (0.1 * need * rng.uniform(0.3, 1.0, need.size)).to_dict()
    ev["q_diary"] = q
    sel = ev["unit_id"].isin(seed_units)
    ev.loc[sel, "seed_count"] = ev.loc[sel, "unit_id"].map(new_seed)

    dup = ev.iloc[dup_pos].copy()
    dup["event_id"] = dup["event_id"] + "-DUP"
    dup["q_diary"] = dup["q_diary"] * rng.uniform(0.96, 1.04, len(dup))
    dup["q_ver"] = np.nan
    ids = {"duplicate": set(dup["event_id"]), "x10": set(events["event_id"].to_numpy()[x10_pos]),
           "seed": set(seed_units), "gap": set(events["event_id"].to_numpy()[gap_pos])}
    return pd.concat([ev, dup], ignore_index=True), ids
