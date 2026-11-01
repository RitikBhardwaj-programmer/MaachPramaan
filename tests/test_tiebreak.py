"""design.md 20.1: equal predicted propensities must not make the classes depend on row order."""
import numpy as np

from d32 import nonresponse as NR


def _tied_sample():
    n = 20
    Z = np.tile([1.0, 0.5, 1.0, 0.3], (n, 1))             # identical covariates: every propensity ties
    resp = np.array([int(c) for c in "11110010100101010111"], bool)
    w0 = np.full(n, 5.0)
    key = np.random.default_rng(3).random(n)               # stands in for the unit PRN
    return w0, resp, Z, key


def _run(perm, w0, resp, Z, key, use_key):
    out = NR.nonresponse_weights(w0[perm], resp[perm], Z[perm], 5, 1e9, 1e-6, key[perm] if use_key else None)
    back = np.empty(perm.size, int)
    back[perm] = np.arange(perm.size)                      # put results back in the original unit order
    return out[1][back], out[0][back]


def test_tie_break_key_makes_classes_independent_of_row_order():
    w0, resp, Z, key = _tied_sample()
    ident = np.arange(w0.size)
    cls0, w_0 = _run(ident, w0, resp, Z, key, True)
    for seed in range(5):
        perm = np.random.default_rng(seed).permutation(w0.size)
        cls1, w_1 = _run(perm, w0, resp, Z, key, True)
        assert np.array_equal(cls0, cls1)
        assert np.allclose(w_0, w_1)


def test_without_key_ties_follow_row_order():
    """Documents the old behaviour for callers that have no unit IDs, and shows the test above has power."""
    w0, resp, Z, key = _tied_sample()
    cls0, _ = _run(np.arange(w0.size), w0, resp, Z, key, False)
    differs = any(
        not np.array_equal(cls0, _run(np.random.default_rng(s).permutation(w0.size), w0, resp, Z, key, False)[0])
        for s in range(5))
    assert differs
