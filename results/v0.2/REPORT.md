# D-32 confirmatory simulation report, design v0.2 (all numbers SIMULATED)

Every number below is **simulated**. The district is synthetic (20,000 listed and 1,600 not-on-list water bodies); nothing here describes real Assam production. Source of the method: `docs/design.md` v0.2 (sections 4.4, 5.2, 6, 8.2, 8.6-8.9, 9, 15.4, 18).

This is the **confirmatory** run of section 15.4: seeds `pop_seed = 20261102` and `master_seed = 4417` (no earlier run used them), 1,000 replications for each of S1-S5, bootstrap (500 replicates) on every replication. Nothing was tuned on these seeds, and nothing was changed after the run started. The v0.1 run is archived in `results/v0.1-exploratory/`. S6 (3 years, rotation, composite estimator) was **not implemented** (optional in the brief).

Truth in this district: **14,439.8 t (simulated)**, of which 431.0 t (3.0%) is not-on-list. Run time 9 min 22 s on 14 workers.

**Headline.** All seven criteria AC1-AC7 are met in S1 as v0.2 defines them. S2-S5 are reported in section 3: the bootstrap interval covers 95.7-96.1% in S2-S4 and 93.1% in S5; E3 bias rises to +4.0% in S4 (dropout depends on yield) and falls to -1.9% in S5. One weak spot in v0.2 itself: the calibration constraints fail in about 29% of replications, always in small strata (section 4, issue 1).

## 1. What changed in the code (v0.1 to v0.2)

| Item | Implementation |
|---|---|
| Propensity model (9 step 1) | Unweighted logit on exactly intercept, log area, assisted, distance/10. No block dummies, no tank term. Ridge 1e-6 (numerical safety only). |
| Calibration (9 step 5) | `estimate.calibrate`: per stratum, linear GREG to frame count `N_h` and frame area `A_h`, g bounded to [0.3, 3] by iterative truncation, at most 20 iterations. A stratum with fewer than 4 respondents calibrates to `N_h` only. A stratum whose constraints do not hold (or with no respondents) is recorded; counts are in `replications.csv` (`cal_failed`). |
| Take-all (4.4) | `design.take_all_units`: largest units with area >= 2 ha, capped at floor(0.1 n) = 20, counted inside n = 200. |
| Allocation (5.2) | kappa removed. |
| Variance (8.6, 8.7) | Primary CI = Rao-Wu bootstrap (500 replicates, `n_h - 1` selected units, `lambda_h = sqrt(1 - f_h)`, whole pipeline re-run including propensity fit, classes and calibration), `t` with `df = m - H_ver`. The linearised SE is the cross-check (`E3lin` rows). |
| Design effect (8.9) | `deff_full` (all weights) and `deff_factors` (phi x g only, per stratum Kish, pooled with respondent counts as weights). |
| Seeds, scenarios | New seeds; S1u dropped. |

Design used (simulated frame, n = 200 selected): 10 strata, of which one is the take-all stratum of **20 units** (68 units in the frame reach 2 ha; only the 20 largest are take-all). Strata (N_h / n_h): pond plain 9,544/27, 3,586/20, 760/19; pond assisted 2,603/14, 2,274/25, 842/52; tank plain 177/10 (three size classes merged); tank assisted 132/7 and 62/6; take-all 20/20. Mean respondents 180.6, mean verified 54.7.

## 2. Results (simulated)

Truth 14,439.8 t. Bias, RMSE and CI width are relative to the truth. "Cov" = 95% CI coverage (Monte Carlo SE in brackets). `E3` uses the bootstrap interval; `E3lin` is the same estimate with the linearised interval. Full table: `metrics.csv`; per-replication output: `replications.csv`.

### S1 (base case)

| Estimator | Rel. bias (MC SE) | Rel. RMSE | Cov | Rel. CI width | RSE empirical | RSE mean estimated |
|---|---|---|---|---|---|---|
| E0 area x 4.89 t/ha | +14.65% | 14.65% | n/a (no CI) | n/a | 0 | n/a |
| E1 recall only | -27.11% (0.23) | 28.05% | 8.0% (0.9) | 26.8% | 7.20% | 9.32% |
| E2 diary only (classes + calibration) | -12.25% (0.16) | 13.30% | 38.7% (1.5) | 21.9% | 5.19% | 6.31% |
| **E3 proposed, bootstrap CI** | **+0.68% (0.22)** | **6.98%** | **96.1% (0.6)** | 29.0% | **6.95%** | 7.14% |
| E3, linearised CI (cross-check) | +0.68% | 6.98% | 95.2% (0.7) | 28.8% | 6.95% | 7.09% |

### S2-S5 (E3; E0-E2 are in `metrics.csv`)

