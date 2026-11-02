"""Tests for design.md v0.5 (section 22): F1 matched-event ratio, F2 dropout recall, F3 adaptive rate."""
from dataclasses import replace

import numpy as np
import pytest

from d32.config import BASE, SCENARIOS
from d32.estimate import CellSample, ListSample, dropout_recall_weights, e3_estimate
from d32.select import rep_streams
from d32.simulate import run, verify_probabilities
from d32.variance import adaptive_rate

EQUAL = replace(BASE, n_np_classes=1)      # one propensity class; no area below -> no calibration


def _cells():
    k = np.ones(3)
    return CellSample(np.zeros(3, int), np.array([3.0]), np.array([3.0]), k * 0.0, k, k * 0.0)


def _sample(resp, ver, x, y, r, xv=None, yv=None, rdrop=None, stratum=None):
    n = resp.size
    st = np.zeros(n, int) if stratum is None else stratum
    H = st.max() + 1
    Z = np.column_stack([np.ones(n), np.zeros(n), np.zeros(n), np.zeros(n)])
    return ListSample(st, np.full(H, float(n)), np.ones(n), resp, ver, x, y, r, Z, xv=xv, yv=yv, rdrop=rdrop)


# ---- F1 -------------------------------------------------------------------------------------------
X4 = np.array([10.0, 20.0, 30.0, 40.0])
R4 = np.array([8.0, 15.0, 25.0, 30.0])


def test_F1_matched_ratio_hand_example():
    resp = np.ones(4, bool)
    ver = np.array([True, True, False, False])
    xv = np.array([4.0, 20.0, 0.0, 0.0])        # unit 0: only 40% of its diary verified
    yv = np.array([5.0, 22.0, 0.0, 0.0])
    y_mixed = np.array([5.0 + 6.0, 22.0, np.nan, np.nan])   # what v0.4 would use: verified + diary remainder
    s = _sample(resp, ver, X4, y_mixed, R4, xv, yv)
    est = e3_estimate(s, s.w0, _cells(), _cells().cw, EQUAL)
    R = (5 + 22) / (4 + 20)                     # w2 is equal (= 2) on both verified units
    assert est["R"] == pytest.approx(R, rel=1e-12)
    assert est["Rrec"] == pytest.approx(R * (10 + 20) / (8 + 15), rel=1e-12)
    assert est["YL"] == pytest.approx(R * 100.0, rel=1e-12)
    old = e3_estimate(replace(s, xv=None, yv=None), s.w0, _cells(), _cells().cw, EQUAL)
    assert old["R"] == pytest.approx(33 / 30, rel=1e-12) and old["R"] < est["R"]   # v0.4 is pulled toward 1


def test_F1_equals_v04_ratio_when_all_events_verified():
    resp, ver = np.ones(4, bool), np.array([True, True, True, False])
    y = np.array([12.0, 21.0, 36.0, np.nan])
    s = _sample(resp, ver, X4, y, R4, np.where(ver, X4, 0.0), np.nan_to_num(y))
    new = e3_estimate(s, s.w0, _cells(), _cells().cw, EQUAL)
    old = e3_estimate(replace(s, xv=None, yv=None), s.w0, _cells(), _cells().cw, EQUAL)
    for k in ("R", "Rrec", "Y"):
        assert new[k] == pytest.approx(old[k], rel=1e-12)


# ---- F2 -------------------------------------------------------------------------------------------
def test_F2_double_sampling_weights_hand_example():
    stratum = np.array([0, 0, 0, 0, 1, 1, 1])
    resp = np.array([True, True, False, False, True, True, False])
    rdrop = np.array([False, False, True, False, False, False, False])
    w0 = np.array([1.0, 1.0, 1.0, 1.0, 2.0, 2.0, 2.0])
    w = dropout_recall_weights(w0, stratum, resp, rdrop, 2)
    # stratum 0: the one recall dropout stands for both dropouts; stratum 1: no recall dropout,
    # so its dropout's weight goes to the respondents (2 + 2 + 2) / (2 + 2)
    assert np.allclose(w, [1.0, 1.0, 2.0, 0.0, 3.0, 3.0, 0.0])
    assert w[stratum == 0].sum() == pytest.approx(4.0) and w[stratum == 1].sum() == pytest.approx(6.0)


