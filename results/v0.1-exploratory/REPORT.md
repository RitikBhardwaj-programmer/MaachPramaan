> **Archived v0.1 exploratory run.** The switch to the bootstrap interval as the primary CI (section 8 and the AC1 "met" below) was made after the results were seen, so that AC1 "met" is post hoc.

# D-32 simulation report (all numbers SIMULATED)

Every number below comes from a **simulated** synthetic district (20,000 listed + 1,600 not-on-list water bodies, parameters in `src/d32/config.py`, copy in `results/config_used.json`). Nothing here describes real Assam production. Design source: `docs/design.md` v0.1, sections 3-9, 12, 13, 15.

Run: `python -m d32.simulate --reps 1000 --scenarios S1,S2,S3,S4,S5,S1u --out results --workers 14` (6 min 32 s). 1,000 replications per scenario, bootstrap (500 replicates) on every replication. Seeds: `pop_seed=20261101`, `master_seed=2026`. The truth is the true district total including the not-on-list units: **14,347.5 t (simulated)**; of this, 424.6 t (3.0%) is not-on-list.

**Headline.** The design's bias claims about E0, E1 and E2 hold. For the proposed estimator E3: AC2 (bias) and AC4 (linearised vs bootstrap SE) are **not met**, AC5 is a near miss, and AC1 (coverage) is met only with the bootstrap interval, which section 8 adopts as the primary CI (the linearised interval gets 90.5%). Causes are diagnosed below; no parameter was tuned. S6 (3 years, rotation, composite estimator) was **not implemented** (the brief made it optional).

## 1. What was built

| File | Role |
|---|---|
| `src/d32/config.py` | one dataclass with every parameter, each tagged DOC / SOURCED / ASSUMPTION; scenario overrides S1-S5 |
| `synth.py` | synthetic district (section 15.1), rho calibration, dropout model |
| `design.py` | cumulative sqrt-f size classes, take-all, Neyman allocation, collapse rule |
| `select.py` | HMAC-SHA256 PRN selection, phase-2 subsample, `SeedSequence(...).spawn` streams |
| `nonresponse.py` | logistic propensity (own IRLS, checked against statsmodels), 5 classes, phi cap 2 |
| `estimate.py`, `variance.py` | E0-E3; linearised variance; Rao-Wu bootstrap |
| `simulate.py` | runner, metrics, plots |
| `tests/` | 23 tests (PRN order-independence, AC7 reproducibility, allocation, take-all, hand-computed ratio and variance, Hypothesis weight property) |

Only numpy, pandas, scipy, statsmodels, matplotlib, pytest, hypothesis are used. Config is a dataclass, not YAML (PyYAML is not on the allowed list). A virtual environment `.venv/` was created inside the folder (git-ignored).

Frame design used (simulated frame, n = 200 selected): 9 strata after the collapse rule, 0 take-all units. Allocation: pond/plain 28+21+22, pond/assisted 14+26+59, tank/plain 10 (3 size classes merged), tank/assisted 8+12. Expected response 179.2, verified 54.1 (the "min 2 verified per stratum" rule lifts verification from 30% to 27% of selected, i.e. 54 vs 50 planned), Kish deff_w about 2.5 (planning value in section 6 was 1.2).

## 2. Results (simulated)

Truth 14,347.5 t. Bias, RMSE and CI width are relative to the truth. "Cov" is 95% CI coverage with its Monte Carlo SE (1,000 reps). E0 is a point estimate with no CI. Full table: `results/metrics.csv`.

### S1 (base case)

| Estimator | Rel. bias | Rel. RMSE | Cov (MC SE) | Rel. CI width | RSE empirical | RSE mean estimated |
|---|---|---|---|---|---|---|
| E0 area x 4.89 t/ha | +13.2% | 13.2% | n/a | n/a | 0 | n/a |
| E1 recall only | -27.2% | 28.1% | 7.8% (0.9) | 25.7% | 6.9% | 9.0% |
| E2 diary only | -11.0% | 12.4% | 47.0% (1.6) | 21.6% | 5.8% | 6.2% |
| **E3 proposed, linearised CI** | **+2.29% (MC SE 0.24)** | 8.0% | **90.5% (0.9)** | 27.6% | 7.63% | 6.69% |
| E3, bootstrap-SE CI (cross-check) | +2.29% | 8.0% | 96.4% (0.6) | 31.6% | 7.63% | 7.68% |

