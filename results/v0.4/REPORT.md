# Part A main run, design v0.4 (all numbers SIMULATED)

**Every number below is simulated** (synthetic district, nothing about real Assam production). Spec: `docs/design.md` sections 21.1 (take-all phase-2 variance, T3) and 21.2 (productivity, P1 to P4). Seeds fixed in section 21 before any run: `pop_seed = 20261104`, `master_seed = 6609` (part A). The plausibility checks used the same seeds in a separate run (`results/v0.4-plausibility/`); that run drew its own replication streams and changed nothing here. Nothing was tuned on these seeds.

1,000 replications each for S1 to S5, bootstrap (500 replicates) on every replication, v0.3 calibration rule, take-all phase-2 resampling on, productivity on. True district total in this synthetic district: **14,935.8 t**; true productivity **4.156 t/ha** (both simulated).

    python -m d32.simulate --reps 1000 --v04 --pop-seed 20261104 --master-seed 6609 --workers 12 --out results/v0.4

**Headline.** T3 (AC1 to AC5) and P1 to P3 are met in S1, all with room. E3 coverage is 94.6% (MC SE 0.7), bias +0.06%, bootstrap SE / empirical SD 0.979. Productivity: coverage 94.7%, bias +0.04%, ratio 0.972. S5 (75% of events verified) stays the weak case: coverage 89.4% for the total and 89.7% for productivity.

## 1. T3: AC1 to AC5 in S1 (judged as a replication on a new district)

| # | Criterion | Measured | Result |
|---|---|---|---|
| AC1 | E3 bootstrap CI coverage 93% to 97% | **94.6%** (MC SE 0.7) | met |
| AC2 | E3 absolute relative bias below 1% | **+0.06%** (MC SE 0.23) | met |
| AC3 | E0 and E1 show their bias, E3 does not | E0 +13.05%, E1 −27.09%, E3 +0.06% | met |
| AC4 | Mean bootstrap SE within 10% of the empirical SD | **0.979** (1,044 t / 1,067 t); linearised 1.032 | met |
| AC5 | RSE at most 7.5% | empirical **7.14%**, mean estimated 6.99% | met |

Diagnostics (S1 means): 180.2 respondents, 54.7 verified; no bootstrap replicate failed; no calibration constraint unmet after the fallback; no take-all stratum skipped for $m_h < 2$.

## 2. P1 to P4: productivity $\hat P = \hat Y / \hat A$

| # | Criterion | Measured (S1) | Result |
|---|---|---|---|
| P1 | Absolute relative bias below 1% | **+0.04%** (MC SE 0.23) | met |
| P2 | Bootstrap coverage 93% to 97% | **94.7%** (MC SE 0.7); linearised 94.1% | met |
| P3 | Bootstrap SE within 10% of the empirical SD | **0.972**; linearised 1.026 | met |
| P4 | S2 to S5 reported | section 3 | met |

## 3. S2 to S5 (AC6, P4)

| Scen. | E3 bias (MC SE) | E3 cov boot / lin | E3 RSE emp. | E3 boot/emp | P bias | P cov boot | P boot/emp | Reading and mitigation |
|---|---|---|---|---|---|---|---|---|
| S1 | +0.06% (0.23) | 94.6% / 94.6% | 7.14% | 0.979 | +0.04% | 94.7% | 0.972 | Base case. |
| S2 (ρ 0.7) | +0.71% (0.36) | 93.7% / 92.6% | 11.51% | 0.969 | +0.69% | 93.8% | 0.964 | Interval holds; RSE far above 7.5%. Mitigation unchanged: verify or select more units. |
| S3 (diary bias by group) | +0.04% (0.23) | 93.7% / 94.8% | 7.22% | 0.975 | +0.02% | 94.4% | 0.968 | Combined ratio still unbiased. |
| S4 (dropout depends on yield) | **+3.39%** (0.23) | 94.3% / 93.4% | 7.14% | 1.003 | +3.37% | 94.8% | 0.997 | Bias stays; the interval covers only because it is wide. A9 (recall of dropouts) is still not simulated. |
| S5 (75% of events verified) | −2.42% (0.21) | **89.4%** / 90.9% | 6.56% | 0.980 | −2.44% | **89.7%** | 0.973 | **Coverage below 93%**, as on the v0.3 seeds (90.7%). Mitigation (A7): announcement discipline, verified-event share per unit. |

## 4. Reading

- **The take-all term does not break anything.** S1 coverage is 94.6% here against 93.6% on the v0.3 seeds without the term. These are different districts, so the difference cannot be credited to the term; the paired diagnostic T4 (same samples, with and without the term) does that and is **not run yet**.
- **Productivity behaves like the total.** $\hat A$ is estimated with little error, so $\hat P$ has almost the same bias, RSE and coverage as $\hat Y$ in every scenario.
- **The bootstrap SE still sits about 2% to 3% below the empirical SD** (0.96 to 0.98 in S1 to S3, S5), the same pattern as v0.3. It is inside the 10% limit and does not push S1 coverage out of the band.
- **Limits.** One synthetic district per part; the MC SEs cover replication noise only. S5 and S4 remain stated limits in the proposal.

## 5. Next, per design 21.1 and 21.7

- T1 and T2 pass in `tests/test_v04.py`, and T3 passes here, so sections 8.6 and 8.7 and proposal §9.6 (the take-all gap statement) are now due for their edit.
- T4 (paired diagnostic on 20261103/5521), part B (Fay-Herriot, 20261105/7703) and part C (panel, 20261106/8815) are not run.

Files: `replications.csv` (5,000 rows), `metrics.csv`, `config_used.json`, `coverage_plot.png`, `bias_plot.png`, `run_log.txt`, `command.txt`.