| Scenario | What changed | E3 rel. bias (MC SE) | Cov, bootstrap | Cov, linearised | Rel. RMSE | RSE empirical |
|---|---|---|---|---|---|---|
| S2 | rho 0.7 | +1.62% (0.37) | 96.0% | 92.0% | 11.77% | 11.67% |
| S3 | diary bias -5% / -20% | +0.66% (0.22) | 96.1% | 95.0% | 6.99% | 6.96% |
| S4 | dropout depends on yield | +3.97% (0.22) | 95.7% | 93.6% | 7.96% | 6.90% |
| S5 | 75% of harvest events verified | -1.92% (0.20) | 93.1% | 93.3% | 6.70% | 6.42% |

Plots: `coverage_plot.png` (first 100 E3 bootstrap intervals per scenario, green covers the truth, red misses), `bias_plot.png` (relative bias of E0-E3 per scenario with 1.96 Monte Carlo SE bars).

Other run statistics (S1, means over replications): Kish deff on full weights 2.79; Kish deff on the nonresponse-and-calibration factors only 1.08 (planning value in section 6: 1.2); linearised SE 1,030.5 t, bootstrap SE 1,038.4 t, empirical SD 1,004.1 t; mean estimated undercoverage rate 7.3% (true 7.4%); mean `R_hat` 1.114 (true 1.111); no bootstrap replicate failed; no variance fallbacks.

### v0.1 vs v0.2, E3 in S1

The two runs differ in **both** the method and the seeds (new synthetic district, truth 14,347 t vs 14,440 t), so this table cannot separate the two effects.

| Quantity (S1, E3) | v0.1 exploratory (`results/v0.1-exploratory/`) | v0.2 confirmatory |
|---|---|---|
| Rel. bias | +2.29% | **+0.68%** |
| Rel. RMSE | 7.96% | 6.98% |
| Empirical RSE | 7.63% | 6.95% |
| Coverage, linearised CI | 90.5% | 95.2% |
| Coverage, bootstrap CI | 96.4% (looked at after the results; post hoc) | **96.1%** (pre-specified primary) |
| Mean linearised SE / empirical SD | 0.90 | 1.03 |
| Mean bootstrap SE / empirical SD | 1.03 | 1.03 |
| Kish deff, full weights | 2.5 | 2.79 |
| Kish deff, factors only | not computed | 1.08 |
| Rel. CI width, linearised / bootstrap | 27.6% / 31.6% | 28.8% / 29.0% |

## 3. Acceptance criteria (v0.2 definitions)

| # | Criterion | Status | Evidence (simulated, S1 unless stated) |
|---|---|---|---|
| AC1 | E3 bootstrap-CI coverage between 93% and 97% | **MET** | 96.1% (MC SE 0.6). |
| AC2 | E3 abs. relative bias below 1% | **MET** | +0.68% (MC SE 0.22). The upper end of an approximate 95% band (about 1.1%) is above 1%, so the margin is thin. |
| AC3 | E1 and E0 show their bias; E3 does not | **MET** | E1 -27.11%, E0 +14.65%, E2 -12.25%; E3 +0.68%, which is statistically nonzero (about 3 SE) but below 1%. E0's size depends on my placeholder norm (issue 8). |
| AC4 | Mean bootstrap SE within 10% of the empirical SD of E3 | **MET** | Bootstrap 1,038.4 t vs empirical SD 1,004.1 t: ratio **1.034**. Linearised 1,030.5 t: ratio 1.026. |
| AC5 | E3 RSE <= 7.5% at 200 selected | **MET** | Empirical RSE 6.95%; mean estimated (bootstrap) RSE 7.14%. Both are under 7.5%. |
| AC6 | S2-S5 reported honestly, mitigation named | **MET** | Section 2 table and the mitigations in section 4. No S2-S5 bootstrap coverage fell outside 93-97% (S5 is at 93.1%). |
| AC7 | Same seed and frame give identical output | **MET** | `d32.simulate --reps 30 --scenarios S1` run twice: `replications.csv` SHA-256 `44a7f217...1911e`, `metrics.csv` `7bf39ed8...888b`, identical in both runs (`cmp`: byte-identical). Tests also check repeat runs with the bootstrap and serial vs parallel. |

## 4. Diagnosis and mitigations (not applied)

Proposals below are owner decisions. I applied none of them.

