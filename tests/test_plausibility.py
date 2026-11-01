"""Plausibility tests (design.md section 10 and 21.3: C1, C2, C4, C5). SIMULATED data.

C1, C2, C5 use 20 replications of a small district (pop_seed 1..20). The full 200-replication
run on the part A seeds is done separately; no run seed is used here.
"""
import hashlib
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from d32.config import BASE
from d32.events import build_events, unit_table
from d32.plausibility import CHECKS, FLAG_COLUMNS, X10_LOG_LR_CUT, inject_faults, run_checks, x10_log_lr
from d32.synth import eta_cv, lognormal_noise, make_district

REPS = 20
SMALL = dict(n_listed=800, n_not_on_list=60, n_cells=60)


def _hash(df: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=True).to_numpy().tobytes()).hexdigest()


def _rep(i: int) -> dict:
    cfg = replace(BASE, pop_seed=i + 1, **SMALL)
    d = make_district(cfg)
    u = unit_table(d)
    y = u["y"].to_numpy()
    rng = np.random.default_rng(1000 + i)
    cv = eta_cv(y, d.calib_group, cfg.rho_diary)
    x = y * np.exp(cfg.beta_diary_assisted) * lognormal_noise(rng.standard_normal(len(u)), cv)
    ev = build_events(d, x=x)                              # every unit verified (verify_prob = 1)
    inj, ids = inject_faults(ev, seed=2000 + i)
    return dict(u=u, ev=ev, inj=inj, ids=ids, clean_flags=run_checks(u, ev), inj_flags=run_checks(u, inj))


@pytest.fixture(scope="module")
def reps():
    return [_rep(i) for i in range(REPS)]


def _excluded_total(ev: pd.DataFrame, flags: pd.DataFrame) -> float:
    """Sensitivity estimate stand-in (census of the units, no sampling).

    Flagged events are excluded and the unit total is rescaled by the events kept
    (a duplicate pair counts as one event). Units with a unit-level flag are excluded and
    the sum is expanded by units total / units kept. Flagged records are not changed.
    """
    bad_ev = set(flags["event_id"].dropna())
    bad_u = set(flags.loc[flags["event_id"].isna(), "unit_id"])
    dup = set(flags.loc[flags["check"] == "duplicate", "event_id"])
    g = ev.assign(bad=ev["event_id"].isin(bad_ev), dup=ev["event_id"].isin(dup))
    g = g.assign(kept_q=np.where(g["bad"], 0.0, g["q_diary"])).groupby("unit_id").agg(
        n=("bad", "size"), nbad=("bad", "sum"), nd=("dup", "sum"), kq=("kept_q", "sum"))
    ok = (g["n"] > g["nbad"]) & ~g.index.isin(bad_u)
    est = g["kq"] * (g["n"] - g["nd"] / 2) / (g["n"] - g["nbad"]).where(g["n"] > g["nbad"], 1)
    return float(est[ok].sum() * len(g) / ok.sum())


def test_flag_table_shape(reps):
    f = reps[0]["inj_flags"]
    assert list(f.columns) == FLAG_COLUMNS
    assert set(f["check"]) <= set(CHECKS)
    assert len(f) > 0
    assert f.loc[f["check"] == "yield_outlier", "event_id"].isna().all()   # unit-level check
    assert f.loc[f["check"] == "duplicate", "event_id"].notna().all()      # event-level check


def test_empty_flag_table_has_columns():
    d = make_district(replace(BASE, pop_seed=1, **SMALL))
    u = unit_table(d)
    ev = build_events(d)
    ev = ev.assign(q_diary=1.0, date=ev["date"].min() + pd.to_timedelta(ev.groupby("unit_id").cumcount(), unit="D"))  # one day per event: nothing to flag
    u = u.assign(area=1.0, type="pond", assisted=0)
    f = run_checks(u, ev.assign(seed_count=1e9, q_ver=np.nan))
    assert list(f.columns) == FLAG_COLUMNS and f.empty


def test_c4_inputs_not_modified(reps):
    r = reps[0]
    before = (_hash(r["u"]), _hash(r["ev"]), _hash(r["inj"]))
    run_checks(r["u"], r["ev"])
    run_checks(r["u"], r["inj"])
    assert (_hash(r["u"]), _hash(r["ev"]), _hash(r["inj"])) == before
    ev_before = _hash(r["ev"])
    inject_faults(r["ev"], seed=5)
    assert _hash(r["ev"]) == ev_before                     # injection works on a copy


def test_injection_counts(reps):
    r = reps[0]
    n = len(r["ev"])
    assert len(r["inj"]) == n + len(r["ids"]["duplicate"])
    assert len(r["ids"]["x10"]) == len(r["ids"]["gap"]) == round(0.02 * n)
    assert len(r["ids"]["seed"]) == round(0.02 * r["ev"]["unit_id"].nunique())
    assert not (r["ids"]["x10"] & r["ids"]["gap"]) and not (r["ids"]["x10"] & r["ids"]["duplicate"])


