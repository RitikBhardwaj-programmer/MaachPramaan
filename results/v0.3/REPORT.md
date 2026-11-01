# D-32 post-confirmation check, design v0.3 (all numbers SIMULATED)

**This is a post-confirmation check, not a confirmatory run.** The confirmatory record stays `results/v0.2/REPORT.md`. Every number below is **simulated** (synthetic district, nothing about real Assam production). Spec: `docs/design.md` section 19 (v0.3), plus sections 9 step 5, 4.4 and 17. I found no conflict between the brief and the doc.

Seeds fixed in section 19 before the run: `pop_seed = 20261103`, `master_seed = 5521` (new; passed with `--pop-seed` / `--master-seed`). 1,000 replications each for S1-S5, bootstrap (500 replicates) on every replication. Nothing was tuned on these seeds. Two runs on **identical samples** (same selected units, responses, verification, measurement noise; checked column by column for truth, E0, E1, `n_resp`, `n_ver`): the v0.3 rule in `results/v0.3/`, and the v0.2 rule in `results/v0.3-v02rule/` (comparison only). S6 was not run (optional). True district total in this synthetic district: **14,838.5 t (simulated)**.

**Headline.** V1, V2, V3 and V4 are met. V1 is met with room (0.0% vs a 5% limit). V2 holds, but E3 coverage in S1 is 93.6%, only 0.6 points above the lower edge of the 93-97% band (Monte Carlo SE 0.8). On the same samples the v0.3 rule cuts S1 bias from +0.55% to +0.09% and removes every unmet calibration constraint, but it lowers coverage in all five scenarios (by 0.2 to 2.2 points) because the bootstrap SE sits about 2% below the empirical SD. In S5, bootstrap coverage is 90.7% under v0.3 (92.9% under the v0.2 rule).

## 1. What changed in the code

| Change | Where |
|---|---|
| `cal_min_resp` 4 to 8: a stratum with fewer than 8 respondents calibrates to `N_h` only | `src/d32/config.py` |
| Fallback: a stratum calibrated to `N_h` and `A_h` that still misses after 20 iterations is redone with `N_h` only (`cal_fallback = True`) | `src/d32/estimate.py` (`calibrate_detail`; `calibrate` keeps its old 2-value return) |
| Counts per replication in `replications.csv`: `cal_failed` (any miss before fallback, the v0.2 definition, zero-respondent strata included), `cal_fallback`, `cal_unmet_after` (V1: an attempted constraint still unmet after the fallback; zero-respondent strata excluded), `cal_zero_resp`, `cal_at_bound` (a factor at 0.3 or 3 among respondents) | `estimate.py`, `simulate.py` |
| Rule switch and seed flags: `--cal-rule v0.2` sets `cal_min_resp = 4`, `cal_fallback = False`; `--pop-seed`, `--master-seed`. Default rule = v0.3. Defaults of the seeds in `config.py` are unchanged (v0.2 values). The effective config of each run is in its `config_used.json`. | `simulate.py`, `config.py` |

Tests: 42 pass (34 earlier plus 8 new in `tests/test_v03.py`: threshold 7 vs 8 respondents, v0.2 threshold 4, fallback, v0.2 rule without fallback, fallback that also fails is logged, zero-respondent stratum, run overrides). **One existing test was adjusted**: `test_calibration_respects_bounds_and_logs_failure` in `tests/test_v02.py` encoded the v0.2 no-fallback behaviour, so it now runs under the v0.2 rule (`cal_min_resp=4, cal_fallback=False`); its assertions are unchanged. No test encoded the old threshold of 4 as such.

## 2. Results, S1 (simulated)

Truth 14,838.5 t. Bias and RMSE are relative to the truth; Cov is 95% CI coverage, Monte Carlo SE in brackets. `E3` uses the bootstrap interval; `E3lin` is the linearised cross-check.

| Estimator (v0.3 rule) | Rel. bias | Rel. RMSE | Cov | RSE empirical |
|---|---|---|---|---|
| E0 area x 4.89 t/ha | +13.82% | 13.82% | n/a | 0 |
| E1 recall only | -26.77% | 27.81% | 10.8% | 7.54% |
| E2 diary only | -12.44% | 13.52% | 38.9% | 5.31% |
| **E3, bootstrap CI** | **+0.09% (MC SE 0.22)** | 7.00% | **93.6% (0.8)** | **7.00%** |
| E3, linearised CI | +0.09% | 7.00% | 94.1% (0.7) | 7.00% |