### S2-S5 and the S1u sensitivity run (E3 only; E0-E2 in the CSV)

| Scenario | What changed | E3 rel. bias | E3 cov (linearised) | E3 cov (bootstrap SE) | E3 rel. RMSE | E3 RSE empirical |
|---|---|---|---|---|---|---|
| S1u (extra, not in S1-S5) | propensity fit unweighted | +1.05% | 91.6% | 96.9% | 7.4% | 7.4% |
| S2 | rho 0.7 | +3.03% | 89.5% | 96.7% | 11.9% | 11.5% |
| S3 | diary bias -5% / -20% | +2.33% | 89.9% | 96.0% | 8.1% | 7.7% |
| S4 | dropout depends on yield | +5.25% | 88.2% | 95.4% | 9.2% | 7.6% |
| S5 | 75% of harvest events verified | -0.34% | 90.9% | 96.2% | 7.0% | 7.0% |

Plots: `results/coverage_plot.png` (first 100 E3 intervals per scenario, green covers the truth, red misses; the misses in S1 sit mostly to the right of the truth, as a positive bias would give) and `results/bias_plot.png` (E0-E3 relative bias by scenario with Monte Carlo error bars). Per-replication output: `results/replications.csv`.

## 3. Acceptance criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| AC1 | E3 coverage in S1 between 93% and 97% | **MET with the bootstrap interval (primary, section 8); NOT MET with the linearised interval** | Linearised 90.5% (MC SE 0.9); bootstrap-SE interval 96.4% (MC SE 0.6). |
| AC2 | E3 abs. relative bias < 1% in S1 | **NOT MET** | +2.29% (MC SE 0.24), about 9 SE from zero. With an unweighted propensity fit (S1u) it is +1.05%, still above 1%. |
| AC3 | E1 and E0 show bias in S1, E3 does not | **PARTLY MET** | E1 -27.2%, E0 +13.2%, E2 -11.0%: shown. E3 is much smaller (+2.3%) but not zero (see AC2). E0's bias is partly a product of my placeholder norm (issue 9 below). |
| AC4 | Linearised SE and bootstrap SD within 10% on average, S1 | **NOT MET** | Mean linearised SE 981.5 t, mean bootstrap SE 1,126.6 t; ratio of means 1.148, mean of ratios 1.180. The bootstrap SE (7.68% of the estimate) agrees with the empirical SD of E3 (7.63%); the linearised one (6.69%) is about 12% too low. |
| AC5 | E3 RSE <= 7.5% at 200 selected, S1 | **NOT MET (near miss)** | The method's own mean estimated RSE is 6.69% (would pass), but the true sampling SD is 7.63% of the truth. I count the empirical value, because the estimated one is the understated quantity. |
| AC6 | S2-S5 reported honestly, mitigation named | **MET** | Section 2 and section 4 below. Coverage fails in all four (88-91%). |
| AC7 | Same seed and frame give identical samples and estimates | **MET** | `d32.simulate --reps 30 --scenarios S1` run twice: `replications.csv` SHA-256 `c865a6ad...f942` both times (`cmp`: byte-identical), `metrics.csv` also identical. Tests `test_repro.py` check serial vs parallel and repeat runs with the bootstrap. |

## 4. Diagnosis (nothing tuned)