def _recall(reps, kind, check):
    hit = tot = 0
    for r in reps:
        f = r["inj_flags"]
        f = f[f["check"] == check]
        got = set(f["unit_id"]) if kind == "seed" else set(f["event_id"].dropna())
        hit += len(r["ids"][kind] & got)
        tot += len(r["ids"][kind])
    return hit / tot


def test_c1_duplicates(reps):
    assert _recall(reps, "duplicate", "duplicate") >= 0.90


def test_c1_seed(reps):
    assert _recall(reps, "seed", "seed_consistency") >= 0.80


def test_c1_gap(reps):
    assert _recall(reps, "gap", "diary_vs_verified") >= 0.80


def test_c1_x10(reps):
    assert _recall(reps, "x10", "event_size") >= 0.70      # C1, redesigned check, design 21.3b


# --- x10 likelihood ratio, hand-computed from design 21.3b -------------------------------------
_L = np.array([0.0, 0.1, -0.1, 0.2, -0.2, 0.0])            # log(total / area); median 0, MAD 0.1
_SD = 1.4826 * 0.1


def _lr_tables(assisted=0, seed=1e9):
    units = pd.DataFrame({"unit_id": [f"U{i}" for i in range(6)], "area": 1.0,
                          "type": "pond", "assisted": assisted})
    rows = [("U0", 0.5), ("U0", 0.5)] + [(f"U{i}", 1.0) for i in range(1, 6)]   # U0: two equal events
    ev = pd.DataFrame({"unit_id": [u for u, _ in rows],
                       "q_diary": [sh * np.exp(_L[int(u[1])]) for u, sh in rows],
                       "seed_count": seed, "q_ver": np.nan})
    ev["date"] = pd.Timestamp("2026-05-01") + pd.to_timedelta(np.arange(len(ev)), unit="D")
    ev["event_id"] = ev["unit_id"] + "-E" + ev.groupby("unit_id").cumcount().astype(str)
    return units, ev


def test_x10_lr_two_event_unit_matches_formula():
    units, ev = _lr_tables()
    log_d = np.log(10 / 5.5)                                # s' = 0.5
    expected = 2 * log_d - np.log(10) + (0.0 - (log_d / _SD) ** 2) / 2      # z0 = 0
    np.testing.assert_allclose(x10_log_lr(units, ev)[:2], expected, rtol=1e-12)


def test_x10_lr_one_event_unit_has_no_share_evidence():
    units, ev = _lr_tables()
    z0, z1 = 0.1 / _SD, (0.1 - np.log(10)) / _SD           # U1: s' = 1, D = 10, share part 0
    np.testing.assert_allclose(x10_log_lr(units, ev)[2], (z0**2 - z1**2) / 2, rtol=1e-12)


def _tab(ell, stratum=None, assisted=0, seed=1.0):
    """One single-event unit per value of ell = log(total / area), area 1."""
    k = len(ell)
    units = pd.DataFrame({"unit_id": [f"U{i}" for i in range(k)], "area": 1.0, "type": "pond",
                          "assisted": assisted})
    if stratum is not None:
        units["stratum"] = stratum
    ev = pd.DataFrame({"unit_id": units["unit_id"], "q_diary": np.exp(ell), "seed_count": seed})
    return units, ev


def _single(ell, mu, sd):                                   # share part is 0 for one event
    z0, z1 = (ell - mu) / sd, (ell - np.log(10) - mu) / sd
    return (z0**2 - z1**2) / 2


def test_x10_lr_small_stratum_uses_pooled_values():
    ell = np.r_[_L, 0.9, 1.0, 1.1]                          # stratum A: 6 units; B: 3 units -> pooled
    units, ev = _tab(ell, stratum=["A"] * 6 + ["B"] * 3)
    got = x10_log_lr(units, ev)
    np.testing.assert_allclose(got[1], _single(0.1, 0.0, _SD), rtol=1e-12)          # own stratum
    np.testing.assert_allclose(got[7], _single(1.0, 0.1, 1.4826 * 0.2), rtol=1e-12) # pooled: median 0.1, MAD 0.2


def test_x10_lr_flat_stratum_uses_pooled_values():
    ell = np.r_[0, 0, 0, 0, 0.3, 0.6, _L]                   # stratum A has MAD 0
    units, ev = _tab(ell, stratum=["A"] * 6 + ["B"] * 6)
    got = x10_log_lr(units, ev)
    np.testing.assert_allclose(got[5], _single(0.6, 0.0, 1.4826 * 0.05), rtol=1e-12)  # pooled: median 0, MAD 0.05
    np.testing.assert_allclose(got[7], _single(0.1, 0.0, _SD), rtol=1e-12)


