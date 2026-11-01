"""Seed commit-reveal, canonical frame hash and hash-chained append-only log (design.md 13)."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .select import prn_values, seed_bytes, select_smallest

GENESIS_HASH = "0" * 64
EVENTS = ("frame_load", "seed_commit", "frame_freeze", "seed_reveal", "selection",
          "upload", "flag", "review", "estimate_run")
_COMMIT_TAG = b"d32-seed-commit-v1|"


# ---------------------------------------------------------------- seed commit-reveal
def commit(seed, salt: str | None = None) -> tuple[str, str]:
    """Return (commitment, salt_hex). The commitment is SHA-256(tag | salt | seed).

    The salt is there because a short seed such as 4417 can be brute-forced from a bare
    SHA-256 in milliseconds; 16 random bytes make the published hash unguessable until
    the seed and the salt are revealed together."""
    salt = secrets.token_bytes(16).hex() if salt is None else salt
    return _commitment(seed, salt), salt


def _commitment(seed, salt_hex: str) -> str:
    return hashlib.sha256(_COMMIT_TAG + bytes.fromhex(salt_hex) + seed_bytes(seed)).hexdigest()


def verify_reveal(commitment: str, seed, salt: str) -> bool:
    try:
        return hmac.compare_digest(_commitment(seed, salt), str(commitment))
    except ValueError:      # salt is not valid hex
        return False


# ---------------------------------------------------------------- frame hash
def _fmt(v) -> str:
    """Fixed text form of one cell: bool -> true/false, int -> decimal, float -> 17 significant
    digits (round-trips a double), missing -> nan."""
    if v is None or (not isinstance(v, (str, bytes)) and pd.isna(v)):
        return "nan"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return format(v, ".17g")
    return str(v)


def frame_hash(frame) -> str:
    """SHA-256 of a canonical byte form of the frame: columns sorted by name, rows sorted by
    unit_id, one JSON array of fixed-format strings per row. Row order does not matter.
    `frame` is a DataFrame or a path to a CSV file. A column holding ints hashes differently
    from one holding the same numbers as floats, so hash the frame as it will be selected from."""
    df = pd.read_csv(frame) if isinstance(frame, (str, os.PathLike)) else frame
    if "unit_id" not in df.columns:
        raise ValueError("frame has no unit_id column")
    if df["unit_id"].duplicated().any():
        raise ValueError("unit_id is not unique")
    cols = sorted(df.columns, key=str)
    df = df.assign(_k=df["unit_id"].astype(str)).sort_values("_k", kind="stable")
    data = [df[c].tolist() for c in cols]
    lines = [json.dumps([str(c) for c in cols])]
    lines += [json.dumps([_fmt(v) for v in row]) for row in zip(*data)]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def file_hash(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------- hash-chained log
def _default(o):
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, os.PathLike):
        return os.fspath(o)
    raise TypeError(f"not JSON serialisable: {type(o).__name__}")


def _canon(obj) -> str:
    """The one text form used both for hashing and for the file line."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False, default=_default)


def _entry_hash(body: dict) -> str:
    return hashlib.sha256(_canon(body).encode("ascii")).hexdigest()


_BODY_KEYS = {"seq", "timestamp", "event", "payload", "prev_hash"}


def _scan(path: Path):
    """Walk the file. Returns (n_entries, head_hash, first_bad_seq, reason). first_bad_seq is
    the sequence slot (0-based position) at which the file stops being a valid chain."""
    data = path.read_bytes()
    if not data:
        return 0, GENESIS_HASH, None, None
    lines = data.split(b"\n")
    tail = lines.pop()                       # b"" when the file ends with a newline
    prev = GENESIS_HASH
    for pos, raw in enumerate(lines):
        try:
            text = raw.decode("ascii")
            e = json.loads(text)
        except ValueError:
            return pos, prev, pos, "line is not valid ASCII JSON"
        if not isinstance(e, dict) or set(e) != _BODY_KEYS | {"entry_hash"}:
            return pos, prev, pos, "entry does not have the expected fields"
        if type(e["seq"]) is not int or e["seq"] != pos:
            return pos, prev, pos, f"seq is {e['seq']!r}, expected {pos} (entry deleted, inserted or reordered)"
        if e["prev_hash"] != prev:
            return pos, prev, pos, "prev_hash does not match the previous entry"
        body = {k: e[k] for k in _BODY_KEYS}
        try:
            ok = _entry_hash(body) == e["entry_hash"] and _canon(e) == text
        except (ValueError, TypeError):
            ok = False
        if not ok:
            return pos, prev, pos, "entry content does not match its entry_hash"
        prev = e["entry_hash"]
    if tail:
        return len(lines), prev, len(lines), "last line is not terminated by a newline"
    return len(lines), prev, None, None


def verify(path, expected_head: str | None = None) -> tuple[bool, int | None, str]:
    """Re-read the file and check every link. Returns (ok, first_bad_seq, reason).

    A hash chain cannot see entries cut off the end of the file. To catch that, publish the
    head hash (AuditLog.head_hash) and pass it as `expected_head`."""
    path = Path(path)
    if not path.exists():
        return False, None, "log file not found"
    n, head, bad, reason = _scan(path)
    if bad is not None:
        return False, bad, reason
    if expected_head is not None and head != expected_head:
        return False, n, "head hash differs from the published one (log truncated or replaced)"
    return True, None, f"ok: {n} entries, head {head}"


