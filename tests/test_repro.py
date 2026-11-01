import hashlib

from d32.simulate import run


def _digest(df):
    return hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()


def test_same_seed_same_samples_and_estimates_AC7():
    a = run(3, ["S1", "S4"], 1, True)
    b = run(3, ["S1", "S4"], 1, True)
    assert _digest(a) == _digest(b)
    assert a["E3_se"].notna().all()


def test_parallel_equals_serial():
    a = run(4, ["S1"], 1, False)
    b = run(4, ["S1"], 2, False)
    assert _digest(a) == _digest(b)