S1 means for E3: bootstrap SE 1,014.2 t, linearised SE 1,045.0 t, empirical SD 1,038.6 t; mean estimated RSE 6.83%; Kish deff 2.77 (all weights) and 1.06 (phi x g factors); 179.9 respondents, 55.1 verified; no bootstrap replicate failed.

## 3. Criteria

| # | Criterion | Status | Evidence (simulated, S1) |
|---|---|---|---|
| V1 | Replications with any attempted calibration constraint unmet after the fallback <= 5% | **MET** | **0.0%** (0 of 1,000; max 0 strata). Also reported: any miss before fallback (v0.2 definition) **18.6%** (mean 0.2 strata per replication), fallback used 18.6%, factor at a bound **57.0%**, zero-respondent strata 0 replications. Same samples under the v0.2 rule: any miss 35.9% (all unmet, no fallback), factor at a bound 78.5%. |
| V2 | AC1-AC5 hold again on the new seeds | **MET (AC1 narrowly)** | AC1 coverage **93.6%** (band 93-97%, MC SE 0.8: inside, but not distinguishable from the edge). AC2 bias **+0.09%** (< 1%). AC3 E0 +13.82% and E1 -26.77% show their bias, E3 does not. AC4 bootstrap SE / empirical SD = **0.976** (within 10%; linearised 1.006). AC5 empirical RSE **7.00%**, estimated 6.83% (both <= 7.5%). |
| V3 | S2-S5 reported with the change against v0.2 | **MET** | Section 4 tables. |
| V4 | Byte-identical rerun (AC7) | **MET** | `d32.simulate --reps 30 --scenarios S1 --pop-seed 20261103 --master-seed 5521 --out <dir> --workers 4 --no-plots` run twice: `replications.csv` SHA-256 `1514bd20...d5cc` and `metrics.csv` `d86422d1...c407` identical in both runs (`cmp`: byte-identical). |

## 4. v0.2 rule vs v0.3 rule on the new seeds (E3, simulated)

Same samples, only the calibration step differs. Bias with its Monte Carlo SE; `Cov` = bootstrap-CI coverage; `Boot/emp` = mean bootstrap SE / empirical SD; miss rates are the share of replications.

| Scen. | Rule | Rel. bias (SE) | Cov (boot) | Cov (lin) | RSE emp. | RSE est. | Boot/emp | Any miss before fallback | Fallback used | Unmet after | Factor at bound |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | v0.2 | +0.55% (0.22) | 95.1% | 93.4% | 7.08% | 7.07% | 1.004 | 35.9% | 0% | 35.9% | 78.5% |
| S1 | **v0.3** | **+0.09% (0.22)** | **93.6%** | 94.1% | 7.00% | 6.83% | 0.976 | 18.6% | 18.6% | **0.0%** | 57.0% |
| S2 | v0.2 | +1.21% (0.36) | 95.1% | 90.9% | 11.47% | 11.20% | 0.989 | 35.9% | 0% | 35.9% | 78.5% |
| S2 | v0.3 | +0.73% (0.36) | 94.2% | 91.3% | 11.29% | 10.81% | 0.964 | 18.6% | 18.6% | 0.0% | 57.0% |
| S3 | v0.2 | +0.55% (0.22) | 94.9% | 93.3% | 7.09% | 7.13% | 1.011 | 35.9% | 0% | 35.9% | 78.5% |
| S3 | v0.3 | +0.09% (0.22) | 93.8% | 94.2% | 7.00% | 6.87% | 0.982 | 18.6% | 18.6% | 0.0% | 57.0% |
| S4 | v0.2 | +3.96% (0.22) | 95.7% | 92.1% | 7.11% | 7.05% | 1.031 | 35.7% | 0% | 35.7% | 78.1% |
| S4 | v0.3 | +3.47% (0.22) | 95.5% | 93.0% | 7.04% | 6.78% | 0.997 | 18.1% | 18.1% | 0.0% | 54.7% |
| S5 | v0.2 | -1.90% (0.20) | 92.9% | 93.2% | 6.35% | 6.65% | 1.026 | 35.9% | 0% | 35.9% | 78.5% |
| S5 | v0.3 | -2.35% (0.20) | **90.7%** | 92.4% | 6.26% | 6.41% | 1.000 | 18.6% | 18.6% | 0.0% | 57.0% |

