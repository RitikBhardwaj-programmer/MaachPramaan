"""Part A run of the plausibility checks: criteria C1 and C2 (design.md 21.3, 21.3b). SIMULATED data.

    python -m d32.plausibility_run --reps 200 --out results/v0.4-plausibility

One district from part A `pop_seed`; replication r takes child r of SeedSequence(master_seed).spawn(reps)
and spawns from it the diary noise, the event stream, the fault injection and the share re-splits.
The Dirichlet(0.5) and Dirichlet(3) re-splits are a report only (21.3b). C5 is not run here.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

from .config import BASE
from .events import build_events, unit_table
from .plausibility import CHECKS, inject_faults, run_checks
from .synth import eta_cv, lognormal_noise, make_district

PART_A = dict(pop_seed=20261104, master_seed=6609)        # [DOC] design.md 21, part A
ALPHAS = (1.0, 0.5, 3.0)                                  # 1.0 = generator; others report only
UNIT_CHECKS = ("yield_outlier", "seed_consistency")
LIMITS = {"recall": {"duplicate": 0.90, "seed": 0.80, "gap": 0.80, "x10": 0.70},
          "clean": {"yield_outlier": 0.05, "event_size": 0.08, "duplicate": 0.08,
                    "diary_vs_verified": 0.08, "any_event": 0.12}}
FAULT_CHECK = {"duplicate": "duplicate", "seed": "seed_consistency", "gap": "diary_vs_verified",
               "x10": "event_size"}


def resplit(ev: pd.DataFrame, u: pd.DataFrame, x: pd.Series, alpha: float, rng) -> pd.DataFrame:
    """Same units, totals and verified events; new Dirichlet(alpha) shares."""
    w = pd.Series(rng.gamma(alpha, 1.0, len(ev)), index=ev.index)
    share = (w / w.groupby(ev["unit_id"]).transform("sum")).to_numpy()
    y = u.set_index("unit_id")["y"]
    out = ev.copy()
    out["q_diary"] = x.reindex(ev["unit_id"]).to_numpy() * share
    out["q_ver"] = np.where(ev["q_ver"].notna(), y.reindex(ev["unit_id"]).to_numpy() * share, np.nan)
    return out


def one_rep(d, u, child: np.random.SeedSequence) -> list[dict]:
    cfg = d.cfg
    s_diary, s_event, s_inject, s_split = child.spawn(4)
    y = u["y"].to_numpy()
    rng = np.random.default_rng(s_diary)
    cv = eta_cv(y, d.calib_group, cfg.rho_diary)
    x = y * np.exp(cfg.beta_diary_assisted) * lognormal_noise(rng.standard_normal(len(u)), cv)
    ev = build_events(d, x=x, seed=int(s_event.generate_state(1)[0]))
    x_unit = pd.Series(x, index=u["unit_id"].to_numpy())
    split_rng = np.random.default_rng(s_split)
    inject_seed = int(s_inject.generate_state(1)[0])
    rows = []
    for alpha in ALPHAS:
        e = ev if alpha == 1.0 else resplit(ev, u, x_unit, alpha, split_rng)
        inj, ids = inject_faults(e, seed=inject_seed)
        fc, fi = run_checks(u, e), run_checks(u, inj)
        row = {"alpha": alpha, "n_units": len(u), "n_events": len(e),
               "any_event_clean": fc["event_id"].dropna().nunique()}
        for c in CHECKS:
            col = "unit_id" if c in UNIT_CHECKS else "event_id"
            row[f"clean_{c}"] = fc.loc[fc["check"] == c, col].dropna().nunique()
        for kind, c in FAULT_CHECK.items():
            f = fi[fi["check"] == c]
            got = set(f["unit_id"]) if kind == "seed" else set(f["event_id"].dropna())
            row[f"hit_{kind}"], row[f"n_{kind}"] = len(ids[kind] & got), len(ids[kind])
        rows.append(row)
    return rows


def summarise(df: pd.DataFrame) -> dict:
    out = {}
    for alpha, g in df.groupby("alpha"):
        s = g.sum()
        rec = {k: s[f"hit_{k}"] / s[f"n_{k}"] for k in FAULT_CHECK}
        clean = {c: s[f"clean_{c}"] / (s["n_units"] if c in UNIT_CHECKS else s["n_events"]) for c in CHECKS}
        clean["any_event"] = s["any_event_clean"] / s["n_events"]
        per_rep_x10 = g["hit_x10"] / g["n_x10"]
        out[f"alpha_{alpha:g}"] = {
            "reps": len(g), "recall": rec, "clean_share": clean,
            "x10_recall_se_over_reps": float(per_rep_x10.std(ddof=1) / np.sqrt(len(g))),
        }
    main = out["alpha_1"]
    main["pass"] = {f"C1_{k}": bool(main["recall"][k] >= v) for k, v in LIMITS["recall"].items()}
    main["pass"].update({f"C2_{k}": bool(main["clean_share"][k] <= v) for k, v in LIMITS["clean"].items()})
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pop-seed", type=int, default=PART_A["pop_seed"])        # override for smoke tests only
    ap.add_argument("--master-seed", type=int, default=PART_A["master_seed"])
    a = ap.parse_args(argv)
    if (a.pop_seed, a.master_seed) == (PART_A["pop_seed"], PART_A["master_seed"]) and a.reps != 200:
        ap.error("part A seeds run once, with --reps 200 (design.md 21.3b); use other seeds for smoke tests")
    if (a.out / "replications.csv").exists():
        ap.error(f"{a.out / 'replications.csv'} exists; refusing to overwrite a recorded run")
    cfg = replace(BASE, pop_seed=a.pop_seed, master_seed=a.master_seed)
    d = make_district(cfg)
    u = unit_table(d)
    rows = []
    for r, child in enumerate(np.random.SeedSequence(cfg.master_seed).spawn(a.reps)):
        rows += [dict(rep=r, **x) for x in one_rep(d, u, child)]
        if (r + 1) % 20 == 0:
            print(f"rep {r + 1}/{a.reps}", flush=True)
    df = pd.DataFrame(rows)
    a.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out / "replications.csv", index=False)
    seeds = {"pop_seed": cfg.pop_seed, "master_seed": cfg.master_seed, "part_A": cfg.pop_seed == PART_A["pop_seed"]
             and cfg.master_seed == PART_A["master_seed"]}
    summary = {"label": "SIMULATED", "seeds": seeds, "limits": LIMITS, "results": summarise(df),
               "config": {k: v for k, v in asdict(cfg).items() if not isinstance(v, (list, dict))}}
    (a.out / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    print(json.dumps(summary["results"], indent=2, default=float))


if __name__ == "__main__":
    main()
