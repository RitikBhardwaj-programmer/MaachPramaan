"""Tests for the Fay-Herriot part of design.md v0.4 (sections 11, 21.4)."""
from dataclasses import replace

import numpy as np

from d32.config import BASE
from d32.fayherriot import benchmark, fay_herriot, gvf_smooth, shrink, sigma_v2
from d32.simulate import run
from d32.synth import make_district


def test_shrinkage_hand_example():
    theta, psi = np.array([1.0, 3.0]), np.array([1.0, 1.0])
    out = shrink(theta, psi, np.ones((2, 1)), 1.0)          # gamma = 1/(1+1) = 0.5; beta = mean = 2
    assert np.allclose(out["gamma"], 0.5) and np.allclose(out["beta"], [2.0])
    assert np.allclose(out["pred"], [1.5, 2.5])
    # g1 = gamma psi = 0.5 ; g2 = (1-gamma)^2 / sum(1/(s2+psi)) = 0.25 / 1 ; Var(s2) = 2/sum(v^-2) = 4 ; g3 = psi^2/v^3 * 4 = 0.5
    assert np.allclose(out["mse"], 0.5 + 0.25 + 2 * 0.5)


def _blocks(seed=0, m=10, s2=0.5):
    rng = np.random.default_rng(seed)
    X = np.column_stack([np.ones(m), rng.normal(size=m), rng.uniform(size=m)])
    psi = rng.uniform(0.2, 1.5, m)
    theta = X @ np.array([4.0, 0.5, 1.0]) + rng.normal(0, np.sqrt(s2), m) + rng.normal(0, np.sqrt(psi))
    return theta, psi, X


def test_gamma_strictly_between_zero_and_one():
    for seed in range(20):
        theta, psi, X = _blocks(seed)
        s2 = sigma_v2(theta, psi, X, adjusted=True)
        g = shrink(theta, psi, X, s2)["gamma"]
        assert s2 > 0 and np.all((g > 0) & (g < 1))


def test_adjusted_reml_positive_where_plain_reml_is_zero():
    rng = np.random.default_rng(3)
    m = 10
    X = np.column_stack([np.ones(m), rng.normal(size=m), rng.uniform(size=m)])
    psi = np.full(m, 2.0)
    theta = X @ np.array([1.0, 0.0, 0.0]) + rng.normal(0, 0.05, m)      # far less spread than psi says
    assert sigma_v2(theta, psi, X, adjusted=False) == 0.0
    assert sigma_v2(theta, psi, X, adjusted=True) > 0.0


def test_benchmark_is_exact():
    rng = np.random.default_rng(1)
    pred, area = rng.uniform(2, 6, 10), rng.uniform(50, 400, 10)
    bm = benchmark(pred, area, 12345.678)
    assert abs(np.sum(bm * area) - 12345.678) < 1e-9 * 12345.678


def test_fay_herriot_full_pipeline_benchmark_and_missing_block():
    theta, psi, X = _blocks(5)
    area = np.random.default_rng(2).uniform(80, 300, 10)
    n_b = np.arange(10) + 5
    theta[3], n_b[3] = np.nan, 0                                       # a block with no respondent
    r = fay_herriot(theta, psi, n_b, X, area, 9999.0)
    assert abs(np.sum(r["fh_bm"] * area) - 9999.0) < 1e-9 * 9999.0     # F3
    assert r["gamma"][3] == 0.0 and np.isfinite(r["fh"][3]) and r["mse"][3] > 0
    ok = r["valid"]
    assert np.all((r["gamma"][ok] > 0) & (r["gamma"][ok] < 1))


def test_gvf_smoothing_matches_mean_and_shrinks_noise():
    rng = np.random.default_rng(4)
    n = rng.integers(5, 40, 30).astype(float)
    theta = rng.uniform(3, 6, 30)
    psi = 4.0 / n * np.exp(rng.normal(0, 0.6, 30))
    sm = gvf_smooth(psi, n, theta)
    assert np.isclose(sm.mean(), psi.mean())
    assert np.var(np.log(sm)) < np.var(np.log(psi))
    assert np.array_equal(gvf_smooth(psi[:4], n[:4], theta[:4]), psi[:4])   # too few blocks: raw


def test_sigma_b_zero_leaves_population_unchanged_and_positive_changes_only_production():
    a, b = make_district(BASE), make_district(replace(BASE, sigma_b=0.0))
    assert a.units.equals(b.units)
    c = make_district(replace(BASE, sigma_b=0.15))
    for col in ("area", "assisted", "block", "dist_km", "cell", "z_prod", "n_events"):
        assert np.array_equal(a.units[col], c.units[col])
    assert not np.array_equal(a.units["y"], c.units["y"])
    m = c.units.groupby("block").apply(lambda d: d.y.sum() / d.area.sum())
    m0 = a.units.groupby("block").apply(lambda d: d.y.sum() / d.area.sum())
    assert m.std() > 1.5 * m0.std()                                   # the block effect is visible


def test_run_with_fayherriot_writes_block_table_and_benchmarks():
    df = run(2, ["S1"], 1, True, overrides={"n_boot": 30, "fayherriot": True, "sigma_b": 0.15})
    assert (df["fh_bench_err"] < 1e-9).all()
    b = df.attrs["fh_blocks"]
    assert len(b) == 2 * BASE.n_blocks and {"direct", "fh", "fh_bm", "gamma", "mse_pr", "truth"} <= set(b.columns)
    assert (b.loc[b.valid, "gamma"].between(0, 1, inclusive="neither")).all()
    off = run(2, ["S1"], 1, True, overrides={"n_boot": 30})
    assert "fh_bench_err" not in off.columns and "fh_blocks" not in off.attrs