Reading (inference, not tested beyond this table): the fix does what it was built for on calibration (no unmet constraint, half as many first-attempt misses). It lowers the bias in S1-S4. In every scenario it also lowers the empirical SD and the bootstrap SE slightly, and the bootstrap SE falls a little more, so coverage drops by 0.2 to 2.2 points. In S5 it also moves the bias further from zero (-1.90% to -2.35%), which fits the S5 mechanism (unverified events pull `R` down) no longer being offset by a positive calibration bias.

## 5. S2-S5 against the v0.2 confirmatory run (V3)

The v0.2 numbers are from `results/v0.2/REPORT.md` (seeds 20261102 / 4417, a different synthetic district), so each change mixes the rule change with the new seeds. The section 4 table (same samples) isolates the rule.

| Scen. | v0.2 confirmatory: bias / bootstrap cov / RSE emp. | v0.3 check (new seeds): bias / bootstrap cov / RSE emp. | Comment |
|---|---|---|---|
| S1 | +0.68% / 96.1% / 6.95% | +0.09% / 93.6% / 7.00% | Coverage 2.5 points lower; at the band's lower edge. |
| S2 (rho 0.7) | +1.62% / 96.0% / 11.67% | +0.73% / 94.2% / 11.29% | RSE far above 7.5% in both; mitigation unchanged: verify or select more units. |
| S3 (diary bias by group) | +0.66% / 96.1% / 6.96% | +0.09% / 93.8% / 7.00% | Combined ratio still unbiased. |
| S4 (dropout depends on yield) | +3.97% / 95.7% / 6.90% | +3.47% / 95.5% / 7.04% | Bias remains; A9 check (recall of dropouts) still not simulated. |
| S5 (75% of events verified) | -1.92% / 93.1% / 6.42% | -2.35% / **90.7%** / 6.26% | **Coverage falls below 93%.** S5 is not a formal pass/fail criterion, but the interval is no longer reliable when verification drops to 75%. Mitigation named in the doc (A7): announcement discipline, verified-event share per unit. |

## 6. Notes and issues

1. **Coverage under v0.3 is at the edge.** 93.6% in S1 meets V2, and the Monte Carlo SE (0.8 points) means a true coverage of 92-95% cannot be excluded. Coverage was 96.1% on the v0.2 seeds and 95.1% under the v0.2 rule on these seeds, so the v0.3 rule costs about 1.5 points on identical samples (S1). I report it without change; I did not tune anything.
2. **A factor at a bound in 57% of replications** (78.5% under the v0.2 rule): with the fallback, the remaining bounded factors are in strata that still calibrate; this does not break V1 (V1 counts unmet constraints, not bounds). I did not look at which strata.
3. **`cal_failed`** keeps the v0.2 meaning (any miss before fallback), so it is comparable with `results/v0.2/` (28.7% on the v0.2 seeds, 35.9% for the v0.2 rule on the new seeds).
4. **Take-all cap (doc section 17, item 5)** is unchanged and was not tested, as section 19 says.
5. **v0.2 code** is the same code with the old settings (`--cal-rule v0.2`), so the comparison is reproducible.

## 7. Commands run and outputs

| Command | Output |
|---|---|
| `.venv\Scripts\python -m pytest -q` (after the last code change) | 42 passed in 56.6 s |
| `python -u -m d32.simulate --reps 1000 --scenarios S1,S2,S3,S4,S5 --pop-seed 20261103 --master-seed 5521 --cal-rule v0.3 --out results/v0.3 --workers 14` | `results/v0.3/`: `metrics.csv`, `replications.csv` (5,000 rows), `config_used.json`, two PNGs, `run_log.txt` |
| same with `--cal-rule v0.2 --out results/v0.3-v02rule` | `results/v0.3-v02rule/` (same files; comparison only) |
| V4: `python -m d32.simulate --reps 30 --scenarios S1 --pop-seed 20261103 --master-seed 5521 --out <dir> --workers 4 --no-plots`, twice | identical SHA-256 for both CSV files (see V4) |

Nothing is committed. `docs/design.md` was not edited.