1. **Calibration constraints fail in small strata.** In 28.7% of S1 replications at least one stratum (up to 3) misses its `N_h` or `A_h` constraint, and in 77.5% a calibration factor sits at a bound (0.3 or 3). A 200-replication diagnostic (S1, run in a throwaway script, not part of the results) put the failures in the small tank strata with 6-10 selected units (strata 6, 7, 8: 17, 18 and 24 failures), and a few in stratum 2 (5) and 3 (1). With about 5 respondents, two constraints cannot be met with g in [0.3, 3]. Mitigation to consider: raise the "calibrate to `N_h` only" respondent threshold above 4, or collapse the small tank strata further. This does not break the S1 criteria, but it makes calibration weaker exactly where the strata are thin.
2. **S4 (dropout depends on yield).** Bias +3.97%, coverage 95.7%: the bootstrap interval is wide enough to absorb the bias, but the bias is real (about 5.7 SE). Frame variables cannot see a yield shock. Named mitigation (design.md 9, A9): compare recall of dropouts with recall of respondents, and report a sensitivity estimate. Not simulated.
3. **S2 (rho 0.7).** RSE rises to 11.7%, well above 7.5%; the bootstrap interval still covers 96.0%, the linearised one only 92.0%. Mitigation: verify more units (raise nu) or select more units.
4. **S5 (75% of harvest events verified).** Bias -1.92% (about 10 SE), coverage 93.1%, at the bottom of the 93-97% band. Unverified events fall back to the diary value, which pulls `R_hat` down (1.085 vs 1.114, a 2.6% drop). In v0.1 this effect was masked by an opposite +2.3% nonresponse bias; with that bias largely removed, S5's own bias shows. Mitigation: announcement discipline for phase-2 harvests (A7) and reporting the verified-event share per unit.
5. **S3.** Combined ratio stays unbiased (+0.66%, same as S1): phase 2 is a random subsample of the same population, so one ratio is right for the total even when diary bias differs by group. The separate-ratios fallback (>= 20 verified per calibration group) was **not tested**; with about 55 verified and about 30% assisted, the assisted group has about 16 verified, below the doc's own condition.

## 5. Design doc issues (reading chosen)

1. **Calibration failure rule.** The doc says to log strata where constraints fail but not what weights to use then. I keep the truncated g from the last iteration, so the stratum does not match `A_h`. Frequency in section 4, item 1. A stratum with zero respondents gets no weights and is logged.
2. **Take-all stratum is calibrated too.** The doc calibrates "each stratum h"; I applied it to the take-all stratum as well, so a non-responding take-all unit is replaced by reweighting the others.
3. **Take-all vs the top size class.** Only 20 of the 68 units >= 2 ha become take-all (cap); the other 48 stay in the sampled strata (the top pond and tank size classes), where their inclusion probability is small. The doc's cap makes this the rule; it may deserve a comment in section 4.4.
4. **E2 definition.** The doc says "diary-only stratified expansion". I use the same weights as E3 (classes and calibration), so E2 differs from E3 only by the missing verification step. E1 uses recall of all selected units; E0 uses frame area x 4.89 t/ha (my placeholder from one of three published totals; the synthetic truth is 4.09 t/ha, so E0's +14.65% is partly an artefact of that choice).
5. **8.9 form (b) "pooled over strata".** I compute Kish deff of phi x g inside each stratum and pool with respondent counts as weights. The doc does not give the pooling formula.
6. **AC5.** The doc does not say whether RSE means the true SD or the estimated SE. I report both (6.95% and 7.14%); both pass.
7. **Linearised cross-check is unchanged** from v0.1: it does not use calibration. It still agrees with the empirical SD here (ratio 1.03), but the formula has no calibration or nonresponse term, and it covered only 92.0% in S2.
8. **Planning CV.** The synthetic district has a pooled within-group CV of about 1.6 (heavier tailed than the 0.7 of section 6); the section 6 table is not tested at that CV.
9. **v0.1 code is not preserved.** Nothing is committed, so v0.2 overwrote the v0.1 code; only the v0.1 results are archived.
10. **Not implemented** (outside the brief): productivity estimate (8.8), Fay-Herriot, plausibility checks, commit-reveal and audit log, S6 with PRN rotation.

## 6. Synthetic-data checks (simulated)

Listed mean area 0.169 ha (target 0.17); tanks 1.9% of listed units; assisted 29.6%. Realised pooled within-group corr(diary, truth): 0.93 in S1 (target 0.9), 0.66 in S2 (target 0.7; one draw, noisy because of the heavy tail); recall 0.62 (assumption 0.6).

## 7. Commands run and outputs

| Command | Output |
|---|---|
| `.venv\Scripts\python -m pytest -q` (after the last code change) | 34 passed in 30.7 s (23 earlier tests plus 11 new in `tests/test_v02.py`) |
| `python -u -m d32.simulate --reps 1000 --scenarios S1,S2,S3,S4,S5 --out results/v0.2 --workers 14` | tables above; `metrics.csv`, `replications.csv` (5,000 rows), `config_used.json` (seeds 20261102 and 4417), two PNGs, `run_log.txt`; real time 9 min 22.7 s |
| AC7: `python -m d32.simulate --reps 30 --scenarios S1 --out <dir> --workers 4 --no-plots`, twice | identical SHA-256 for both CSV files (see AC7) |

New tests (`tests/test_v02.py`): calibration reproduces `N_h` and `A_h` and respects the bounds; failure is logged when bounds make it infeasible; strata with fewer than 4 respondents calibrate to `N_h` only; take-all rule on a small frame and inside the design total; a take-all stratum adds zero bootstrap variance (both in `rao_wu` and through the whole `bootstrap_e3` pipeline); the propensity model is unweighted and has exactly three variables; Kish form (b) ignores intended Neyman weight differences.
