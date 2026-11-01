"""Tests for design.md v0.4 section 21.5: rotating panel and composite estimator (scenario S6)."""
import numpy as np

from d32.panel import (YEARS, composite_chain, draw_counts, estimate_K, estimate_K_chain, rw_factor, run,
                       shifted_prn, year_production)
from d32.select import prn_values, select_smallest
from d32.simulate import _base_ctx


def test_ideal_rotation_keeps_two_thirds_and_at_most_three_years():
    """With evenly spaced PRNs the rule of section 12 is exact: matched share 2/3, no unit in a 4th year."""
    N, n = 3000, 300
    prn = (np.arange(N) + 0.5) / N
    st, Nh, nh = np.zeros(N, int), np.array([N]), np.array([n])
    sels = [select_smallest(shifted_prn(prn, st, Nh, nh, t), st, nh) for t in range(8)]
    for a, b in zip(sels, sels[1:]):
        assert abs(np.intersect1d(a, b).size / n - 2 / 3) < 0.01
    run_len, mx = np.zeros(N, int), np.zeros(N, int)
    for s in sels:
        inn = np.zeros(N, bool)
        inn[s] = True
        run_len = np.where(inn, run_len + 1, 0)
        mx = np.maximum(mx, run_len)
    assert mx.max() <= 3


def test_simulated_rotation_matched_share_about_two_thirds():
    dist, design, *_ = _base_ctx()
    listed = dist.listed
    ta = np.isin(design.unit_stratum, np.where(design.strata["take_all"].values)[0])
    shares_all, shares_rot = [], []
    for rep in range(10):
        prn = prn_values(f"t/{rep}", listed["unit_id"].values)
        s = [select_smallest(shifted_prn(prn, design.unit_stratum, design.N_h, design.n_h, t),
                             design.unit_stratum, design.n_h) for t in range(YEARS)]
        for a, b in zip(s, s[1:]):
            c = np.intersect1d(a, b)
            shares_all.append(c.size / a.size)
            shares_rot.append((~ta[c]).sum() / (~ta[a]).sum())
            assert ta[a].sum() == ta[c].sum()                      # take-all units stay in every year
    assert 0.62 < np.mean(shares_rot) < 0.70                       # rotating strata only
    assert 0.63 < np.mean(shares_all) < 0.74                       # with the take-all units, which never leave


def test_composite_with_K_zero_is_direct_and_year_one_is_direct():
    rng = np.random.default_rng(0)
    Y, D = rng.normal(100, 10, (50, 3)), rng.normal(5, 3, (50, 2))
    assert np.array_equal(composite_chain(Y, D, [0.0, 0.0]), Y)
    C = composite_chain(Y, D, [0.4, 0.7])
    assert np.array_equal(C[:, 0], Y[:, 0])
    assert np.allclose(C[:, 1], 0.6 * Y[:, 1] + 0.4 * (Y[:, 0] + D[:, 0]))
    assert np.allclose(C[:, 2], 0.3 * Y[:, 2] + 0.7 * (C[:, 1] + D[:, 1]))


def test_estimate_K_hand_cases():
    rng = np.random.default_rng(1)
    a = rng.normal(0, 1, 5000)
    assert estimate_K(a, a.copy(), 0.8) == 0.0                     # b = a: nothing to gain
    b_exact = rng.normal(0, 0.01, 5000)                            # b almost noise-free, independent of a
    assert estimate_K(a, b_exact, 0.8) == 0.8                      # K* ~ 1, clipped
    b = rng.normal(0, 1, 5000)                                     # same variance, independent: K* = 1/2
    assert abs(estimate_K(a, b, 0.8) - 0.5) < 0.05
    assert estimate_K(a, a + 1.0 * 0 + 10, 0.8) == 0.0
    K = estimate_K_chain(np.column_stack([a, a, a]), np.zeros((5000, 2)), 0.8)
    assert K == [0.0, 0.0]


def test_bootstrap_counts_are_multinomial_and_shared_between_years():
    rng = np.random.default_rng(2)
    size, H = 60, 2
    stratum = np.repeat([0, 1], 30)
    s1 = np.concatenate([np.arange(0, 10), np.arange(30, 40)])
    s2 = np.concatenate([np.arange(3, 13), np.arange(33, 43)])     # 7 of 10 stay in each stratum
    N_h = np.array([30.0, 30.0])
    shared = []
    tot1 = np.zeros(2)
    for _ in range(4000):
        c1 = draw_counts(s1, None, None, stratum, H, rng, size)
        c2 = draw_counts(s2, s1, c1, stratum, H, rng, size)
        for h in range(2):
            assert c1[s1[stratum[s1] == h]].sum() == 9 and c2[s2[stratum[s2] == h]].sum() == 9
        common = np.intersect1d(s1, s2)
        assert np.array_equal(c1[common], c2[common])
        shared.append(c2[s2[:10]])
        tot1 += [c1[0], c2[12]]
    assert np.allclose(np.mean(shared, axis=0), 0.9, atol=0.05)    # each unit's mean count = (n-1)/n
    a = rw_factor(c2[s2], stratum[s2], N_h)
    assert a.shape == s2.shape and np.all(a >= 0)


def test_year_production_persistence_trend_and_year_one_marginal():
    dist, *_ = _base_ctx()
    from d32.config import BASE
    from dataclasses import replace
    y = year_production(dist, replace(BASE, rho_u=0.6))
    assert y.shape == (3, len(dist.units))
    u = dist.units
    base = u["prod"].values / np.exp(0.5 * u["z_prod"].values - 0.5**2 / 2)
    ly = np.log(y / u["area"].values / base)                       # unit-level noise part of log productivity
    r = np.corrcoef(ly[0], ly[1])[0, 1]
    assert 0.55 < r < 0.65                                         # its year-to-year correlation = rho_u
    assert 1.01 < y[1].sum() / y[0].sum() < 1.05 and 1.01 < y[2].sum() / y[1].sum() < 1.05   # about +3% a year
    y3 = year_production(dist, replace(BASE, rho_u=0.3))
    assert np.corrcoef(np.log(y3[0]), np.log(y3[1]))[0, 1] < np.corrcoef(np.log(y[0]), np.log(y[1]))[0, 1]


def test_run_year_one_composite_equals_direct_and_columns():
    df = run(2, 1, True, {"pop_seed": 1, "master_seed": 1, "n_boot": 12})
    y1 = df[df.year == 1]
    assert np.array_equal(y1["composite"], y1["direct"]) and (y1["K"] == 0).all()
    assert set(df.year) == {1, 2, 3} and df["K"].between(0, 0.8).all()
    nb = run(1, 1, False, {"pop_seed": 1, "master_seed": 1})
    assert np.allclose(nb["composite"], nb["direct"])              # no bootstrap -> K = 0
