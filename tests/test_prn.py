import numpy as np

from d32.select import prn_values, select_smallest, rep_streams, phase2_subsample


def test_prn_depends_only_on_seed_and_id():
    ids = [f"U{i:05d}" for i in range(1000)]
    base = prn_values("seed-1", ids)
    # add units before, between and after: the old units keep their PRNs
    more = ["X1"] + ids[:500] + ["X2", "X3"] + ids[500:] + ["Z9"]
    got = dict(zip(more, prn_values("seed-1", more)))
    assert all(got[i] == b for i, b in zip(ids, base))
    # shuffled order gives the same value per id
    perm = np.random.default_rng(0).permutation(len(ids))
    shuffled = prn_values("seed-1", [ids[j] for j in perm])
    assert np.array_equal(shuffled, base[perm])


def test_prn_range_and_seed_sensitivity():
    ids = [f"U{i}" for i in range(5000)]
    a, b = prn_values(1, ids), prn_values(2, ids)
    assert a.min() >= 0 and a.max() < 1
    assert not np.array_equal(a, b)
    assert abs(a.mean() - 0.5) < 0.02


def test_selection_unchanged_when_other_stratum_units_added():
    ids = np.array([f"U{i:04d}" for i in range(400)])
    strat = np.repeat([0, 1], 200)
    p = prn_values("s", ids)
    sel = select_smallest(p, strat, np.array([10, 10]))
    ids2 = np.concatenate([ids, [f"N{i}" for i in range(50)]])
    strat2 = np.concatenate([strat, np.ones(50, int)])
    p2 = prn_values("s", ids2)
    sel2 = select_smallest(p2, strat2, np.array([10, 10]))
    # stratum 0 untouched by additions to stratum 1
    assert set(ids[sel][sel < 200]) == set(ids2[sel2][sel2 < 200])


def test_select_sizes_and_sorted():
    p = np.random.default_rng(1).random(100)
    st = np.repeat([0, 1, 2], [50, 30, 20])
    sel = select_smallest(p, st, np.array([5, 30, 7]))
    assert len(sel) == 42 and np.all(np.diff(sel) > 0)
    assert (st[sel] == 1).sum() == 30


def test_rep_streams_independent_and_reproducible():
    a = [g.random(3) for g in rep_streams(7, 3)]
    b = [g.random(3) for g in rep_streams(7, 3)]
    assert all(np.array_equal(x, y) for x, y in zip(a, b))
    assert len({tuple(x) for x in a}) == len(a)       # purposes never share a stream
    assert not np.array_equal(a[0], rep_streams(7, 4)[0].random(3))


def test_phase2_subsample_counts():
    st = np.repeat([0, 1], [20, 5])
    resp = np.ones(25, bool)
    ver = phase2_subsample(st, resp, 2, 0.3, 2, np.random.default_rng(0))
    assert ver[st == 0].sum() == 6 and ver[st == 1].sum() == 2
    assert not (ver & ~resp).any()
