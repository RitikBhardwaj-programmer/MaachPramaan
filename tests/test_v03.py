"""Tests for the design.md v0.3 calibration change (section 19)."""
from dataclasses import replace

import numpy as np

from d32.config import BASE
from d32.estimate import calibrate, calibrate_detail
from d32.simulate import run

V02 = replace(BASE, cal_min_resp=4, cal_fallback=False)         # the v0.2 rule


def _stratum(n, seed=0, area_factor=1.0):
    """One stratum of n respondents, N = 100 frame units, A_h a bit off the weighted sample area."""
    rng = np.random.default_rng(seed)
    area = rng.lognormal(-1.5, 0.5, n)
    w = np.full(n, 100.0 / n) * rng.uniform(0.9, 1.1, n)
    A_h = (w * area).sum() * 1.05 * area_factor
    return np.zeros(n, int), w, area, np.array([100.0]), np.array([A_h]), np.ones(n, bool)


def test_defaults_are_v03():
    assert BASE.cal_min_resp == 8 and BASE.cal_fallback is True


def test_threshold_eight_respondents():
    for n, both in ((7, False), (8, True)):
        st, w, a, N, A, resp = _stratum(n)
        g, info = calibrate_detail(w, st, a, N, A, resp, BASE)
        assert np.isclose((w * g).sum(), N[0])
        assert np.isclose((w * g * a).sum(), A[0]) == both
        assert info["miss_before"] == [] and info["unmet_after"] == []


def test_v02_threshold_four_attempts_both_constraints():
    st, w, a, N, A, resp = _stratum(5)
    g, info = calibrate_detail(w, st, a, N, A, resp, V02)
    assert np.isclose((w * g * a).sum(), A[0])                  # 5 >= 4: area attempted under v0.2


def test_fallback_to_counts_when_area_unreachable():
    st, w, a, N, A, resp = _stratum(12, area_factor=8.0)         # A_h cannot be reached with g <= 3
    g, info = calibrate_detail(w, st, a, N, A, resp, BASE)
    assert info["miss_before"] == [0] and info["fallback"] == [0] and info["unmet_after"] == []
    assert np.isclose((w * g).sum(), N[0])                       # N_h now holds
    assert g.min() >= BASE.cal_g_lo - 1e-12 and g.max() <= BASE.cal_g_hi + 1e-12
    assert np.allclose(g, g[0])                                  # N-only calibration: one common factor
    assert calibrate(w, st, a, N, A, resp, BASE)[1] == []


def test_v02_rule_keeps_truncated_factors_without_fallback():
    st, w, a, N, A, resp = _stratum(12, area_factor=8.0)
    g, info = calibrate_detail(w, st, a, N, A, resp, V02)
    assert info["miss_before"] == [0] and info["fallback"] == [] and info["unmet_after"] == [0]
    assert not np.isclose((w * g).sum(), N[0]) or not np.isclose((w * g * a).sum(), A[0])


def test_fallback_that_also_fails_is_still_logged():
    st, w, a, N, A, resp = _stratum(12, area_factor=8.0)
    N = np.array([1000.0])                                       # even N_h alone needs g ~ 8 > 3
    g, info = calibrate_detail(w, st, a, N, A, resp, BASE)
    assert info["fallback"] == [0] and info["unmet_after"] == [0]
    assert g.max() <= BASE.cal_g_hi + 1e-12


def test_zero_respondent_stratum_recorded_not_counted_as_unmet():
    st, w, a, N, A, resp = _stratum(10)
    g, info = calibrate_detail(w, st, a, N, A, np.zeros(10, bool), BASE)
    assert info["zero_resp"] == [0] and info["miss_before"] == [0] and info["unmet_after"] == []
    assert np.all(g == 1.0)


def test_run_overrides_change_seeds_and_rule_on_same_samples():
    a = run(3, ["S1"], 1, False)
    b = run(3, ["S1"], 1, False, overrides={"cal_min_resp": 4, "cal_fallback": False})
    c = run(3, ["S1"], 1, False, overrides={"pop_seed": 20261103, "master_seed": 5521})
    for col in ("truth", "E1_est", "n_resp", "n_ver"):            # same samples, only calibration differs
        assert np.array_equal(a[col], b[col])
    assert a["truth"].iloc[0] != c["truth"].iloc[0]               # new seeds give a new district
    for col in ("cal_failed", "cal_fallback", "cal_unmet_after", "cal_at_bound"):
        assert col in a.columns
