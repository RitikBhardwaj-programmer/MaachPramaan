"""Tests for design.md 13: commit-reveal, frame hash, hash-chained append-only log."""
import json
import tempfile
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings, strategies as st

from d32.audit import (EVENTS, GENESIS_HASH, AuditLog, commit, estimate_run_record, file_hash,
                       frame_hash, log_estimate_run, run_demo, verify, verify_reveal)
from d32.config import BASE
from d32.design import build_design
from d32.select import prn_values, select_smallest
from d32.synth import make_district


# ------------------------------------------------------------------ commit-reveal
def test_commitment_verifies_for_right_seed_and_salt():
    c, salt = commit(4417)
    assert verify_reveal(c, 4417, salt)
    assert verify_reveal(c, "4417", salt)          # same seed text, same bytes as the PRN key


def test_commitment_fails_for_wrong_seed_or_salt():
    c, salt = commit(4417)
    assert not verify_reveal(c, 4418, salt)
    assert not verify_reveal(c, 4417, commit(4417)[1])
    assert not verify_reveal(c, 4417, "zz")        # not hex: false, no exception
    assert not verify_reveal("0" * 64, 4417, salt)


def test_same_seed_gives_different_commitments():
    # the salt is what stops a guesser testing seeds 0..10^6 against the published hash
    assert commit(4417)[0] != commit(4417)[0]


# ------------------------------------------------------------------ frame hash
def _frame(n=60):
    rng = np.random.default_rng(3)
    return pd.DataFrame({"unit_id": [f"D1-{i:06d}" for i in range(n)],
                         "area": rng.lognormal(0, 1, n),
                         "type": rng.choice(["pond", "tank"], n),
                         "on_list": rng.random(n) < 0.5,
                         "block": rng.integers(0, 9, n)})


def test_frame_hash_ignores_row_and_column_order():
    f = _frame()
    shuffled = f.sample(frac=1, random_state=1)[list(reversed(f.columns))]
    assert frame_hash(f) == frame_hash(shuffled)


def test_frame_hash_changes_with_one_area_value():
    f = _frame()
    g = f.copy()
    g.loc[7, "area"] = np.nextafter(g.loc[7, "area"], np.inf)   # one ulp is enough
    assert frame_hash(f) != frame_hash(g)
    assert frame_hash(f) != frame_hash(f.drop(index=7))


def test_frame_hash_of_csv_file_equals_hash_of_dataframe(tmp_path):
    f = _frame()
    p = tmp_path / "frame.csv"
    f.sample(frac=1, random_state=2).to_csv(p, index=False)
    assert frame_hash(p) == frame_hash(f)


def test_frame_hash_needs_unique_unit_id():
    f = _frame()
    f.loc[1, "unit_id"] = f.loc[0, "unit_id"]
    with pytest.raises(ValueError):
        frame_hash(f)


# ------------------------------------------------------------------ chain
def _make_log(tmp_path, n=6):
    p = tmp_path / "audit.jsonl"
    log = AuditLog(p)
    for i in range(n):
        log.append(EVENTS[i % len(EVENTS)], {"i": i, "note": f"entry {i}", "x": 0.1 * i})
    return p


def _lines(p):
    return p.read_bytes().split(b"\n")[:-1]


def _write_lines(p, lines):
    p.write_bytes(b"\n".join(lines) + b"\n")


def test_untouched_chain_verifies(tmp_path):
    p = _make_log(tmp_path)
    ok, bad, reason = verify(p)
    assert ok and bad is None and "6 entries" in reason
    first = json.loads(_lines(p)[0])
    assert first["seq"] == 0 and first["prev_hash"] == GENESIS_HASH


def test_unknown_event_type_rejected(tmp_path):
    with pytest.raises(ValueError):
        AuditLog(tmp_path / "a.jsonl").append("made_up", {})


@pytest.mark.parametrize("k", [0, 2, 5])
def test_editing_a_byte_of_entry_k_breaks_chain_at_k(tmp_path, k):
    p = _make_log(tmp_path)
    lines = _lines(p)
    i = lines[k].index(b"entry ") + 6                 # a digit inside the payload text
    edited = bytearray(lines[k])
    edited[i] = ord("9") if edited[i] != ord("9") else ord("8")
    lines[k] = bytes(edited)
    _write_lines(p, lines)
    ok, bad, _ = verify(p)
    assert not ok and bad == k


