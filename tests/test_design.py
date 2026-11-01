import numpy as np

from d32.config import BASE
from d32.design import build_design, certainty_units, dalenius_hodges_cuts, neyman_allocate
from d32.synth import make_district


def test_neyman_sums_and_proportionality():
    N = np.array([1000., 2000., 500.])
    S = np.array([1., 2., 4.])
    n, full, real = neyman_allocate(N, S, 100, 5)
    assert n.sum() == 100 and not full.any()
    # n_h proportional to N_h S_h = 1000 : 4000 : 2000
    assert np.allclose(real, 100 * np.array([1000, 4000, 2000]) / 7000)
    assert np.all(np.abs(n - real) <= 1)


def test_neyman_take_all_when_nh_exceeds_Nh():
    N = np.array([100., 50., 10.])
    S = np.array([1., 1., 100.])
    n, full, _ = neyman_allocate(N, S, 60, 5)
    assert full.tolist() == [False, False, True]
    assert n[2] == 10 and n.sum() == 60                    # stratum 3 fully enumerated
    assert n[0] + n[1] == 50 and n[0] > n[1]


def test_neyman_minimum_five():
    N = np.array([5000., 5000., 40.])
    S = np.array([1., 1., 0.01])
    n, _, real = neyman_allocate(N, S, 100, 5)
    assert real[2] < 5 and n[2] == 5 and n.sum() == 100


def test_certainty_units_and_cap():
    m = np.array([1000.] + [1.] * 99)
    ta = certainty_units(m, 10, cap=5)
    assert ta.tolist() == [True] + [False] * 99
    assert not certainty_units(m, 10, cap=0).any()
    flat = np.ones(100)
    assert not certainty_units(flat, 10, cap=5).any()
    two = np.array([1000., 900.] + [1.] * 98)
    assert certainty_units(two, 10, cap=1).sum() == 1      # cap binds


def test_dalenius_hodges_cuts_increasing():
    a = np.random.default_rng(0).lognormal(-2, 1, 5000)
    c = dalenius_hodges_cuts(a, 3, 500)
    assert len(c) == 2 and c[0] < c[1]


def test_build_design_on_synthetic_district():
    d = make_district(BASE)
    des = build_design(d.listed, BASE)
    assert des.strata["n_h"].sum() == BASE.n_per_district
    assert des.strata["N_h"].sum() == BASE.n_listed
    ok = des.strata[~des.strata.take_all]
    assert (ok.n_h >= BASE.n_min_stratum).all() and (ok.N_h >= BASE.min_frame_stratum).all()
    assert (des.unit_stratum >= 0).all()
    counts = np.bincount(des.unit_stratum)
    assert np.array_equal(counts, des.strata["N_h"].values)