def test_x10_lr_anchor_is_seed_for_assisted_area_otherwise():
    # assisted: total 1 t, seed exp(-L) -> l = L; U0 has three events, seed varies, median used.
    # not assisted: l = 2L from area, seed exp(-3L) must be ignored; U12 is assisted without seed -> area.
    units = pd.DataFrame({"unit_id": [f"U{i}" for i in range(13)], "area": 1.0, "type": "pond",
                          "assisted": [1] * 6 + [0] * 6 + [1]})
    rows = [("U0", 0.2, 1.0), ("U0", 0.3, 1.0), ("U0", 0.5, 4.0)]
    rows += [(f"U{i}", 1.0, np.exp(-_L[i])) for i in range(1, 6)]
    rows += [(f"U{i + 6}", np.exp(2 * _L[i]), np.exp(-3 * _L[i])) for i in range(6)]
    rows += [("U12", np.exp(0.1), 0.0)]
    ev = pd.DataFrame(rows, columns=["unit_id", "q_diary", "seed_count"])
    got = x10_log_lr(units, ev)
    log_d = np.log(10 / 5.5)                                # U0's s' = 0.5 event, l = 0
    np.testing.assert_allclose(got[2], 3 * log_d - np.log(10) - (log_d / _SD) ** 2 / 2, rtol=1e-12)
    np.testing.assert_allclose(got[3], _single(0.1, 0.0, _SD), rtol=1e-12)          # U1, seed anchor
    np.testing.assert_allclose(got[11], _single(0.4, 0.0, 1.4826 * 0.2), rtol=1e-12)  # U9, area anchor
    np.testing.assert_allclose(got[14], _single(0.1, 0.0, 1.4826 * 0.2), rtol=1e-12)  # U12 pooled with area units


def test_x10_flags_exactly_scores_above_cut():
    assert X10_LOG_LR_CUT == 0.5                            # design 21.3b
    units, ev = _lr_tables()
    for factor, lo, hi, flagged in ((2.600, 0.4, 0.5, False), (2.603, 0.5, 0.6, True)):   # U3 scaled: score near the cut
        slip = ev.copy()
        slip.loc[slip["unit_id"] == "U3", "q_diary"] *= factor
        score = x10_log_lr(units, slip)
        assert lo < score[4] < hi
        f = run_checks(units, slip)
        f = f[f["check"] == "event_size"]
        assert ("U3-E0" in set(f["event_id"])) == flagged
        assert set(f["event_id"]) == set(slip["event_id"][score > 0.5])
        assert (f["threshold"] == 0.5).all()
        np.testing.assert_allclose(f["value"].astype(float), score[score > 0.5])


def test_x10_single_event_slip_is_flagged_and_bad_rows_are_not():
    units, ev = _lr_tables()
    slip = ev.copy()
    slip.loc[slip["unit_id"] == "U3", "q_diary"] *= 10
    flags = run_checks(units, slip)
    assert "U3-E0" in set(flags.loc[flags["check"] == "event_size", "event_id"])
    zero = ev.copy()
    zero.loc[zero["unit_id"] == "U4", "q_diary"] = 0.0     # no positive total: no score, no flag
    score = x10_log_lr(units, zero)
    assert np.isnan(score[zero["unit_id"].to_numpy() == "U4"]).all()
    assert "U4-E0" not in set(run_checks(units, zero)["event_id"].dropna())
    ghost = pd.concat([ev, ev.iloc[[2]].assign(unit_id="GHOST", event_id="GHOST-E0")], ignore_index=True)
    assert np.isnan(x10_log_lr(units, ghost)[-1])          # unit not in the unit table: no score


def test_c2_clean_data_per_check(reps, capsys):
    n_u = sum(len(r["u"]) for r in reps)
    n_e = sum(len(r["ev"]) for r in reps)
    share = {}
    for c in CHECKS:
        if c in ("yield_outlier", "seed_consistency"):
            k = sum(r["clean_flags"][r["clean_flags"]["check"] == c]["unit_id"].nunique() for r in reps)
            share[c] = k / n_u
        else:
            k = sum(r["clean_flags"][r["clean_flags"]["check"] == c]["event_id"].nunique() for r in reps)
            share[c] = k / n_e
    any_ev = sum(r["clean_flags"]["event_id"].dropna().nunique() for r in reps) / n_e
    with capsys.disabled():
        print("\nC2 per check (clean data, 20 reps):", {k: round(v, 4) for k, v in share.items()},
              "any event flag:", round(any_ev, 4))
    assert share["yield_outlier"] <= 0.05
    for c in ("event_size", "duplicate", "diary_vs_verified"):   # amended C2: each event-level check <= 8%
        assert share[c] <= 0.08, c


def test_c2_any_event_flag_share(reps):
    n_e = sum(len(r["ev"]) for r in reps)
    any_ev = sum(r["clean_flags"]["event_id"].dropna().nunique() for r in reps) / n_e
    assert any_ev <= 0.12                                   # amended C2, design 21.3a


def test_c5_exclusion_moves_estimate_closer(reps):
    closer = 0
    err_inj = err_ex = 0.0
    for r in reps:
        clean = float(r["ev"]["q_diary"].sum())
        e_inj = abs(float(r["inj"]["q_diary"].sum()) - clean)
        e_ex = abs(_excluded_total(r["inj"], r["inj_flags"]) - clean)
        closer += e_ex < e_inj
        err_inj += e_inj
        err_ex += e_ex
    print(f"\nC5: closer in {closer}/{REPS} reps; mean abs error {err_inj / REPS:.1f} -> {err_ex / REPS:.1f} t")
    assert closer >= REPS // 2          # per replication the gain is noisy; see the mean error below
    assert err_ex < err_inj
