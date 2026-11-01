"""Stratification, Neyman allocation, take-all and collapse rule (design.md 4, 5)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import Config


def dalenius_hodges_cuts(area: np.ndarray, k: int, bins: int) -> np.ndarray:
    """Cumulative sqrt(f) rule (design.md 4.3). Returns k-1 interior cut points on area."""
    if k <= 1 or area.size == 0:
        return np.array([])
    f, edges = np.histogram(area, bins=bins)
    cum = np.cumsum(np.sqrt(f))
    targets = cum[-1] * np.arange(1, k) / k
    idx = np.searchsorted(cum, targets)
    return edges[np.minimum(idx + 1, bins)]  # upper edge of the bin where the target is reached


def neyman_allocate(N: np.ndarray, S: np.ndarray, n: int, n_min: int):
    """Neyman allocation with full enumeration and a minimum (design.md 5.2).

    Returns (n_h integers summing to n, take_all bool array, n_h real before rounding).
    Step 2: if n_h > N_h the stratum is fully enumerated, removed and the rest re-allocated.
    Step 3: n_h < n_min raised to min(n_min, N_h) (the caller collapses strata first).
    Step 4: largest-remainder rounding keeping the sum.
    """
    N = np.asarray(N, float)
    S = np.asarray(S, float)
    H = N.size
    full = np.zeros(H, bool)
    while True:
        rem = n - N[full].sum()
        free = ~full
        denom = (N[free] * S[free]).sum()
        nh = np.where(full, N, 0.0)
        nh[free] = rem * N[free] * S[free] / denom if denom > 0 else rem * N[free] / N[free].sum()
        over = free & (nh > N)
        if not over.any():
            break
        full |= over
    nh_real = nh.copy()
    lo = np.minimum(n_min, N)
    fixed = full.copy()
    # raise to minimum, take the excess from the strata with room above the minimum
    low = (~fixed) & (nh < lo)
    nh[low] = lo[low]
    fixed |= low
    for _ in range(H + 1):
        excess = nh.sum() - n
        if abs(excess) < 1e-9:
            break
        free = ~fixed
        if not free.any():
            break
        share = nh[free] / nh[free].sum()
        nh[free] -= excess * share
        low = free & (nh < lo)
        nh[low] = lo[low]
        fixed |= low
    out = np.floor(nh + 1e-9).astype(int)
    out = np.maximum(out, lo.astype(int))
    out = np.minimum(out, N.astype(int))
    deficit = int(n - out.sum())
    rema = nh - np.floor(nh + 1e-9)
    order = np.argsort(-rema, kind="stable")
    i = 0
    while deficit != 0 and i < 10 * H:
        j = order[i % H] if deficit > 0 else order[::-1][i % H]
        if deficit > 0 and out[j] < N[j] and not full[j]:
            out[j] += 1
            deficit -= 1
        elif deficit < 0 and out[j] > lo[j] and not full[j]:
            out[j] -= 1
            deficit += 1
        i += 1
    return out, full, nh_real


def take_all_units(area: np.ndarray, n: int, min_area: float, cap_frac: float) -> np.ndarray:
    """Take-all rule of design.md v0.2 section 4.4: the largest units by water area among those
    of at least `min_area` ha, up to floor(cap_frac * n) units. Returns a bool mask."""
    cap = int(np.floor(cap_frac * n))
    ta = np.zeros(area.size, bool)
    cand = np.where(area >= min_area)[0]
    top = cand[np.argsort(-area[cand], kind="stable")[:cap]]
    ta[top] = True
    return ta


def certainty_units(size_measure: np.ndarray, n: int, cap: int) -> np.ndarray:
    """v0.1 rule, no longer used by build_design (kept for reference and its tests).
    Unit-level take-all (design.md v0.1 4.4): move units, largest first, while their
    probability-proportional-to-size inclusion probability would exceed 1; at most `cap`.
    Returns a bool mask."""
    ta = np.zeros(size_measure.size, bool)
    order = np.argsort(-size_measure, kind="stable")
    while ta.sum() < cap:
        rem = n - ta.sum()
        pi = rem * size_measure / size_measure[~ta].sum()
        cand = (~ta) & (pi > 1.0)
        if not cand.any():
            break
        for j in order:
            if cand[j] and ta.sum() < cap:
                ta[j] = True
    return ta


@dataclass
class Design:
    strata: pd.DataFrame            # one row per stratum: label, N_h, n_h, take_all, kind
    unit_stratum: np.ndarray        # stratum index per listed unit
    cuts: dict                      # size-class cut points per type
    notes: list = field(default_factory=list)

    @property
    def N_h(self) -> np.ndarray:
        return self.strata["N_h"].values

    @property
    def n_h(self) -> np.ndarray:
        return self.strata["n_h"].values


def build_design(listed: pd.DataFrame, cfg: Config) -> Design:
    n_tot = cfg.n_per_district
    area = listed["area"].values
    typ = listed["type"].values
    ass = listed["assisted"].values
    N = len(listed)
    notes: list[str] = []

    # size classes per type (Dalenius-Hodges)
    size_class = np.zeros(N, int)
    cuts = {}
    for t in ("pond", "tank"):
        m = typ == t
        c = dalenius_hodges_cuts(area[m], cfg.n_size_classes, cfg.hist_bins)
        cuts[t] = c.tolist()
        size_class[m] = np.searchsorted(c, area[m], side="left")

    # take-all (v0.2): largest units >= 2 ha, capped at floor(0.1 n), counted inside n
    ta_unit = take_all_units(area, n_tot, cfg.take_all_min_area_ha, cfg.take_all_cap_frac)
    notes.append(f"take-all units: {int(ta_unit.sum())} (cap {int(np.floor(cfg.take_all_cap_frac * n_tot))}, "
                 f"{int((area >= cfg.take_all_min_area_ha).sum())} units >= {cfg.take_all_min_area_ha} ha)")

    n_rest = n_tot - int(ta_unit.sum())
    # strata keyed by (type, intensity, size class); collapse loop
    key = pd.DataFrame({"type": typ, "ass": ass, "sc": size_class})
    labels = {}  # (type, ass) -> list of groups of size classes
    groups: dict[tuple, list[list[int]]] = {
        (t, a): [[s] for s in range(cfg.n_size_classes)] for t in ("pond", "tank") for a in (0, 1)
    }
    while True:
        rows = []
        for (t, a), glist in groups.items():
            for gi, scs in enumerate(glist):
                m = (~ta_unit) & (typ == t) & (ass == a) & np.isin(size_class, scs)
                Nh = int(m.sum())
                if Nh == 0:
                    rows.append((t, a, gi, scs, 0, 0.0, m))
                    continue
                Sa = float(area[m].std(ddof=1)) if Nh > 1 else 0.0
                S = cfg.planning_productivity[(t, a)] * Sa
                rows.append((t, a, gi, scs, Nh, S, m))
        live = [r for r in rows if r[4] > 0]
        Nh = np.array([r[4] for r in live], float)
        Sh = np.array([r[5] for r in live], float)
        n_int, full, n_real = neyman_allocate(Nh, Sh, n_rest, cfg.n_min_stratum)
        # collapse check: <min frame units or <min selected units (and not fully enumerated)
        bad = None
        for r, nr, fl in zip(live, n_real, full):
            if (r[4] < cfg.min_frame_stratum or nr < cfg.n_min_stratum) and not fl:
                t, a, gi = r[0], r[1], r[2]
                if len(groups[(t, a)]) > 1:
                    bad = (t, a, gi)
                    break
        if bad is None:
            # empty groups (no units) also merge away
            empties = [(r[0], r[1], r[2]) for r in rows if r[4] == 0 and len(groups[(r[0], r[1])]) > 1]
            if empties:
                bad = empties[0]
        if bad is None:
            break
        t, a, gi = bad
        glist = groups[(t, a)]
        j = gi + 1 if gi + 1 < len(glist) else gi - 1   # next size class, else previous
        lo, hi = sorted((gi, j))
        merged = glist[lo] + glist[hi]
        notes.append(f"collapse: {t} assisted={a} size classes {glist[lo]}+{glist[hi]}")
        groups[(t, a)] = glist[:lo] + [merged] + glist[hi + 1:]

    unit_stratum = np.full(N, -1, int)
    recs = []
    for h, (r, ni, fl) in enumerate(zip(live, n_int, full)):
        unit_stratum[r[6]] = h
        recs.append({"label": f"{r[0]}|A{r[1]}|sc{'+'.join(map(str, r[3]))}",
                     "N_h": r[4], "n_h": int(ni), "take_all": bool(fl), "kind": "stratum",
                     "A_h": float(area[r[6]].sum())})
    if ta_unit.any():
        h = len(recs)
        unit_stratum[ta_unit] = h
        recs.append({"label": "TAKE-ALL", "N_h": int(ta_unit.sum()),
                     "n_h": int(ta_unit.sum()), "take_all": True, "kind": "take_all_units",
                     "A_h": float(area[ta_unit].sum())})
    assert (unit_stratum >= 0).all()
    df = pd.DataFrame(recs)
    return Design(df, unit_stratum, cuts, notes)
