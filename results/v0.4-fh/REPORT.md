# Part B, Fay-Herriot block estimates (all numbers SIMULATED)

**Every number below is simulated** (synthetic district, nothing about real Assam production). Spec: `docs/design.md` section 21.4 (scenario F). Seeds fixed in section 21 before any v0.4 code: `pop_seed = 20261105`, `master_seed = 7703` (first use; nothing tuned on them). Wiring check before the run: 24 reps on throw-away seed 61.

The spec was written for the v0.4 estimator, so this run uses `--v04 --fh` (take-all phase-2 variance and productivity on; v0.5 switches off). **Part B does not test the v0.5 estimator:** `variance.block_list_totals` gives R·Σw1·x per block and has no recall-dropout term (F2, design 22.2), so under v0.5 the block totals would not add up to the list total. Wiring F2 into the block totals is a later change with its own criterion.

Three cases, 1,000 replications each, S1 base scenario, bootstrap (500 replicates) on every replication:

| Case | Folder | Block effect $\sigma_b$ | Blocks | Respondents per block (mean) | True district total |
|---|---|---|---|---|---|
| Primary | `results/v0.4-fh` | 0.15 | 10 | 18.0 | 13,470.4 t |
| No-harm (F5) | `results/v0.4-fh-nullb` | 0 | 10 | 18.0 | 14,501.4 t |
| Stress | `results/v0.4-fh-30blocks` | 0.15 | 30 | 6.0 | 13,952.1 t |

    python -m d32.simulate --reps 1000 --v04 --fh --scenarios S1 --pop-seed 20261105 --master-seed 7703 --workers 12 --sigma-b 0.15 --n-blocks 10 --out results/v0.4-fh
    (same with --sigma-b 0 --n-blocks 10 --out results/v0.4-fh-nullb, and --sigma-b 0.15 --n-blocks 30 --out results/v0.4-fh-30blocks)

**Headline.** All five criteria are met. Benchmarked Fay-Herriot (FH) cuts the mean block MSE to 0.55 of the direct estimate, with 95.0% mean interval coverage. **But the run shows a defect that the criteria do not catch:** before benchmarking, FH is biased low (−4.7% with 10 blocks, −26% with 30), and after benchmarking single blocks are still off by −10% to +7% (10 blocks) and −22% to +18% (30 blocks). The cause is in the variance smoothing (section 3). FH stays "experimental" in the proposal.

## 1. Criteria (primary case unless stated)

| # | Criterion | Measured (MC SE) | Result |
|---|---|---|---|
| F1 | Mean over blocks of MSE(FH) / MSE(direct) ≤ 0.85 | **0.549** (0.005); per block 0.46 to 0.74 | met |
| F2 | Mean coverage of the Prasad–Rao 95% interval in 92–97% | **95.0%** (0.2); per block 89.9% to 97.4% | met |
| F3 | Benchmarked block totals equal the direct district total to 1e-9 | max error 4.4e-16 | met |
| F4 | Share of reps where unadjusted REML gives $\hat\sigma_v^2 = 0$ (report) | **39.4%** | reported |
| F5 | No-harm, $\sigma_b = 0$: mean MSE ratio ≤ 1.05 | **0.519** (0.005); coverage 95.1% | met |

F4 is why the design uses the Li–Lahiri adjustment: plain REML sets the block variance to zero in four replications out of ten, which would shrink every block fully onto the regression line.

Stress case (30 blocks; report only, no pass or fail): F1 0.278 (0.004), F2 93.5% (0.1), F3 5.6e-16, F4 11.3%. On average 29.9 of 30 blocks had a respondent (minimum 28); blocks with none get the synthetic estimate and are left out of F1 and F2.

The district estimate is unchanged by the block work: E3 bias +0.02%, coverage 96.1%, RSE 6.5% (primary); +0.12%, 96.3%, 6.4% (no-harm); −0.04%, 95.7%, 6.7% (stress).

