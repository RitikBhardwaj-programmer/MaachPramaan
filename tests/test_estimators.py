import numpy as np
import statsmodels.api as sm
from hypothesis import given, settings, strategies as st

from d32.config import BASE
from d32.estimate import (CellSample, ListSample, design_weights, e3_estimate, kish_deff, phase2_weights,
                          ratio_total)
from d32.nonresponse import class_adjustment, fit_logit
from d32.variance import lin_var_e3, rao_wu


def tiny():
    # one stratum, N=10, n=4 all respond, first two verified
    stratum = np.zeros(4, int)
    N_h = np.array([10.])
    w0 = design_weights(stratum, N_h, np.array([4.]))
    resp = np.ones(4, bool)
    ver = np.array([True, True, False, False])
    x = np.array([10., 20., 30., 40.])
    y = np.array([12., 25., np.nan, np.nan])
    r = np.array([9., 18., 27., 36.])
    return stratum, N_h, w0, resp, ver, x, y, r


def test_ratio_estimator_hand_computed():
    stratum, N_h, w0, resp, ver, x, y, r = tiny()
    assert np.allclose(w0, 2.5)
    w1 = w0.copy()
    w2 = phase2_weights(w0, w1, stratum, resp, ver, 1)
    assert np.allclose(w2[ver], 5.0)                       # 2.5 * 4/2
    X, R, Rrec = ratio_total(w1, w2, x, y, r, resp, ver)
    assert X == 250.0                                      # 2.5 * (10+20+30+40)
    assert np.isclose(R, 37 / 30)                          # (5*37)/(5*30)
    assert np.isclose(R * X, 308.3333333333333)
    assert np.isclose(Rrec, 37 / 27)                       # (5*37)/(5*27)


def test_linearised_variance_hand_computed():
    stratum, N_h, w0, resp, ver, x, y, r = tiny()
    s = ListSample(stratum, N_h, w0, resp, ver, x, y, r, np.ones((4, 1)))
    w2 = phase2_weights(w0, w0, stratum, resp, ver, 1)
    X, R, Rrec = ratio_total(w0, w2, x, y, r, resp, ver)
    cells = CellSample(np.zeros(2, int), np.array([10.]), np.array([2.]), np.zeros(2), np.zeros(2))
    v = lin_var_e3(s, {"R": R, "Rrec": Rrec, "H": 0.0, "w2": w2}, cells)
    # s2_y = 84.5 ; e = (-1/3, +1/3) -> s2_e = 2/9
    # V = 100*(1/4-1/10)*84.5 + 100*(1/2-1/4)*(2/9) = 1267.5 + 5.5556
    assert np.isclose(v["V_L"], 1267.5 + 100 * 0.25 * 2 / 9)
    assert v["df"] == 1


def test_e3_end_to_end_no_nonresponse_equals_ratio():
    stratum, N_h, w0, resp, ver, x, y, r = tiny()
    Z = np.column_stack([np.ones(4), np.array([0., 1., 0., 1.])])
    s = ListSample(stratum, N_h, w0, resp, ver, x, y, r, Z)
    cells = CellSample(np.zeros(2, int), np.array([10.]), np.array([2.]), np.array([3., 5.]), np.array([1., 2.]))
    e = e3_estimate(s, w0, cells, cells.cw, BASE)
    assert np.isclose(e["YL"], 308.3333333333333)          # phi = 1 when everybody responds
    assert np.isclose(e["YNL"], e["Rrec"] * 5 * 8)         # cw = 10/2 = 5 ; sum z = 8


@settings(max_examples=200, deadline=None)
@given(st.lists(st.tuples(st.integers(1, 5000), st.floats(0.01, 1.0)), min_size=1, max_size=12))
def test_design_weights_sum_to_N_per_stratum(spec):
    N_h = np.array([a for a, _ in spec], float)
    n_h = np.maximum(1, np.minimum(N_h, np.round(N_h * np.array([b for _, b in spec])))).astype(float)
    stratum = np.repeat(np.arange(len(spec)), n_h.astype(int))
    w0 = design_weights(stratum, N_h, n_h)
    assert np.allclose(np.bincount(stratum, weights=w0, minlength=len(spec)), N_h)


@settings(max_examples=200, deadline=None)
@given(st.integers(0, 10**6), st.integers(2, 6), st.integers(1, 6))
def test_nonresponse_and_phase2_weights_preserve_totals(seed, H, k):
    rng = np.random.default_rng(seed)
    n_h = rng.integers(4, 30, H)
    N_h = n_h * rng.integers(2, 50, H).astype(float)
    stratum = np.repeat(np.arange(H), n_h)
    n = stratum.size
    w0 = design_weights(stratum, N_h, n_h.astype(float))
    resp = rng.random(n) < 0.8
    resp[np.arange(0, n, 7)] = True
    cls = rng.integers(0, k, n)
    phi, cls2 = class_adjustment(w0, resp, cls, cap=1e9)
    w1 = np.where(resp, w0 * phi, 0.0)
    # sum of nonresponse-adjusted weights = N (every class has a respondent when cap is off)
    ok = all(resp[cls2 == c].any() for c in np.unique(cls2))
    if ok:
        assert np.isclose(w1.sum(), N_h.sum())
    ver = np.zeros(n, bool)
    for h in range(H):
        idx = np.where((stratum == h) & resp)[0]
        if idx.size:
            ver[rng.choice(idx, size=max(1, idx.size // 3), replace=False)] = True
    w2 = phase2_weights(w0, w1, stratum, resp, ver, H)
    for h in range(H):
        m = stratum == h
        if ver[m].any():
            # design.md 8.2: w2 = w1 * n'_h / m_h exactly (w0 is constant inside a stratum)
            ratio = (m & resp).sum() / (m & ver).sum()
            assert np.allclose(w2[m & ver], w1[m & ver] * ratio)


def test_class_adjustment_merges_when_phi_above_cap():
    w0 = np.ones(10)
    resp = np.array([1, 1, 1, 1, 1, 1, 0, 0, 0, 1], bool)
    cls = np.array([0, 0, 1, 1, 2, 2, 3, 3, 3, 3])          # class 3 has 1 respondent of 4 -> phi 4
    phi, cls2 = class_adjustment(w0, resp, cls, cap=2.0)
    assert phi.max() <= 2.0 and np.unique(cls2).size < 4


def test_rao_wu_preserves_expected_weight_total():
    rng = np.random.default_rng(0)
    N_h = np.array([1000., 500.])
    stratum = np.repeat([0, 1], [20, 10])
    w = (N_h / np.array([20, 10]))[stratum]
    tot = np.mean([rao_wu(w, stratum, N_h, rng).sum() for _ in range(2000)])
    assert np.isclose(tot, w.sum(), rtol=0.01)
    full = rao_wu(w, stratum, np.array([20., 10.]), rng)    # f = 1 (take-all): weights unchanged
    assert np.allclose(full, w)


def test_logit_matches_statsmodels():
    rng = np.random.default_rng(3)
    Z = np.column_stack([np.ones(500), rng.normal(size=(500, 3))])
    p = 1 / (1 + np.exp(-(Z @ np.array([0.5, 1., -0.5, 0.2]))))
    yv = rng.random(500) < p
    mine = fit_logit(Z, yv, np.ones(500), ridge=0.0)
    ref = sm.Logit(yv.astype(float), Z).fit(disp=0).params
    assert np.allclose(mine, ref, atol=1e-5)


def test_kish_deff():
    assert np.isclose(kish_deff(np.ones(10)), 1.0)
    assert kish_deff(np.array([1., 1., 1., 5.])) > 1.0