def test_editing_and_rehashing_entry_is_caught_at_next_entry(tmp_path):
    p = _make_log(tmp_path)
    lines = _lines(p)
    e = json.loads(lines[2])
    e["payload"]["note"] = "forged"
    from d32.audit import _canon, _entry_hash
    e["entry_hash"] = _entry_hash({k: e[k] for k in ("seq", "timestamp", "event", "payload", "prev_hash")})
    lines[2] = _canon(e).encode()
    _write_lines(p, lines)
    ok, bad, _ = verify(p)
    assert not ok and bad == 3


def test_deleting_an_entry_breaks_chain_where_it_was(tmp_path):
    p = _make_log(tmp_path)
    lines = _lines(p)
    del lines[3]
    _write_lines(p, lines)
    ok, bad, _ = verify(p)
    assert not ok and bad == 3


def test_inserting_an_entry_breaks_chain_where_it_was_put(tmp_path):
    p = _make_log(tmp_path)
    lines = _lines(p)
    lines.insert(2, lines[1])                       # a copy of a valid entry
    _write_lines(p, lines)
    ok, bad, _ = verify(p)
    assert not ok and bad == 2


def test_reordering_two_entries_breaks_chain_at_first_of_them(tmp_path):
    p = _make_log(tmp_path)
    lines = _lines(p)
    lines[3], lines[4] = lines[4], lines[3]
    _write_lines(p, lines)
    ok, bad, _ = verify(p)
    assert not ok and bad == 3


def test_truncation_is_caught_only_with_published_head(tmp_path):
    p = _make_log(tmp_path)
    head = AuditLog(p).head_hash
    _write_lines(p, _lines(p)[:-2])
    assert verify(p)[0]                              # a bare chain cannot see a cut tail
    ok, bad, _ = verify(p, expected_head=head)
    assert not ok and bad == 4


def test_missing_trailing_newline_and_non_ascii_byte_are_caught(tmp_path):
    p = _make_log(tmp_path)
    raw = p.read_bytes()
    p.write_bytes(raw[:-1])
    assert verify(p)[:2] == (False, 5)
    p.write_bytes(raw[:10] + b"\xc3" + raw[11:])
    assert verify(p)[:2] == (False, 0)


def test_reopen_continues_the_chain(tmp_path):
    p = _make_log(tmp_path, n=3)
    head = AuditLog(p).head_hash
    log2 = AuditLog(p)
    e = log2.append("flag", {"unit": "D1-000001"})
    assert e["seq"] == 3 and e["prev_hash"] == head
    AuditLog(p).append("review", {"ok": True})
    ok, bad, reason = verify(p)
    assert ok and "5 entries" in reason


def test_reopening_a_tampered_log_refuses_to_append(tmp_path):
    p = _make_log(tmp_path)
    lines = _lines(p)
    del lines[1]
    _write_lines(p, lines)
    with pytest.raises(ValueError):
        AuditLog(p)


def test_numpy_values_in_payload_are_logged(tmp_path):
    p = tmp_path / "a.jsonl"
    AuditLog(p).append("selection", {"n": np.int64(5), "w": np.float64(0.5), "ids": np.array([1, 2])})
    assert verify(p)[0]
    assert json.loads(_lines(p)[0])["payload"] == {"n": 5, "w": 0.5, "ids": [1, 2]}


# ------------------------------------------------------------------ estimate run record
def test_estimate_run_record_and_entry(tmp_path):
    snap, params, out = tmp_path / "snap.csv", tmp_path / "params.json", tmp_path / "out.csv"
    snap.write_text("a,b\n1,2\n")
    params.write_text('{"n": 200}', encoding="utf-8")
    out.write_text("total,7\n")
    log = AuditLog(tmp_path / "a.jsonl")
    e = log_estimate_run(log, frame_hash="f" * 64, seed_commitment="c" * 64,
                         data_snapshot=snap, params=params, output=out)
    r = e["payload"]
    assert e["event"] == "estimate_run" and verify(log.path)[0]
    assert r["frame_hash"] == "f" * 64 and r["seed_commitment"] == "c" * 64
    assert r["data_snapshot_hash"] == file_hash(snap) and r["output_hash"] == file_hash(out)
    assert r["params_hash"] == file_hash(params) and r["params"] == '{"n": 200}'
    assert r["code_version"]["commit"] == "unknown" or len(r["code_version"]["commit"]) == 40