class AuditLog:
    """Append-only JSON Lines log. One writer at a time: two open handles on the same file
    would fork the chain."""

    def __init__(self, path):
        self.path = Path(path)
        if self.path.exists():
            n, head, bad, reason = _scan(self.path)
            if bad is not None:
                raise ValueError(f"refusing to append to a broken log (seq {bad}): {reason}")
            self._next, self._head = n, head
        else:
            self._next, self._head = 0, GENESIS_HASH

    @property
    def head_hash(self) -> str:
        return self._head

    def __len__(self) -> int:
        return self._next

    def append(self, event: str, payload: dict | None = None) -> dict:
        if event not in EVENTS:
            raise ValueError(f"unknown event type {event!r}; expected one of {EVENTS}")
        body = {
            "seq": self._next,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            "event": event,
            "payload": json.loads(_canon(payload or {})),   # normalise numpy, paths, tuples
            "prev_hash": self._head,
        }
        entry = {**body, "entry_hash": _entry_hash(body)}
        with open(self.path, "ab") as f:     # binary: no newline translation on Windows
            f.write(_canon(entry).encode("ascii") + b"\n")
            f.flush()
            os.fsync(f.fileno())
        self._next, self._head = self._next + 1, entry["entry_hash"]
        return entry


# ---------------------------------------------------------------- estimate run record
def code_version(repo_dir=None) -> dict:
    """Git commit of the code, or 'unknown'. `dirty` is True when files differ from that commit."""
    cwd = str(repo_dir or Path(__file__).resolve().parent)
    try:
        run = lambda *a: subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True,
                                        timeout=10, check=True).stdout.strip()
        return {"commit": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain"))}
    except (OSError, subprocess.SubprocessError):
        return {"commit": "unknown", "dirty": None}


def estimate_run_record(*, frame_hash: str, seed_commitment: str, data_snapshot, params, output,
                        repo_dir=None) -> dict:
    """The design.md 13 record. data_snapshot, params and output are file paths: the snapshot
    and the output are hashed byte for byte; the parameter file is hashed and stored in full."""
    params = Path(params)
    return {
        "code_version": code_version(repo_dir),
        "frame_hash": frame_hash,
        "seed_commitment": seed_commitment,
        "data_snapshot_hash": file_hash(data_snapshot),
        "params_hash": file_hash(params),
        "params": params.read_text(encoding="utf-8"),
        "output_hash": file_hash(output),
    }


def log_estimate_run(log: AuditLog, **kwargs) -> dict:
    return log.append("estimate_run", estimate_run_record(**kwargs))


# ---------------------------------------------------------------- demo
def select_sample(listed: pd.DataFrame, design, seed) -> list[str]:
    ids = listed["unit_id"].values
    sel = select_smallest(prn_values(seed, ids), design.unit_stratum, design.n_h)
    return [str(i) for i in ids[sel]]


def run_demo(directory, seed: int = 4417, cfg=None) -> dict:
    """commit -> load -> freeze -> reveal -> select, each step logged, then verify."""
    from .config import BASE
    from .design import build_design
    from .synth import make_district

    cfg = cfg or BASE
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / "audit.jsonl"
    if log_path.exists():
        raise FileExistsError(f"{log_path} exists; use an empty directory for the demo")
    log = AuditLog(log_path)

    commitment, salt = commit(seed)
    log.append("seed_commit", {"commitment": commitment})

    listed = make_district(cfg).listed.reset_index(drop=True)
    frame_path = directory / "frame.csv"
    listed.to_csv(frame_path, index=False)
    fh = frame_hash(frame_path)
    assert fh == frame_hash(listed), "frame hash differs between the file and the in-memory frame"
    log.append("frame_load", {"path": frame_path.name, "n_units": len(listed)})
    log.append("frame_freeze", {"frame_hash": fh})

    assert verify_reveal(commitment, seed, salt)
    log.append("seed_reveal", {"seed": seed, "salt": salt, "commitment": commitment})

    design = build_design(listed, cfg)
    chosen = select_sample(listed, design, seed)
    log.append("selection", {"frame_hash": fh, "seed_commitment": commitment, "n_selected": len(chosen),
                             "unit_ids": chosen})

    # an outsider re-runs from the public record only: logged reveal + frame file
    reveal = next(json.loads(l)["payload"] for l in log_path.read_text().splitlines()
                  if json.loads(l)["event"] == "seed_reveal")
    rerun = select_sample(pd.read_csv(frame_path), design, reveal["seed"])
    ok, bad, reason = verify(log_path)
    return {"log_path": log_path, "frame_hash": fh, "commitment": commitment, "selected": chosen,
            "rerun_matches": rerun == chosen, "verify": (ok, bad, reason), "entries": len(log),
            "head": log.head_hash}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m d32.audit")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo", help="run commit, freeze, reveal and select on a synthetic frame")
    d.add_argument("--dir", required=True)
    d.add_argument("--seed", type=int, default=4417)
    v = sub.add_parser("verify", help="check the chain of a log file")
    v.add_argument("path")
    a = ap.parse_args(argv)
    if a.cmd == "verify":
        ok, bad, reason = verify(a.path)
        print(f"chain {'VERIFIED' if ok else 'BROKEN'}: {reason}" + ("" if ok else f" (first bad seq {bad})"))
        return 0 if ok else 1
    r = run_demo(a.dir, a.seed)
    print(f"log:            {r['log_path']}")
    print(f"commitment:     {r['commitment']}")
    print(f"frame hash:     {r['frame_hash']}")
    print(f"selected:       {len(r['selected'])} units; re-run from the logged reveal matches: {r['rerun_matches']}")
    ok, bad, reason = r["verify"]
    print(f"chain {'VERIFIED' if ok else 'BROKEN'}: {reason}")
    return 0 if ok and r["rerun_matches"] else 1


if __name__ == "__main__":
    sys.exit(main())