def test_F2_total_hand_example():
    resp = np.array([True, True, True, False, False])
    ver = np.array([True, True, False, False, False])
    rdrop = np.array([False, False, False, True, False])
    x = np.array([10.0, 20.0, 30.0, np.nan, np.nan])
    y = np.array([12.0, 22.0, np.nan, np.nan, np.nan])
    r = np.array([8.0, 16.0, 20.0, 50.0, 60.0])
    s = _sample(resp, ver, x, y, r, rdrop=rdrop)
    est = e3_estimate(s, s.w0, _cells(), _cells().cw, EQUAL)
    R, Rrec = 34 / 30, 34 / 24                   # w2 = 1.5 on both verified units cancels
    assert est["R"] == pytest.approx(R, rel=1e-12) and est["Rrec"] == pytest.approx(Rrec, rel=1e-12)
    assert est["YD"] == pytest.approx(Rrec * 2 * 50.0, rel=1e-12)     # weight 2: stands for both dropouts
    assert est["YL"] == pytest.approx(R * 60.0 + Rrec * 100.0, rel=1e-12)


# ---- F3 -------------------------------------------------------------------------------------------
def _lv(n1=50, m=15, N=100.0, s2e=1.0, base=1000.0):
    t2 = N**2 * (1 / m - 1 / n1) * s2e
    return {"V": base + 2 * t2, "t2_h": np.array([t2, t2]), "n1_h": np.array([n1, n1], float),
            "s2e_h": np.array([s2e, s2e])}


class _S:                                   # two strata, 15 of 50 respondents verified in each
    N_h = np.array([100.0, 100.0])
    H = 2
    stratum = np.repeat([0, 1], 50)
    ver = np.tile(np.arange(50) < 15, 2)


EST = {"Y": 1000.0, "R": 1.2}


@pytest.mark.parametrize("target,nu", [(0.045, 0.30), (0.038, 0.50), (0.0355, 0.70), (0.030, 0.80)])
def test_F3_adaptive_rate_hand_example_full_top_up(target, nu):
    # q = 1: m'(nu) = 15, 20, 25, 30, 35, 40 of 50; predicted RSE = sqrt(1000 + 2*1e4*(1/m' - 1/50)) / 1000:
    # 0.0440, 0.0400, 0.0374, 0.0356, 0.0343, 0.0332
    assert adaptive_rate(_S(), EST, _lv(), BASE.nu_grid, 2, target, 1.2, 1.0) == nu


def test_F3_half_verified_top_up_needs_more_units():
    # q = 0.5, nu = 0.5: a = 10, m_eff = 20^2 / 17.5 = 22.86, RSE 0.0384 > 0.038; nu = 0.6: m_eff = 27.0, RSE 0.0366
    assert adaptive_rate(_S(), EST, _lv(), BASE.nu_grid, 2, 0.038, 1.2, 0.5) == 0.60


def test_F3_denominator_does_not_use_the_interim_ratio():
    # denominator Y * r_plan / R: doubling r_plan halves the predicted RSE (0.0440 -> 0.0220)
    assert adaptive_rate(_S(), EST, _lv(), BASE.nu_grid, 2, 0.030, 2.4, 1.0) == 0.30
    # a high interim R (and so a high Y) does not stop the top-up: denominator 2000 * 1.2 / 2.4 = 1000
    assert adaptive_rate(_S(), {"Y": 2000.0, "R": 2.4}, _lv(), BASE.nu_grid, 2, 0.038, 1.2, 1.0) == 0.50


def test_F1_lin_phase2_term_scaled_for_partial_verification():
    from d32.variance import lin_var_e3
    resp, ver = np.ones(6, bool), np.array([True, True, True, False, False, False])
    x = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0])
    xv, yv = np.array([5.0, 12.0, 15.0, 0, 0, 0]), np.array([6.0, 13.0, 18.0, 0, 0, 0])
    s = _sample(resp, ver, x, np.array([11.0, 21.0, 33.0, np.nan, np.nan, np.nan]), x * 0.8, xv, yv)
    est = e3_estimate(s, s.w0, _cells(), _cells().cw, EQUAL)
    R = 37 / 32
    e = yv[:3] - R * xv[:3]
    c = 210.0 / (2.0 * 32.0)                   # X / sum(w2 xv), w2 = 2
    want = 6.0**2 * (1 / 3 - 1 / 6) * np.var(e, ddof=1) * c**2
    assert lin_var_e3(s, est, _cells())["t2_h"][0] == pytest.approx(want, rel=1e-12)


