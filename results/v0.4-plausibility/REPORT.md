# Part A plausibility run: C1 and C2 (design.md 21.3, 21.3b)

**All data are SIMULATED.** Seeds: part A, `pop_seed` 20261104, `master_seed` 6609 (first use). 200 replications on one S1-size district (21,600 units), checks run on every unit's events. Command:

    python -m d32.plausibility_run --reps 200 --out results/v0.4-plausibility

The ×10 check was redesigned (21.3b) and its cut fixed on throw-away seeds 1 to 20 before this run. Nothing was tuned after it.

## Criteria (Dirichlet(1) shares, the generator)

| Criterion | Limit | Measured | Result |
|---|---|---|---|
| C1 recall, duplicates | ≥ 90% | 100% | met |
| C1 recall, seed-inconsistent units | ≥ 80% | 100% | met |
| C1 recall, gap events | ≥ 80% | 100% | met |
| C1 recall, ×10 events (new LR check) | ≥ 70% | **73.3%** (SE 0.08 points within this district) | met |
| C2 clean units with a yield-outlier flag | ≤ 5% | 0.04% | met |
| C2 clean events, event size (×10 check) | ≤ 8% | 4.9% | met |
| C2 clean events, duplicate | ≤ 8% | 0.02% | met |
| C2 clean events, diary vs verified | ≤ 8% | **8.7%** | **not met** |
| C2 clean events with any flag | ≤ 12% | **12.9%** | **not met** |

The old multiple-6 rule gave 63.7% ×10 recall on the throw-away seeds. The new check gives 73.9% there and 73.3% here, so the throw-away estimate held on new seeds.

## Share-model robustness (report only, 21.3b)

| Shares | ×10 recall | Clean events flagged by the ×10 check |
|---|---|---|
| Dirichlet(0.5), more uneven than the generator | 62.2% | 7.1% |
| Dirichlet(1), generator | 73.3% | 4.9% |
| Dirichlet(3), more even | 88.1% | 1.9% |

The Dirichlet(0.5) row is the honest lower reading: the share part of the score assumes the generator's own model.

## Reading

- **The redesign works as specified.** ×10 recall rose by about 10 points at the same clean-flag rate. About a quarter of ×10 slips still pass, mostly on small events.
- **The two C2 failures are in the diary-vs-verified check, which did not change.** Its limits (21.3a) came from the 860-unit test fixture (5.8% there). At the S1 size the gap rule flags 8.7% of clean events. The cause is diary noise at ρ = 0.9: the flag depends on each unit's diary/true ratio, so it is the same under every share model. Per the spec, this is reported and not re-tuned. A real review queue would hold about 13% of events.
- **Limits of this run.** One district, so the SE above leaves out variation between districts. C3 and C4 run in pytest on every test replication; C5 is covered only by pytest (20 small replications), not by this run.

Files: `replications.csv` (one row per replication and share model), `summary.json`.
