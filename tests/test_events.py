"""Event table tests (design.md 21.3, criterion C3). SIMULATED data; small district for speed."""
from dataclasses import replace

import numpy as np
import pandas as pd

from d32.config import BASE
from d32.events import REF_DAYS, REF_START, build_events, unit_table
from d32.synth import make_district

SMALL = dict(n_listed=800, n_not_on_list=60, n_cells=60)   # test-only sizes; seeds 1, 2, 3 (not run seeds)


def _district(pop_seed=1, **over):
    return make_district(replace(BASE, pop_seed=pop_seed, **SMALL, **over))


def test_columns_and_dates():
    d = _district()
    ev = build_events(d)
    assert list(ev.columns) == ["event_id", "unit_id", "date", "q_diary", "q_ver", "seed_count"]
    assert ev["event_id"].is_unique
    assert len(ev) == int(d.units["n_events"].sum())
    assert ev["date"].min() >= REF_START
    assert ev["date"].max() <= REF_START + pd.Timedelta(days=REF_DAYS - 1)
    assert ev["date"].max() <= pd.Timestamp("2027-03-31")


def test_c3_event_sums_equal_unit_totals():
    for ps in (1, 2, 3):
        d = _district(ps)
        u = unit_table(d).set_index("unit_id")
        rng = np.random.default_rng(ps)
        x = u["y"].to_numpy() * rng.uniform(0.6, 1.2, len(u))      # any diary totals
        ev = build_events(d, x=x, verified=rng.random(len(u)) < 0.3, verify_prob=1.0)
        sx = ev.groupby("unit_id")["q_diary"].sum().reindex(u.index)
        assert np.abs(sx.to_numpy() - x).max() < 1e-9
        ver = ev[ev["q_ver"].notna()]
        sy = ver.groupby("unit_id")["q_ver"].sum()
        assert np.abs(sy.to_numpy() - u["y"].reindex(sy.index).to_numpy()).max() < 1e-9


def test_verified_mask_and_rate():
    d = _district(2)
    n = len(d.units)
    mask = np.zeros(n, bool)
    mask[:100] = True
    ev = build_events(d, verified=mask, verify_prob=0.75)
    uid = unit_table(d)["unit_id"].to_numpy()
    assert ev.loc[~ev["unit_id"].isin(uid[:100]), "q_ver"].isna().all()
    inside = ev.loc[ev["unit_id"].isin(uid[:100]), "q_ver"].notna().mean()
    assert 0.65 < inside < 0.85


def test_not_on_list_ids_are_unique_and_district_unchanged():
    d = _district()
    before = d.units["unit_id"].copy()
    assert unit_table(d)["unit_id"].is_unique       # synth cuts the NOL ids to 9 characters
    pd.testing.assert_series_equal(before, d.units["unit_id"])


def test_own_stream_and_reproducible():
    d = _district(3)
    a = build_events(d)
    b = build_events(d)
    pd.testing.assert_frame_equal(a, b)
    # the district is a function of pop_seed alone: building events must not change it
    d2 = _district(3)
    pd.testing.assert_frame_equal(d.units, d2.units)


def test_seed_count_rule():
    d = _district()
    ev = build_events(d)
    y = unit_table(d).set_index("unit_id")["y"]
    ratio = ev.groupby("unit_id")["seed_count"].first() / (y * 1000 / (0.5 * 0.8))
    assert abs(np.log(ratio).mean()) < 0.05      # lognormal noise has mean 1, so log-mean is -s^2/2
    assert ev.groupby("unit_id")["seed_count"].nunique().max() == 1