1. **Coverage failure (AC1, AC4) is mainly variance underestimation.** The linearised SE is about 12% below the true SD; the bias adds a smaller part (bias is 0.3 SD, which alone would cost roughly one coverage point). The section 8.6 formula has no term for the nonresponse phase and treats propensity-class weights as if they were `N_h/n'_h`. Kish deff_w is 2.5 here, against the planning value 1.2 used in section 6, so the weights really do cost more than planned. The linearised formula also takes `s2_y` from about 4 verified units per stratum, and ignores the covariance between `R` and `R_rec`. The Rao-Wu bootstrap re-runs the whole pipeline and gets the SD right (7.68% vs 7.63%) and covers 96.4%. **Suggested mitigation (an owner decision, not applied):** make the bootstrap interval the primary one and keep the linearised SE as the cross-check, or add a nonresponse-phase term to 8.6.
2. **Bias (AC2).** With full response the bias is -0.18% (diagnostic run, 400 reps, MC SE about 0.4%), so selection, weights and the ratio estimator are sound. The bias comes from the propensity-class step: 1 class gives +6.1%, 5 classes +2.1%, 20 classes +2.2% on the list part. More classes do not help, so the propensity model's ranking is too noisy with about 200 rows and 14 parameters. An unweighted fit cuts it to about 1% (run as S1u after seeing this; see issue 6). I did **not** switch the primary run to the unweighted fit, to avoid choosing the method after seeing the outcome. These diagnostic runs were ad-hoc scripts, not saved in the repo.
3. **S2 (rho 0.7).** RSE rises to 11.5%, far above 7.5%. Mitigation: verify more units (raise nu) or select more units; section 6 shows the sample size is sensitive to rho. Coverage 89.5%.
4. **S3 (different diary bias by group).** E3 bias is the same as S1 (+2.3%) and coverage 89.9%. The combined ratio stays unbiased for the total here because phase 2 is a random subsample of the same population. The separate-ratios fallback (>= 20 verified per calibration group) was **not tested**: with about 54 verified units and about 30% assisted, the assisted group has about 16, which fails the doc's own condition.
5. **S4 (dropout depends on yield).** Worst case: bias +5.3%, coverage 88.2%. A9 fails as expected; propensity classes on frame variables cannot see a yield shock. Mitigation named in the doc and not simulated: compare recall of dropouts with recall of respondents, and report a sensitivity estimate.
6. **S5 (75% of harvest events verified).** Bias -0.3% looks good but is a **cancellation**: unverified events fall back to the diary value, which pulls `R` down (1.087 vs 1.116 in S1, a 2.6% drop) and offsets the +2.3% nonresponse bias. Do not read S5 as harmless. Mitigation: announcement discipline and a verified-event share reported per unit (A7).

## 5. Design doc issues (reading chosen in each case)

1. **Take-all rule (4.4) never fires.** At 200 of 20,000 units, a unit needs a size above about 100 times the mean to get inclusion probability > 1. Result: 0 take-all units in the simulation (unit-level rule, cap 10%). The take-all code is tested on small frames only (`test_design.py`). Also, 4.4 caps take-all at 10% of the district sample, while section 6 says "200 per district plus the take-all units"; I used **200 in total including take-all** (fewer units, the conservative reading). The stratum-level rule in 5.2 step 2 (n_h > N_h) is implemented separately and also did not fire.
2. **kappa (5.2) cancels** in Neyman allocation (it multiplies every S_h), so it has no effect on `n_h`.
3. **Collapse (4.5) and "raise to 5" (5.2 step 3) overlap.** I applied collapse first (frame < 20 or planned n_h < 5), merging with the next size class, and only then rounded with a minimum of 5. Three tank strata collapsed.
4. **Variance 8.6 is incomplete** (see diagnosis 1). I implemented it literally and added the simplified `R_rec` term: `V(R_rec)` from the verified units of each stratum as if the phase-2 sample were a single-phase stratified sample. `V(Y_NL) = R_rec^2 V(H) + H^2 V(R_rec)`; the covariance between `R_hat` and `R_rec` is ignored as the doc implies (3.4 and 8.5).
5. **Bootstrap (8.7)** says to resample `n'_h - 1` respondents, but re-running the nonresponse classes needs the nonrespondents. I resample the `n_h - 1` *selected* units, with the Rao-Wu fpc form `w* = w(1 - lam + lam (n/m) t)`, `lam = sqrt(m(1-f)/(n-1))`. Area-frame cells are resampled the same way. The propensity model is refitted in every replicate.
6. **Propensity fit (9)** does not say whether it is weighted. I used the survey-weighted fit (robust to misspecification) before seeing results, with a ridge of 0.01. S1u shows an unweighted fit is better here (bias 1.05% vs 2.29%). The size of this effect means it should be decided deliberately.
7. **Phase-2 size.** The doc gives nu = 0.3 and needs >= 2 verified per stratum; I used `m_h = max(2, round(0.3 n'_h))`, so 54 verified rather than 50.
8. **A7 in S1.** A7 says "at least 90%" of phase-2 harvests are verified; S1 uses 100% (assumption holds exactly). A 90% sensitivity run was **not** done; S5 (75%) is the only partial-verification case.
9. **E0, E1, E2 definitions are mine.** E0 = listed area x 4.89 t/ha (4.74 lakh t / 96,968.86 ha, one of the three published totals). The synthetic truth is 4.14 t/ha, so E0's +13.2% bias follows from my placeholder productivities and says little about the real method. E1 uses recall of all selected units, list frame only. E2 uses the same nonresponse classes as E3, list frame only. Neither has the not-on-list domain.
10. **Planning CV.** Section 6 plans with CV = 0.7 inside strata. My synthetic district (lognormal area with log-sd 1.0, production noise 0.5) has a pooled within-group CV of about 1.6, much heavier tailed, so the section 6 sample-size table is not tested at the assumed CV.
11. **Not implemented** (outside the brief): productivity estimate 8.8, Fay-Herriot, plausibility checks, commit-reveal and the hash-chained log, S6 and the PRN rotation. Kish deff is computed (8.9) and stored in `replications.csv`.