def test_F2_calibration_uses_the_covered_set():
    resp = np.array([True, True, True, False, False])
    rdrop = np.array([False, False, False, True, False])
    area = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    s = replace(_sample(resp, np.array([True, True, False, False, False]), np.array([1.0, 2, 3, np.nan, np.nan]),
                        np.array([1.1, 2.2, np.nan, np.nan, np.nan]), area, rdrop=rdrop),
                area=area, A_h=np.array([15.0]))
    est = e3_estimate(s, s.w0, _cells(), _cells().cw, replace(EQUAL, cal_min_resp=2))
    cov = resp | rdrop
    assert est["w1"][cov].sum() == pytest.approx(5.0) and (est["w1"] * area)[cov].sum() == pytest.approx(15.0)
    assert est["w1"][~cov].sum() == 0.0


def test_top_up_unit_is_verified_only_after_mid_year():
    from d32.simulate import _verify_events
    rng = np.random.default_rng(5)
    full = np.mean([_verify_events(4, 1.0, rng) for _ in range(4000)])
    half = np.mean([_verify_events(4, 1.0, rng, 0.5) for _ in range(4000)])
    assert full == pytest.approx(1.0) and half == pytest.approx(0.5, abs=0.02)


def test_F3_requires_F1():
    with pytest.raises(ValueError):
        run(1, ["S1"], 1, False, overrides={"adaptive_phase2": True})


# ---- streams, stress scenarios, switches ----------------------------------------------------------
def test_nine_streams_leave_the_first_six_unchanged():
    a = rep_streams(9931, 7)
    b = rep_streams(9931, 7, k=9)
    for g, h in zip(a, b[:6]):
        assert np.array_equal(g.random(5), h.random(5))


def test_S5x_verification_mean_and_direction():
    eta = np.exp(np.random.default_rng(1).normal(0, 0.3, 500))
    p = verify_probabilities(eta, 0.75, 2.0)
    assert p.mean() == pytest.approx(0.75, abs=1e-9)
    assert np.corrcoef(np.log(eta), p)[0, 1] > 0.9          # under-reporting units are verified less


def test_stress_scenarios_defined():
    assert SCENARIOS["S4x"]["recall_drop_shift"] == -0.10 and SCENARIOS["S5x"]["verify_eta_slope"] == 2.0


def test_defaults_have_v05_features_off():
    assert not (BASE.matched_ratio or BASE.dropout_recall or BASE.adaptive_phase2)
    df = run(2, ["S1"], 1, False)
    assert not {"nu_final", "n_ver_topup", "n_drop_recall", "YD_hat"} & set(df.columns)


def test_F1_alone_changes_nothing_when_all_events_verified():
    off = run(3, ["S1"], 1, False)
    on = run(3, ["S1"], 1, False, overrides={"matched_ratio": True})
    assert np.allclose(off["E3_est"], on["E3_est"], rtol=1e-12, atol=0)
    assert np.array_equal(off["E1_est"], on["E1_est"])


def test_v05_run_adds_recall_and_top_up_consistently():
    ov = {"matched_ratio": True, "dropout_recall": True, "adaptive_phase2": True}
    off = run(3, ["S2"], 1, False)
    on = run(3, ["S2"], 1, False, overrides=ov)
    assert np.array_equal(off["n_resp"], on["n_resp"])                       # same samples
    assert (on["nu_final"] >= 0.30).all() and (on["n_ver"] == off["n_ver"] + on["n_ver_topup"]).all()
    assert (on["n_drop_recall"] <= on["n_drop"]).all() and (on["n_drop"] == on["n_sel"] - on["n_resp"]).all()
    assert (on["YD_hat"] > 0).all()
    assert np.allclose(on["E2_est"], off["E2_est"], rtol=1e-12)              # E2 keeps the old weights
