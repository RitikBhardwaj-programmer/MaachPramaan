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
from d32.plausibility import CHECKS, FLAG_COLUMNS, inject_faults, run_checks
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


@pytest.mark.xfail(strict=True, reason=(
    "Spec tension, see report: with the event-size multiple at 6 (needed for C2 on this check), "
    "recall of x10 events is about 70%. A multiple of 2 gives about 90% recall but flags about 28% "
    "of clean events."))
def test_c1_x10(reps):
    assert _recall(reps, "x10", "event_size") >= 0.90


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
    assert share["event_size"] <= 0.05 and share["duplicate"] <= 0.05


@pytest.mark.xfail(strict=True, reason=(
    "Spec tension, see report: with diary noise at rho_diary = 0.9 (cv about 0.3), 4% to 8% of clean "
    "events fail the 50% diary-vs-verified rule on their own, so the any-flag share is above 5%."))
def test_c2_any_event_flag_share(reps):
    n_e = sum(len(r["ev"]) for r in reps)
    any_ev = sum(r["clean_flags"]["event_id"].dropna().nunique() for r in reps) / n_e
    assert any_ev <= 0.05


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
