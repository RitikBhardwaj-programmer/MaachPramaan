# Part D confirmation run, design v0.5 (all numbers SIMULATED)

**Every number below is simulated** (synthetic district, nothing about real Assam production). Spec: `docs/design.md` section 22 (F1 matched-event ratio, F2 recall of dropouts with double sampling, F3 adaptive verification rate; amendments 22.6 after the independent review). Seeds fixed in section 22 before any run: `pop_seed = 20261107`, `master_seed = 9931` (first use). Nothing was tuned on these seeds; the pilot (seeds 41 to 44) and the review (seeds 51 to 60) were throw-away.

1,000 replications each for S1 to S5 and the stress scenarios S4x and S5x, bootstrap (500 replicates) on every replication, all three fixes on plus the v0.4 features. True district total in this synthetic district: **14,358.7 t**; true productivity **4.086 t/ha** (both simulated).

    python -m d32.simulate --reps 1000 --v05 --scenarios S1,S2,S3,S4,S5,S4x,S5x --pop-seed 20261107 --master-seed 9931 --workers 12 --out results/v0.5

**Headline.** The S5 and S4 biases are fixed (R1, R2 met) and S1 still meets AC1 to AC5 (R4). S2 is improved but **not fixed**: RSE 8.3% against the 7.5% target, with the 0.80 cap reached in a third of replications (R3 not met). The fixes cost extra verification visits: +28% in S1, +112% in S2. The stress scenario S5x shows F1's limit: when verification follows the diary error, bias is −4.2% and coverage 86.9%.

## 1. Criteria

| # | Criterion | Measured | Result |
|---|---|---|---|
| R1 | S5: \|bias\| < 1%, coverage 93–97% | bias **+0.22%** (MC SE 0.24), coverage **94.6%** (0.7) | met |
| R2 | S4: \|bias\| < 1%, coverage 93–97% | bias **+0.55%** (0.21), coverage **96.1%** (0.6) | met |
| R3 | S2: empirical RSE ≤ 7.5%, coverage 93–97% | RSE **8.28%** (about ±0.19), coverage 94.6% | **not met** (RSE) |
| R4 | S1: AC1–AC5 | coverage 95.3%, bias +0.10%, E0 +14.7% and E1 −27.7% show their bias, bootstrap SE / SD 0.985, RSE 6.99% | met |
| R5 | S3, S4x, S5x reported | section 2 | met |
| Z1 | v0.5 switches off reproduce `results/v0.4` (reps 0–29) | 150 of 150 rows exactly equal (checked before and after the review fixes) | met |

## 2. All scenarios (E3, bootstrap interval)

| Scen. | Bias (MC SE) | Coverage boot / lin | RSE emp. | Boot SE / SD | Mean ν (cap hit) | Verified units | Reading |
|---|---|---|---|---|---|---|---|
| S1 | +0.10% (0.22) | 95.3% / 93.7% | 6.99% | 0.985 | 0.39 (9%) | 70.0 | Base case holds. |
| S2 (ρ 0.7) | +0.25% (0.26) | 94.6% / 93.7% | **8.28%** | 0.987 | 0.64 (32%) | 115.8 | Interval holds; precision short of 7.5% even at the cap. |
| S3 | +0.12% (0.22) | 95.8% / 93.6% | 7.03% | 0.978 | 0.40 (10%) | 71.7 | Combined ratio still unbiased. |
| S4 | +0.55% (0.21) | 96.1% / 96.1% | 6.58% | 1.007 | 0.39 (9%) | 70.5 | Fixed by recall of dropouts (13.7 of 19.7 dropouts answer). |
| S5 | +0.22% (0.24) | 94.6% / 93.0% | 7.43% | 0.964 | 0.40 (10%) | 72.5 | Fixed by the matched-event ratio. |
| S4x (stress) | −0.11% (0.21) | 95.3% / 96.4% | 6.50% | 1.007 | 0.40 (10%) | 71.3 | Dropouts recall 10% worse: the bias moves by −0.7 points as expected (recall dropouts carry 6.6% of the S4 total), still inside 1%. |
| S5x (stress) | **−4.15%** (0.22) | **86.9%** / 86.4% | 7.08% | 0.971 | 0.38 (7%) | 67.8 | **Breaks A7′.** Units that under-report are verified less, so R is biased low. No estimator fix exists for this; it needs field practice (section 3). |

Productivity $\hat P$ follows $\hat Y$ in every scenario (S1: bias +0.12%, coverage 95.0%, boot SE / SD 0.981). No bootstrap replicate failed, no calibration constraint was unmet, no take-all stratum was skipped.

## 3. Against v0.4 (part A, a different synthetic district)

| Scen. | v0.4: bias / coverage / RSE | v0.5: bias / coverage / RSE | Verified units v0.4 → v0.5 |
|---|---|---|---|
| S1 | +0.06% / 94.6% / 7.14% | +0.10% / 95.3% / 6.99% | 54.7 → 70.0 (+28%) |
| S2 | +0.71% / 93.7% / 11.51% | +0.25% / 94.6% / 8.28% | 54.7 → 115.8 (+112%) |
| S4 | **+3.39%** / 94.3% / 7.14% | +0.55% / 96.1% / 6.58% | 54.7 → 70.5 |
| S5 | **−2.42%** / **89.4%** / 6.56% | +0.22% / 94.6% / 7.43% | 54.7 → 72.5 |

The districts differ, so each change mixes the method change with the new district. The review's paired runs on throw-away seeds isolate the method: F1 moves S5 bias from −2.4% to +0.3%, and F2 removes about 2.95 points of the S4 bias.

## 4. Reading

- **S5 and S4 are fixed under their stated assumptions.** F1 needs A7′ (the verified share does not follow the diary error). F2 needs A9′ (dropouts' recall error is like respondents') and A9″ (which dropouts answer the recall is random within the stratum, assumed 70%). S4x shows F2 tolerates a 10% recall shift. S5x shows F1 does not tolerate verification that follows the diary error. The field mitigation for S5x is procedural: unannounced spot checks, and tracking the verified-event share per farmer.
- **S2 is a cost question, not a bias.** The adaptive rule more than doubles verification and brings RSE from 11.5% to 8.3%. Reaching 7.5% would need a higher cap, more selected units, or top-ups verified for the whole year (impossible after mid-year). The design states S2 as a limit with this cost.
- **Adaptivity is not free in S1.** The rule fires in 30.8% of S1 replications (98% in S2; mean ν 0.39 in S1), adding 15.8 top-up units per district on average. The interim prediction is noisy around the 7.5% target.
- **The linearised interval is now a cross-check only.** It does not include the recall-dropout term (by design) and runs low in S5 (93.0%). The bootstrap stays primary and holds in every non-stress scenario.
- **Limits of this run.** One synthetic district; MC SEs cover replication noise only. The S5x and S4x mechanisms are two chosen ways for the assumptions to fail, not all of them.

Files: `replications.csv` (7,000 rows), `metrics.csv`, `config_used.json`, `coverage_plot.png`, `bias_plot.png`, `run_log.txt`, `command.txt`.