## 2. More than the criteria show

| Quantity | Primary | No-harm | Stress (30) |
|---|---|---|---|
| Mean relative error, direct | +0.06% | +0.06% | +0.5% |
| Mean relative error, FH before benchmarking | **−4.7%** | **−4.7%** | **−26.0%** |
| Mean relative error, FH benchmarked | +0.3% | +0.1% | +1.0% |
| Per-block bias of benchmarked FH (min, max) | −10.3%, +7.2% | −9.1%, +3.7% | −22.4%, +17.8% |
| Mean benchmark factor (FH_bm / FH) | 1.053 | 1.051 | 1.371 |
| Mean coverage, direct interval (±1.96 √ψ) | 90.4% | 90.3% | 83.7% |
| Mean coverage, FH before benchmarking | 93.4% | 93.5% | 82.3% |
| Mean $\hat\sigma_v^2$ | 1.91 | 2.12 | 1.50 |
| True between-block variance of θ_b | 0.145 | 0.035 | 0.235 |
| Mean ψ_raw / empirical variance of the direct estimate | 1.007 | 1.007 | 0.998 |

The bootstrap block variances ψ are right on average (last row), so the direct intervals under-cover because the direct estimates are skewed and some blocks are biased, not because ψ is too small.

## 3. Reading

- **Benchmarking is doing real work, not cosmetic work.** It removes a −4.7% (10 blocks) to −26% (30 blocks) level bias. Benchmarked FH meets every criterion, but F1 and F2 are averages over blocks, and they let through per-block biases of up to 10% (22% at 30 blocks). These criteria were too weak to catch this; the report says so rather than changing them after the run.
- **Cause (code verified, mechanism inferred).** `fayherriot.gvf_smooth` fits log ψ on (1, log n, **log θ̂_b**), the block's own direct estimate. A block whose direct estimate is low by chance gets a small smoothed variance, so the WLS regression and the shrinkage trust it more. The pooled prediction is pulled down, and $\hat\sigma_v^2$ is inflated (about 1.9 against a true between-block variance of at most 0.145, and 2.1 when there is no block effect at all, where it should be near 0.035). This is the known problem of a direct estimate correlated with its variance estimate. It grows as blocks get smaller, which matches the 30-block case.
- **Direct block estimates have their own per-block bias.** Block 4 of the primary case is −14.5% (MC SE 1.0); the range over blocks is −14.5% to +5.8%, identical with and without the block effect (the effect scales true and diary values together). Diary errors are redrawn every replication, so the diary model does not explain it. Likely cause, **not tested**: nonresponse and calibration adjust weights per stratum, not per block, so a block whose units respond less than its stratum is under-represented. FH inherits this bias where it trusts the direct estimate.
- **Interval honesty per block is uneven.** Mean FH coverage is 95.0%, but block 4 gets 89.9%.

## 4. What would fix it (not done; needs a new spec and unused seeds)

1. GVF without the direct estimate: fit log ψ on log n only, or on the synthetic prediction $\mathbf{x}_b^\top\hat\beta$ instead of θ̂_b.
2. A per-block bias criterion, for example max |bias| over blocks below 5% at 10 blocks, beside F1 and F2.
3. Investigate the direct-estimate bias of block 4 (response by block within stratum).
4. Add the recall-dropout term to the block totals so FH works with v0.5.

None of these was tried on these seeds. Seeds 20261105/7703 are now used.

## 5. Limits

One synthetic district per case; MC SEs cover replication noise only (F1 and F2 MC SEs by resampling whole replications, 200 resamples). Seed per ha (named in design section 11) is not simulated. The block effect is one simple form ($\theta_b = \bar\theta(1 + 0.15u_b)$).

Files per case: `replications.csv`, `metrics.csv`, `fh_blocks.csv` (one row per block and replication), `fh_metrics.csv`, `config_used.json`, `coverage_plot.png`, `bias_plot.png`, `run_log.txt`, `command.txt`.
