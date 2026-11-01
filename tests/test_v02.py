"""Tests for the design.md v0.2 changes (section 18)."""
import inspect
from dataclasses import replace

import numpy as np

from d32.config import BASE
from d32 import nonresponse as NR
from d32.design import build_design, take_all_units
from d32.estimate import CellSample, ListSample, calibrate, kish_deff, kish_deff_factors
from d32.synth import make_district
from d32.variance import bootstrap_e3, rao_wu


# ---- calibration (section 9 step 5) -------------------------------------------------------------
def _two_strata(seed=0):
    rng = np.random.default_rng(seed)
    n_h = np.array([30, 20])
    N_h = np.array([600., 400.])
    stratum = np.repeat([0, 1], n_h)
    area = np.concatenate([rng.lognormal(-1.8, 0.6, 30), rng.lognormal(-1.0, 0.6, 20)])
    w = (N_h / n_h)[stratum] * rng.uniform(0.9, 1.3, 50)       # unequal adjustment factors
    # frame area totals a bit different from the weighted sample totals
    A_h = np.array([(w[stratum == 0] * area[stratum == 0]).sum() * 1.03,
                    (w[stratum == 1] * area[stratum == 1]).sum() * 0.97])
    return stratum, w, area, N_h, A_h


def test_calibration_reproduces_frame_counts_and_area():
    stratum, w, area, N_h, A_h = _two_strata()
    resp = np.ones(50, bool)
    g, failed = calibrate(w, stratum, area, N_h, A_h, resp, BASE)
    assert failed == []
    for h in range(2):
        m = stratum == h
        assert np.isclose((w * g)[m].sum(), N_h[h])
        assert np.isclose((w * g * area)[m].sum(), A_h[h])
    assert g.min() >= BASE.cal_g_lo - 1e-12 and g.max() <= BASE.cal_g_hi + 1e-12


def test_calibration_respects_bounds_and_logs_failure():
    stratum, w, area, N_h, A_h = _two_strata()
    resp = np.ones(50, bool)
    A_bad = A_h * np.array([8.0, 1.0])                          # unreachable with g <= 3
    # v0.2 rule (no N_h-only fallback); the v0.3 fallback is tested in test_v03.py
    g, failed = calibrate(w, stratum, area, N_h, A_bad, resp, replace(BASE, cal_min_resp=4, cal_fallback=False))
    assert failed == [0]
    assert g.min() >= BASE.cal_g_lo - 1e-12 and g.max() <= BASE.cal_g_hi + 1e-12


def test_calibration_small_stratum_uses_counts_only():
    stratum, w, area, N_h, A_h = _two_strata()
    resp = np.ones(50, bool)
    resp[:30] = False
    resp[:3] = True                                             # 3 respondents in stratum 0 (< 4)
    w_adj = np.where(stratum == 0, w * 10.0, w) * resp          # nonresponse adjustment: 30 selected, 3 respond
    g, failed = calibrate(w_adj, stratum, area, N_h, A_h, resp, BASE)
    m = resp & (stratum == 0)
    assert failed == [] or failed == [1]                        # stratum 0 is fine
    assert np.isclose((w_adj * g)[m].sum(), N_h[0])             # count constraint holds
    assert not np.isclose((w_adj * g * area)[m].sum(), A_h[0])  # area is not calibrated here
    assert np.allclose(g[m], g[m][0])                           # one common factor


def test_calibration_stratum_without_respondents_is_logged():
    stratum, w, area, N_h, A_h = _two_strata()
    resp = stratum == 1
    g, failed = calibrate(w * resp, stratum, area, N_h, A_h, resp, BASE)
    assert failed == [0]


# ---- take-all (section 4.4) ---------------------------------------------------------------------
def test_take_all_rule_small_frame():
    area = np.array([3.0, 0.1, 2.5, 2.0, 1.99, 0.2, 5.0, 0.3, 0.1, 0.1])
    ta = take_all_units(area, 20, 2.0, 0.10)                    # cap = floor(0.1 * 20) = 2
    assert set(np.where(ta)[0]) == {6, 0}                       # the two largest of the four >= 2 ha
    ta = take_all_units(area, 40, 2.0, 0.10)                    # cap 4 -> all four units >= 2 ha
    assert set(np.where(ta)[0]) == {0, 2, 3, 6}
    assert not take_all_units(np.array([1.9, 0.5, 1.99]), 200, 2.0, 0.1).any()   # none reach 2 ha


