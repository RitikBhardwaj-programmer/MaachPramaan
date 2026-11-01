"""Tests for design.md v0.4 sections 21.1 (take-all phase-2 variance) and 21.2 (productivity)."""
from dataclasses import replace

import numpy as np

from d32.config import BASE
from d32.estimate import CellSample, ListSample, e3_estimate
from d32.simulate import run
from d32.variance import bootstrap_e3, lin_var_p, takeall_phase2_mult, takeall_strata

N_UNITS, N_RESP, N_VER = 40, 30, 8


def _ta_sample(n_ver=N_VER, n_resp=N_RESP, seed=3, with_area=False):
    """One take-all stratum (f_h = 1): all N_UNITS selected, n_resp respond, n_ver verified."""
    rng = np.random.default_rng(seed)
    n = N_UNITS
    area = rng.lognormal(-1.0, 0.5, n)
    resp = np.zeros(n, bool)
    resp[:n_resp] = True
    ver = np.zeros(n, bool)
    ver[:n_ver] = True
    x = np.where(resp, rng.lognormal(0.5, 0.4, n), np.nan)
    y = np.where(ver, x * rng.lognormal(0.1, 0.25, n), np.nan)
    Z = np.column_stack([np.ones(n), np.log(area), rng.integers(0, 2, n), rng.uniform(0, 1, n)])
    N_h, A_h = np.array([float(n)]), np.array([area.sum()])
    # no area -> no calibration (with_area=True adds it); with n_np_classes = 1 (EQUAL below) all phase-2 weights are N_h / m_h
    return ListSample(np.zeros(n, int), N_h, np.ones(n), resp, ver, x, y, 0.8 * np.nan_to_num(x), Z,
                      *((area, A_h) if with_area else ()))


EQUAL = replace(BASE, n_np_classes=1)


def _cells(z=0.0, za=0.0):
    k = np.full(3, 1.0)
    return CellSample(np.zeros(3, int), np.array([3.0]), np.array([3.0]), k * z, k, k * za)


def _hand_phase2_variance(s):
    """N_h^2 (1/m - 1/n') s_e^2 with e = y - R x, R from the point estimate (design.md 8.6, 21.1)."""
    est = e3_estimate(s, s.w0, _cells(), _cells().cw, EQUAL)
    v = s.ver
    e = s.y[v] - est["R"] * s.x[v]
    m, n1 = int(v.sum()), int(s.resp.sum())
    return float(s.N_h[0] ** 2 * (1 / m - 1 / n1) * np.var(e, ddof=1)), est


def test_T1_phase2_term_matches_hand_formula():
    s = _ta_sample()
    target, est = _hand_phase2_variance(s)
    use, skipped = takeall_strata(s)
    assert use == [0] and skipped == []
    rng = np.random.default_rng(11)
    v = s.ver
    e = s.y[v] - est["R"] * s.x[v]
    w2 = est["w2"][v]
    contrib = [np.sum((w2 * takeall_phase2_mult(s, use, rng)[v]) * e) for _ in range(60000)]
    assert abs(np.var(contrib, ddof=1) / target - 1) < 0.02


def test_T1_through_bootstrap_total():
    """With phase 1 fixed (f = 1) and no area-frame term, all bootstrap variance is the phase-2 term."""
    s = _ta_sample()
    target, est = _hand_phase2_variance(s)
    v = s.ver
    target *= (est["X"] / np.sum(est["w2"][v] * s.x[v])) ** 2      # Y = R X: delta method, d Y = (X / sum w2 x) d(sum w2 e)
    cfg = replace(EQUAL, n_boot=3000, takeall_phase2=True)
    out = bootstrap_e3(s, _cells(), cfg, np.random.default_rng(1), np.random.default_rng(2))
    assert abs(np.nanvar(out, ddof=1) / target - 1) < 0.06          # R is a ratio: looser than the 2% check above
    off = bootstrap_e3(s, _cells(), replace(cfg, takeall_phase2=False, n_boot=50), np.random.default_rng(1))
    assert np.nanstd(off) < 1e-9                                    # the v0.3 bootstrap adds nothing here


def test_T2_all_verified_adds_no_term():
    s = _ta_sample(n_ver=N_RESP)
    assert takeall_strata(s) == ([], [])
    cfg = replace(BASE, n_boot=50, takeall_phase2=True)
    out = bootstrap_e3(s, _cells(), cfg, np.random.default_rng(1), np.random.default_rng(2))
    assert np.nanstd(out) < 1e-9