def test_code_version_unknown_outside_git(tmp_path):
    f = tmp_path / "x"
    f.write_text("x")
    r = estimate_run_record(frame_hash="a", seed_commitment="b", data_snapshot=f, params=f, output=f,
                            repo_dir=tmp_path)
    assert r["code_version"] == {"commit": "unknown", "dirty": None}


# ------------------------------------------------------------------ demo = existing selection
def test_demo_selection_equals_direct_selection_and_rerun(tmp_path):
    cfg = replace(BASE, n_listed=3000, n_not_on_list=300)
    r = run_demo(tmp_path / "demo", seed=4417, cfg=cfg)
    assert r["verify"][0] and r["entries"] == 5 and r["rerun_matches"]
    listed = make_district(cfg).listed.reset_index(drop=True)
    design = build_design(listed, cfg)
    ids = listed["unit_id"].values
    direct = select_smallest(prn_values(4417, ids), design.unit_stratum, design.n_h)
    assert r["selected"] == [str(i) for i in ids[direct]]
    # reveal, then re-run from the logged seed, gives the same sample
    entries = [json.loads(l) for l in _lines(r["log_path"])]
    assert [e["event"] for e in entries] == ["seed_commit", "frame_load", "frame_freeze", "seed_reveal", "selection"]
    reveal = entries[3]["payload"]
    assert verify_reveal(entries[0]["payload"]["commitment"], reveal["seed"], reveal["salt"])
    again = select_smallest(prn_values(reveal["seed"], ids), design.unit_stratum, design.n_h)
    assert [str(i) for i in ids[again]] == entries[4]["payload"]["unit_ids"]
    assert entries[2]["payload"]["frame_hash"] == frame_hash(listed)


def test_demo_refuses_existing_log(tmp_path):
    cfg = replace(BASE, n_listed=3000, n_not_on_list=300)
    run_demo(tmp_path / "demo", cfg=cfg)
    with pytest.raises(FileExistsError):
        run_demo(tmp_path / "demo", cfg=cfg)


# ------------------------------------------------------------------ property
_json = st.recursive(
    st.none() | st.booleans() | st.integers(-2**63, 2**63) | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(max_size=20),
    lambda c: st.lists(c, max_size=3) | st.dictionaries(st.text(max_size=8), c, max_size=3),
    max_leaves=8)


@settings(max_examples=60, deadline=None)
@given(items=st.lists(st.tuples(st.sampled_from(EVENTS), st.dictionaries(st.text(max_size=8), _json, max_size=3)),
                      min_size=1, max_size=6),
       where=st.floats(0, 1, exclude_max=True), delta=st.integers(1, 255))
def test_any_payload_sequence_verifies_and_any_byte_edit_breaks_it(items, where, delta):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "a.jsonl"
        log = AuditLog(p)
        for ev, payload in items:
            log.append(ev, payload)
        assert verify(p)[0]
        raw = bytearray(p.read_bytes())
        i = int(where * len(raw))
        line_index = raw[:i].count(b"\n")             # the entry that holds byte i
        raw[i] = (raw[i] + delta) % 256               # always a different byte
        p.write_bytes(bytes(raw))
        ok, bad, _ = verify(p)
        assert not ok and bad == line_index


def test_edit_that_leaves_parsed_content_unchanged_is_still_caught(tmp_path):
    # the escape u00e9 and its upper-case form u00E9 parse to the same text; the file must stay byte-exact
    low = chr(92).encode() + b"u00e9"
    up = chr(92).encode() + b"u00E9"
    p = tmp_path / "a.jsonl"
    log = AuditLog(p)
    log.append("flag", {"name": chr(0xE9)})
    log.append("flag", {"name": "x"})
    raw = p.read_bytes()
    assert low in raw
    p.write_bytes(raw.replace(low, up))
    ok, bad, _ = verify(p)
    assert not ok and bad == 0