def test_take_all_inside_design_total():
    d = make_district(BASE)
    des = build_design(d.listed, BASE)
    ta = des.strata[des.strata.take_all & (des.strata.kind == "take_all_units")]
    assert len(ta) == 1
    n_ta = int(ta.n_h.iloc[0])
    assert 0 < n_ta <= int(np.floor(0.1 * BASE.n_per_district))
    assert des.strata["n_h"].sum() == BASE.n_per_district       # take-all counted inside n
    a = d.listed["area"].values[des.unit_stratum == ta.index[0]]
    assert (a >= BASE.take_all_min_area_ha).all()
    assert a.size == n_ta


def test_rao_wu_take_all_stratum_has_zero_variance():
    rng = np.random.default_rng(1)
    stratum = np.repeat([0, 1], [20, 10])
    N_h = np.array([400., 10.])                                 # stratum 1 is fully enumerated
    w = (N_h / np.array([20, 10]))[stratum]
    draws = np.array([rao_wu(w, stratum, N_h, rng)[stratum == 1] for _ in range(200)])
    assert np.allclose(draws, w[stratum == 1])
    sampled = np.array([rao_wu(w, stratum, N_h, rng)[stratum == 0] for _ in range(200)])
    assert sampled.std(axis=0).min() > 0                        # the sampled stratum does vary


def test_bootstrap_of_all_take_all_design_is_degenerate():
    n = 12
    stratum = np.zeros(n, int)
    N_h, A_h = np.array([float(n)]), np.array([6.0])
    area = np.full(n, 0.5)
    rng = np.random.default_rng(2)
    x = rng.uniform(1, 2, n)
    ver = np.zeros(n, bool)
    ver[:4] = True
    y = np.where(ver, x * 1.1, np.nan)
    Z = np.column_stack([np.ones(n), np.log(area), np.zeros(n), rng.uniform(0, 1, n)])
    s = ListSample(stratum, N_h, np.ones(n), np.ones(n, bool), ver, x, y, 0.8 * x, Z, area, A_h)
    cells = CellSample(np.zeros(3, int), np.array([3.0]), np.array([3.0]), np.array([1., 2., 3.]), np.ones(3))
    out = bootstrap_e3(s, cells, BASE, rng)
    assert out.size == BASE.n_boot and np.nanstd(out) < 1e-9


# ---- propensity model (section 9 step 1) --------------------------------------------------------
def test_propensity_model_is_unweighted_and_three_variable():
    assert "w" not in inspect.signature(NR.propensity_scores).parameters
    rng = np.random.default_rng(5)
    n = 200
    Z = np.column_stack([np.ones(n), rng.normal(size=n), rng.integers(0, 2, n), rng.uniform(0, 2, n)])
    resp = rng.random(n) < 0.85
    phat = NR.propensity_scores(Z, resp, 1e-6)
    for scale in (1.0, 50.0):                                   # design weights must not move the ranking
        w0 = scale * rng.uniform(1, 300, n)
        _, cls, _ = NR.nonresponse_weights(w0, resp, Z, 5, 1e9, 1e-6)
        assert np.array_equal(cls, NR.propensity_classes(phat, 5))


def test_simulation_propensity_covariates_are_exactly_three():
    from d32.simulate import _base_ctx
    Z = _base_ctx()[2]
    assert Z.shape[1] == 4                                      # intercept + log area + assisted + distance
    assert np.all(Z[:, 0] == 1.0)


# ---- design effects (section 8.9) ---------------------------------------------------------------
def test_kish_factor_form_ignores_between_stratum_weight_differences():
    stratum = np.repeat([0, 1], 10)
    f = np.ones(20)
    w = np.where(stratum == 0, 1.0, 50.0)                       # Neyman-style unequal design weights
    assert kish_deff(w) > 1.5                                   # form (a) counts them
    assert np.isclose(kish_deff_factors(f, stratum, np.ones(20, bool)), 1.0)   # form (b) does not
