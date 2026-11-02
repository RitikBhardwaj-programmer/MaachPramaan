# Part C, rotating panel and composite estimator (all numbers SIMULATED)

**Every number below is simulated** (synthetic district, nothing about real Assam production). Spec: `docs/design.md` section 21.5 (scenario S6). Seeds fixed in section 21 before any v0.4 code: `pop_seed = 20261106`, `master_seed = 8815` (first use; nothing tuned on them). Wiring check before the run: 24 reps on throw-away seed 62.

Three years on one fixed frame; productivity persists between years with correlation $\rho_u$ and a +3% district trend [ASSUMPTIONS]. The sample rotates by a PRN shift ($\delta_h = n_h / 3N_h$ a year). Year 1 composite = direct E3; years 2 and 3: $\hat Y''_t = (1-K)\hat Y_t + K(\hat Y''_{t-1} + \hat\Delta_t)$, $K$ from the bootstrap replicates, clipped to [0, 0.8]. The panel code runs the v0.3 estimator (no v0.4 or v0.5 switches). 1,000 replications per case, bootstrap on every replication.

| Case | Folder | $\rho_u$ |
|---|---|---|
| Primary | `results/v0.4-panel` | 0.6 |
| Sensitivity (G6) | `results/v0.4-panel-rho03` | 0.3 |

    python -m d32.panel --reps 1000 --pop-seed 20261106 --master-seed 8815 --workers 12 --rho-u 0.6 --out results/v0.4-panel
    (same with --rho-u 0.3 --out results/v0.4-panel-rho03)

**Headline.** The composite estimator is safe but gives almost no gain: year-3 RMSE is 0.983 of the direct estimate's, against a target of 0.95 (G2 **not met**). It does no harm (G3, G6), stays unbiased (G4) and its intervals cover (G5). The rotation rule itself misses G1: about 9% of the non-take-all farms that enter the sample stay more than 3 years in a row, some all 6 years checked.

## 1. Criteria (primary case, $\rho_u = 0.6$)

| # | Criterion | Measured (MC SE) | Result |
|---|---|---|---|
| G1 | Matched share between consecutive years in [0.63, 0.70]; no unit sampled in more than 3 years | mean share 0.700 (year 2) and **0.702** (year 3); per replication 0.555 to 0.825. **8.6%** of non-take-all units sampled in 6 years stay more than 3 years in a row; the longest run is 6 years | **not met** |
| G2 | Year-3 RMSE(composite) / RMSE(direct) ≤ 0.95 | **0.983** | **not met** |
| G3 | Years 2 and 3 ratio ≤ 1.00 (no harm) | 0.982 and 0.983 | met |
| G4 | Composite absolute relative bias below 1.5% in years 2 and 3 | −0.02% (0.21) and −0.41% (0.22) | met |
| G5 | Composite bootstrap coverage 93% to 97% in years 2 and 3 | 94.0% (0.8) and 94.9% (0.7) | met |
| G6 | $\rho_u = 0.3$: ratio ≤ 1.00 | 0.985 (year 2) and 0.994 (year 3) | met |

G1 counts exclude take-all units (they stay every year by design; `panel.py` filters them out). Under G1, one part is close (mean share) and one part clearly fails (units over 3 years), so G1 as a whole is not met.

## 2. Detail

| Quantity | Year 1 | Year 2 | Year 3 |
|---|---|---|---|
| Direct bias | +0.07% | +0.48% (MC SE 0.22) | −0.01% |
| Direct coverage | 94.0% | 94.9% | 95.1% |
| Composite bias | (= direct) | −0.02% | −0.41% (0.22) |
| Composite coverage | (= direct) | 94.0% | 94.9% |
| RMSE, direct / composite (t) | 1,043 / 1,043 | 1,039 / 1,020 | 1,093 / 1,075 |
| Mean K | 0 | 0.179 | 0.178 |

$\rho_u = 0.3$: mean K 0.154 and 0.146, ratio 0.985 and 0.994, composite coverage 94.2% and 95.2%. The matched share is identical in both cases (same seeds, same rotation).

## 3. Reading

- **The composite is honest but nearly useless here.** The estimated K stays near 0.18, so the composite leans mostly on the current year. A low K is the right choice when the matched change $\hat\Delta_t$ is noisy relative to the direct estimate; the bootstrap measures that and keeps K small. Likely cause (inference, not tested): at $\rho_u = 0.6$ a unit's production is only moderately correlated between years, and each year's diary error and verification ratio are re-drawn, so the change estimated on the two-thirds overlap carries most of the direct estimate's noise. The gain of about 2% does not justify the composite's extra complexity yet.
- **The rotation rule does not cap time in sample.** The PRN shift moves every unit by $\delta_h$ a year, but the sample is the $n_h$ smallest shifted values, and random gaps between PRNs move the cut-off from year to year. Likely cause of the long runs (inference): strata with few units, where one gap is a large share of the window. A unit can then stay in for 4 to 6 years, which matters for farmer burden. A fix would be to rotate by explicit thirds (assign each selected unit a rotation group and drop the oldest group), not to tune $\delta_h$.
- **The year-3 composite bias of −0.41% is about 2 MC SEs from zero**, as is the year-2 direct bias of +0.48%. Both are well inside G4's 1.5%; among the ten bias numbers in the two cases, one or two at about 2 SE are expected by chance.

## 4. Consequence for the proposal

The rotating panel stays in the design for **farmer burden and continuity** (each farm keeps a diary about three years, and two thirds of the sample carries over), not for precision. The proposal must not claim a precision gain from the composite estimator. Rotation by explicit groups is listed for the next version, with its own criterion and new seeds.

## 5. Limits

One synthetic district; MC SEs cover replication noise only. The panel runs the v0.3 estimator, not v0.5. Three years only; the >3-year check uses six PRN shifts of the same frame.

Files per case: `replications.csv` (3,000 rows: year × replication), `metrics.csv`, `config_used.json`, `run_log.txt`, `command.txt`.