def test_fewer_than_two_verified_is_recorded_not_resampled():
    s = _ta_sample(n_ver=1)
    assert takeall_strata(s) == ([], [0])
    cfg = replace(BASE, n_boot=20, takeall_phase2=True)
    out = bootstrap_e3(s, _cells(), cfg, np.random.default_rng(1), np.random.default_rng(2), full=True)
    assert out["ta_skipped"] == [0] and np.nanstd(out["Y"]) < 1e-9


def test_sampled_stratum_is_not_treated_as_take_all():
    s = _ta_sample()
    s.N_h = np.array([400.0])                                       # 40 of 400 selected: f = 0.1
    assert takeall_strata(s) == ([], [])


# ---- 21.2 productivity ---------------------------------------------------------------------------
def test_not_on_list_area_and_productivity_hand_example():
    s = _ta_sample(with_area=True)
    cs = CellSample(np.zeros(2, int), np.array([10.0]), np.array([2.0]), np.array([4.0, 6.0]),
                    np.array([1.0, 2.0]), np.array([1.0, 3.0]))
    est = e3_estimate(s, s.w0, cs, cs.cw, BASE)
    assert np.isclose(est["A_nl"], 5.0 * (1.0 + 3.0))               # C/c = 5 times the sampled NL area
    assert np.isclose(est["A"], s.A_h.sum() + 20.0)
    assert np.isclose(est["P"], est["Y"] / est["A"])
    no_area = CellSample(cs.gstratum, cs.C_g, cs.c_g, cs.z, cs.n_nol)
    assert "P" not in e3_estimate(s, s.w0, no_area, no_area.cw, BASE)


def test_lin_var_p_matches_hand_formula():
    s = _ta_sample(with_area=True)
    cs = CellSample(np.zeros(4, int), np.array([20.0]), np.array([4.0]), np.array([4., 6., 5., 9.]),
                    np.ones(4), np.array([1., 3., 2., 2.5]))
    est = e3_estimate(s, s.w0, cs, cs.cw, BASE)
    V_Y = 7.0
    fac = 20.0**2 * (1 - 4 / 20) / 4
    V_A = fac * np.var(cs.za, ddof=1)
    C = fac * np.cov(cs.z, cs.za, ddof=1)[0, 1]
    want = (V_Y + est["P"] ** 2 * V_A - 2 * est["P"] * est["Rrec"] * C) / est["A"] ** 2
    assert np.isclose(lin_var_p(s, est, cs, V_Y), want)


def test_bootstrap_returns_P_with_area_replicates():
    s = _ta_sample(with_area=True)
    cs = CellSample(np.zeros(4, int), np.array([20.0]), np.array([4.0]), np.array([4., 6., 5., 9.]),
                    np.ones(4), np.array([1., 3., 2., 2.5]))
    cfg = replace(BASE, n_boot=30, productivity=True)
    out = bootstrap_e3(s, cs, cfg, np.random.default_rng(1), full=True)
    assert np.allclose(out["P"], out["Y"] / out["A"])
    assert np.nanstd(out["A"]) > 0                                  # 4 of 20 cells: A* varies


# ---- Z0: switches off = v0.3 columns --------------------------------------------------------------
def test_defaults_have_v04_features_off():
    assert BASE.takeall_phase2 is False and BASE.productivity is False
    df = run(2, ["S1"], 1, False)
    assert not any(c.startswith(("P_", "Plin_", "A_hat", "ta_phase2")) for c in df.columns)


def test_v04_switches_add_columns_only():
    off = run(2, ["S1"], 1, True, overrides={"n_boot": 20})
    on = run(2, ["S1"], 1, True, overrides={"n_boot": 20, "takeall_phase2": True, "productivity": True})
    for c in ("truth", "E1_est", "E3_est", "n_resp", "n_ver", "R_hat"):        # same samples, same point estimates
        assert np.array_equal(off[c], on[c])
    new = {"P_truth", "A_hat", "P_est", "Plin_se", "Plin_lo", "Plin_hi", "P_se", "P_lo", "P_hi", "ta_phase2_skipped"}
    assert new <= set(on.columns) and not new & set(off.columns)
    assert np.allclose(on["P_est"], on["E3_est"] / on["A_hat"])
    assert (on["A_hat"] > 0).all() and (on["P_se"] > 0).all()