## 6. Synthetic-data checks (simulated)

- Listed mean area 0.166 ha (target 0.17), tanks 1.7% of listed units, assisted 30.3%.
- Realised pooled within-group corr(diary, truth): 0.92 in S1 (target 0.9); in S2 it came out at 0.65 for one draw (target 0.7) because the heavy tail makes sample correlations noisy. Recall corr 0.68 (assumption 0.6).
- Mean estimated undercoverage rate 7.3% (true 7.4%).
- Mean `R_hat` 1.116 (true 1.111), mean `R_rec_hat` 1.356 (true 1.333).

## 7. Commands run and outputs

| Command | Output |
|---|---|
| `.venv\Scripts\python -m pytest -q` | 23 passed (last run after the final edit; see end of this section) |
| `python -m d32.simulate --reps 1000 --scenarios S1,S2,S3,S4,S5,S1u --out results --workers 14` | tables above, `metrics.csv`, `replications.csv`, two PNGs, run time 6 min 32 s |
| AC7: `python -m d32.simulate --reps 30 --scenarios S1 --out <dir> --workers 4 --no-plots` twice | identical SHA-256 for `replications.csv` (`c865a6ad...f942`) and `metrics.csv` (`3045a87b...7033`) |

## 8. Follow-up: bootstrap interval as the primary E3 CI (applied after review, no re-run)

Decision: report the Rao-Wu bootstrap-SE interval (`E3boot` rows in `metrics.csv`, `E3boot_*` columns in `replications.csv`) as the primary E3 interval, and keep the linearised SE as the cross-check. The method, the estimates and the simulated samples are unchanged; only the interval changes. The numbers already existed from the 1,000-replication run, so nothing was re-simulated.

| Scenario | Linearised CI cov | **Bootstrap CI cov (primary)** | Within 93-97%? |
|---|---|---|---|
| S1 | 90.5% | **96.4%** | yes |
| S1u | 91.6% | 96.9% | yes |
| S2 | 89.5% | 96.7% | yes |
| S3 | 89.9% | 96.0% | yes |
| S4 | 88.2% | 95.4% | yes |
| S5 | 90.9% | 96.2% | yes |

Effect on the acceptance criteria (S1):
- **AC1 becomes MET** with the bootstrap interval (96.4%, MC SE 0.6). Under the linearised interval it is still not met (90.5%).
- **AC2** is unchanged (the estimate has the same +2.29% bias; only the interval changed). **AC4 stays not met** by definition: the two SEs still differ by 15-18%.
- **AC5 stays not met**: the bootstrap RSE is 7.68%, above 7.5%.
- The bootstrap CI is wider (31.6% of the truth vs 27.6%) and costs 500 pipeline re-runs per estimate (about 0.3 s per estimate here).
- Caveat: coverage near 96% rests on a bias of +2.3%; the interval is wide enough to absorb it, but the bias itself is not fixed. In S4 (bias +5.3%) coverage still reaches 95.4%, but with a larger bias that margin would shrink.
- The nonresponse-phase variance term for the linearised formula was **not** added; that stays an open option.

To reproduce: `py -3 -m venv .venv`, install numpy pandas scipy statsmodels matplotlib pytest hypothesis, set `PYTHONPATH=src`, run the command above.
