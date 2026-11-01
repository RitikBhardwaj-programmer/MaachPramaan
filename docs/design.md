# D-32 Statistical Design Document

**Challenge:** NESFIC-D-32, Scientific Sample Survey for Pond and Tank Aquaculture Production Estimation (Fishery Department, Assam).
**Version:** 0.3 (draft), 2026-11-01. Changes from v0.1 are listed in section 18 (written before the confirmatory run). Changes from v0.2 are in section 19 (post-confirmation; written before the v0.3 check run).
**Status:** Design only. No real data is used. Every number marked *estimate* is own arithmetic from stated assumptions. Every result from the simulation will be marked *simulated*.

Sources: the [D-32 challenge page](https://startup.assam.gov.in/nesfic26/problem-statements/nesfic-d-32), the [USPR](https://startup.assam.gov.in/nesfic26/docs/uspr.pdf), and the research plan (`C:\Users\DELL\.claude\plans\yes-it-has-currently-eventual-pretzel.md`), which holds the source links for the shortcomings in section 1. Textbook methods cite standard references (section 14). I did not re-read those references for this draft.

---

## 0. Summary

| Item | Decision |
|---|---|
| Target | Total live-weight fish production from ponds and tanks, per district and for the pilot area, for one reference year, with a 95% confidence interval (CI). |
| Sampling unit | One water body (pond or tank) in the updated fishery-resource frame. |
| Frames | List frame (department) plus an area frame (grid cells) that measures what the list misses. |
| Strata | District × type × size class × intensity proxy, plus a take-all stratum for the largest water bodies. |
| Allocation | Neyman allocation inside each district, with a minimum of 5 selected units per stratum. Equal precision target across districts. |
| Selection | Permanent random numbers (PRN): each unit gets a fixed random number from a keyed hash of its ID. The units with the smallest PRNs in a stratum form the sample. |
| Measurement | Phase 1: harvest diary for every sampled unit, plus an end-of-year recall question. Phase 2: a random subsample where an enumerator verifies (weighs) every harvest. |
| Estimator | Two-phase ratio estimator: diary totals corrected by the verified-to-diary ratio. Nonresponse weighting: response-propensity classes from a 3-variable model, then calibration to known frame counts and water area. |
| Variance | Rao–Wu rescaled bootstrap that re-runs the whole pipeline (primary). Closed-form linearised variance as a cross-check only. |
| Over time | Rotating panel, one third of each stratum replaced per year by PRN shift. Composite estimator from year 2. |
| Sub-district | Fay-Herriot model for development blocks, benchmarked to the direct district total. |
| Audit | Frame hash, commit–reveal seed, hash-chained append-only log. Anyone with the frame and the seed can re-run the selection. |
| Pilot size | About 200 selected water bodies per district, about 50 of them verified (*estimate*, section 6). |

---

## 1. Problem and what the design must fix

The department now estimates output largely from farmer recall and a single productivity figure applied to water area (challenge page). The page lists these weaknesses: weak recall, missed or double-counted harvests, unrecorded self-consumption and farm-gate sales, and one productivity assumption that ignores stocking, species, feeding and management.

Assam has 560,019 ponds and tanks covering 96,968.86 ha in 2023-24, a mean of about 0.17 ha each ([NEDFI databank](https://databank.nedfi.com/assam-resources/fishery-assam)). The 2023-24 production figure appears as 4.74, 4.75 and 4.99 lakh MT in different sources. That spread is itself evidence of the problem.

| # | Shortcoming | Where the design fixes it |
|---|---|---|
| 1 | Frame is incomplete or out of date | Section 3 (area frame for undercoverage) |
| 2 | Recall is biased | Sections 7–8 (diary plus verified subsample, ratio correction) |
| 3 | Diaries cost money; farmers drop out | Sections 6, 9 (light diary, propensity-class weighting, open dropout report) |
| 4 | Partial harvests; double counting | Section 7 (one record per harvest event with a phone-made ID) |
| 5 | Implausible reports | Section 10 (flag, never overwrite) |
| 6 | Few sampled units per small area | Section 11 (Fay-Herriot, shown beside direct estimates) |
| 7 | A few large farms dominate output | Section 4 (take-all stratum) |
| 8 | Yearly fresh samples lose trend precision | Section 12 (rotating panel, composite estimator) |
| 9 | Method is not auditable | Section 13 (seeded, hashed, logged) |

The claim is **reproducibility and visible error**. The design does not claim to beat the department's current numbers. Only a real pilot can test that.

---

## 2. Target parameters and definitions

**Reference year.** 1 April to 31 March, to match the department's financial-year reporting (assumption A1).

**Production.** Live weight (kg) of all fish and other aquatic animals removed from the water body in the reference year. This includes sales, self-consumption, gifts, payments in kind, and fish given to labour. It excludes seed and fingerlings moved to another pond for further rearing (they count when finally harvested).

**Harvest event.** One removal of fish on one day from one water body. A partial harvest is one event. A final drain harvest is one event. A pond-year total is the sum of its events.

**Parameters.**

| Symbol | Meaning |
|---|---|
| $Y_d$ | Total production in district $d$ (tonnes) |
| $Y = \sum_d Y_d$ | Total over the pilot districts |
| $A_d$ | Total water area in district $d$ (ha), from the frame plus the area-frame correction |
| $P_d = Y_d / A_d$ | Productivity (t/ha), a ratio of two estimated totals |
| $Y_{d,h}$ | Total in stratum $h$ of district $d$ (a domain estimate) |

Productivity is reported because the department already reasons in t/ha. It is estimated as a ratio, never as the mean of unit-level t/ha values. The mean of ratios over-weights tiny ponds.

---

## 3. Frames and coverage

### 3.1 List frame
The updated fishery-resource frame from the department (challenge page: "Use the updated fishery-resource frame"). Required fields: unit ID, district, development block, village or GP, type (pond or tank), water area, location (lat/long if present), owner or operator ID. Useful extra fields: scheme beneficiary flag, fish-seed supply records.

Assumption A2: the frame has a stable unit ID. If not, the engine builds one from district + block + village + serial, and freezes it in the frame snapshot.

### 3.2 Why a second frame
A list frame misses new ponds, unregistered ponds and ponds that changed owner. A list-only estimate is then biased low, and no amount of sampling inside the list shows the gap. USDA NASS pairs a list frame with an area frame for the same reason (plan file, NASS source).

### 3.3 Area frame (screening dual-frame design)
1. Cover each pilot district with a grid of 1 km² cells.
2. Stratify cells by the water fraction seen in free Sentinel-2 imagery (10 m pixels; NDWI water index). Two strata: "water-rich" and "other". A 0.17 ha pond is about 17 pixels, so imagery guides the stratification only. It is never used as a pond census.
3. Select about 30 cells per district by simple random sampling without replacement (SRSWOR) inside each cell stratum.
4. A field team lists every pond and tank in each selected cell and matches each one to the list frame (by location, owner and area).
5. Unmatched water bodies form the **not-on-list domain**. Each one gets a single end-of-year recall interview.

Because the area frame covers the whole district, the list frame is a subset of it. This is the "screening" case of dual-frame estimation: the total is the list estimate plus an estimate for the not-on-list domain. No overlap weighting is needed.

### 3.4 Not-on-list estimator
Let $g$ be a cell stratum with $C_g$ cells, $c_g$ sampled. For a sampled cell $k$, let $z_k$ be the sum of the *corrected* recall production of its not-on-list units: $z_k = \hat R_{rec} \sum_{j \in k,\ \text{not on list}} r_j$, where $r_j$ is recall and $\hat R_{rec}$ is the verified-to-recall ratio from the list sample (section 8.4).

$$\hat Y_{NL} = \sum_g \frac{C_g}{c_g} \sum_{k \in s_g} z_k$$

$$\hat V(\hat Y_{NL}) = \sum_g C_g^2 \left(1 - \frac{c_g}{C_g}\right) \frac{s^2_{z,g}}{c_g} \quad (+\ \text{a term for the variance of } \hat R_{rec}\text{, see 8.4})$$

The same cells give the **undercoverage rate**: estimated not-on-list units divided by estimated total units. This is a direct, reportable measure of frame quality.

---

## 4. Stratification

### 4.1 Why stratify
Production per pond is very skewed. Size, type and management explain much of that spread. Strata built on these variables make each stratum more uniform, so a smaller sample gives the same precision. Strata also guarantee that every kind of pond is in the sample.

### 4.2 Strata variables (all must be in the frame before selection)

| Variable | Levels | Source |
|---|---|---|
| District | 3 pilot districts | Frame |
| Type | Pond, tank | Frame |
| Size | 3 classes, plus take-all | Frame water area |
| Intensity proxy | Assisted, not assisted | Scheme beneficiary records and fish-seed supply records |

Intensity itself (stocking density, feed) is not in the frame. The challenge asks for stratification by intensity, so the design uses the best frame proxy: a unit is "assisted" if it appears in scheme beneficiary records or received departmental seed in the last two years (assumption A3). The real intensity is collected in the field and used later for analysis and for the plausibility checks.

### 4.3 Size class boundaries
Inside each district × type cell, set boundaries on water area by the **cumulative √f rule** (Dalenius–Hodges): build a fine histogram of area, sum √(frequency) cumulatively, and cut the cumulative sum into equal parts. This rule approximately minimises variance under Neyman allocation when the stratifying variable is well correlated with the target.

### 4.4 Take-all stratum
Large water bodies (big tanks, commercial farms) carry a large share of output. A sample that misses one, or includes one, swings the estimate. So every unit above a size cut-off $a^*_d$ enters the sample with certainty (selection probability 1, weight 1, no sampling variance).

Rule (v0.2): take-all = the largest units by water area among those of at least 2 ha (commercial scale), up to $\lfloor 0.1\,n_d \rfloor$ units (20 when $n_d = 200$). The take-all units count inside $n_d$. If fewer units reach 2 ha, take-all is smaller or empty (assumption A4).

**Known property (v0.3 note).** The cap can leave units of 2 ha or more in the sampled strata. In the v0.2 synthetic district (simulated), 68 units reach 2 ha, 20 become take-all, and 48 stay in the top pond and tank size classes with a small inclusion probability. Each of them carries a large weight and a large share of production, so they drive the variance. The design keeps the 10% cap in v0.3 (changing it would change every sample and hide the effect of the calibration fix below). Whether to raise the cap is open decision 5 in section 17.

Why not the v0.1 rule ("take-all when Neyman gives an inclusion probability above 1"): at 200 of 20,000 units a pond must be about 100 times the mean size before that happens, so the rule never fired in simulation. A fixed size cut-off is simple, auditable, and matches how departments already think about commercial farms.

Units in take-all still have measurement error, so they are still eligible for phase-2 verification.

### 4.5 Collapse rule
A stratum with fewer than 20 frame units, or fewer than 5 selected units, is merged with the next size class in the same district × type × intensity cell. Variance estimation needs at least 2 responding units per stratum. The minimum of 5 selected units protects against dropout.

Upper bound per district: 2 types × 3 sizes × 2 intensity = 12 sampled strata, plus take-all.

---

## 5. Allocation

### 5.1 Across districts
The pilot must give a usable estimate for **each** district. So each district gets the sample needed to meet the same precision target (section 6), not a share proportional to its size. Proportional allocation would give the small, "geographically distinct" district too few units.

### 5.2 Inside a district: Neyman allocation
Neyman allocation gives more units to strata that are large and variable:

$$n_h = n \cdot \frac{N_h S_h}{\sum_k N_k S_k}$$

where $N_h$ is the frame count and $S_h$ is the standard deviation of production in stratum $h$.

$S_h$ is unknown before the survey. Plan it from a working model: production ∝ area × productivity, so $S_h \approx \bar p_h \, S_{a,h}$, where $S_{a,h}$ is the area SD in the frame and $\bar p_h$ is a planning productivity for that type and intensity (from the department's historical data, assumption A5). After the first year, use the observed $s_h$. (v0.1 had an extra inflation factor $\kappa$ here. It multiplies every $S_h$ equally, so it cancels in the allocation; it was removed. Variation not explained by area enters only the sample-size calculation, through $CV$ in section 6.)

Steps:
1. Compute $n_h$ by the formula.
2. If any $n_h > N_h$, move that stratum's units to take-all, remove them from $n$, and repeat.
3. Raise any $n_h < 5$ to 5 (or apply the collapse rule).
4. Round to whole units, keeping $\sum n_h = n$.

---

## 6. Sample size (planning estimate)

**Precision target (assumption A6):** relative standard error (RSE) of the district total ≤ 7.5%, so the 95% CI half-width is about ±15% per district. For three districts, the pilot-total RSE is then about 7.5% / √3 ≈ 4.3%.

**Planning assumptions** (to be checked in the simulation and replaced by pilot values):

| Symbol | Value | Meaning |
|---|---|---|
| $CV$ | 0.7 | Coefficient of variation of production per unit, *within strata* |
| $\rho$ | 0.9 | Correlation between diary total and verified total |
| $\nu$ | 0.3 | Phase-2 (verification) rate among phase-1 respondents |
| response | 0.85 | Share of selected units that complete the diary year |
| $deff_w$ | 1.2 | Variance inflation from the *nonresponse* adjustment only (Kish formula on the adjustment factors inside strata). The Kish formula on the full weights is larger, because Neyman allocation makes weights unequal on purpose, and that inequality lowers variance rather than raising it. |
| $N_d$ | 20,000 | Units in a district frame (the state mean is about 16,000–18,000 per district, *estimate*) |

For the two-phase ratio estimator (section 8), with $n_1$ phase-1 respondents and $m = \nu n_1$ verified units:

$$RSE^2 \approx CV^2 \left[\frac{1}{n_1} + \left(\frac{1}{m} - \frac{1}{n_1}\right)(1-\rho^2)\right] = \frac{CV^2}{n_1}\left[1 + \left(\frac{1}{\nu} - 1\right)(1-\rho^2)\right]$$

With the values above the bracket is 1.443. Solving, applying the finite population correction (fpc), the weight effect and the response rate gives (*estimate*):

| $CV$ | RSE target | Respondents | Selected | Verified |
|---|---|---|---|---|
| 0.6 | 7.5% | 110 | 130 | 33 |
| **0.7** | **7.5%** | **150** | **176** | **45** |
| 0.8 | 7.5% | 195 | 230 | 59 |
| 0.7 | 5.0% | 335 | 394 | 100 |

**Plan:** select **200 units per district** (600 total), take-all units included, and verify **about 50 per district** (150 total). The simulation (section 15) tests whether these sizes meet the target.

**Caution from the v0.1 simulation (simulated):** the synthetic district had a pooled within-group CV of about 1.6, much heavier-tailed than the planning value 0.7. Even so, the empirical RSE at 200 units was 7.6%, close to the target, because Neyman allocation and the ratio correction absorb much of that spread. So the table above is a rough guide only. The real spread is unknown until the department's historical data or the first pilot year arrive; the proposal re-sizes the sample from those, using the observed $s_h$ and $\rho$.

Why verify 30% and not more: each verified unit needs an enumerator at every harvest. If the diary is good ($\rho = 0.9$), verifying more units gives little: the bracket only drops from 1.44 to 1.19 when $\nu$ goes from 0.3 to 0.5.

---

## 7. Measurement

### 7.1 Instruments
| Instrument | Who | When | Tool |
|---|---|---|---|
| Listing schedule | Enumerator | Start of year | XLSForm on KoboToolbox or ODK Collect |
| Harvest diary | Farmer (or a helper) | At each harvest | Short phone form; paper card fallback copied by the enumerator |
| Monthly check | Enumerator | Monthly visit or call | Fills gaps, confirms "no harvest" months |
| Verification | Enumerator | At each harvest of a phase-2 unit | Weighs the catch (calibrated scale) or counts crates of known tare weight |
| End-of-year recall | Enumerator | After the year ends | One question set: "How much did you harvest this year?" |
| Not-on-list interview | Enumerator | After the year ends | Recall schedule for units found in area-frame cells |

The custom-app route was rejected. KoboToolbox or ODK handle offline capture, so build time goes to the survey engine.

### 7.2 Harvest event record (one row per event)
`event_id` (UUID made on the phone, so a re-upload of the same event is ignored: idempotent upload), `unit_id`, `date`, `species group`, `quantity_kg`, `disposal` (sold / home use / gift / labour / other), `price` (optional), `source` (diary / monthly-check / verified / recall), `recorder`, `device_time`, `gps` (optional).

A pond-year diary total is $x_i = \sum_{e \in i} q_e$ over diary events. A verified total is $y_i = \sum_{e \in i} q^{ver}_e$ over verified events.

### 7.3 Harvest announcement for verified units
A phase-2 farmer agrees to announce each harvest a day ahead (phone call or SMS to the enumerator). The enumerator attends and weighs. A harvest done without notice is recorded in the diary and marked `unverified`; the count of such events is reported. Assumption A7: at least 90% of phase-2 harvests are verified. The simulation tests what happens below that.

### 7.4 Why also ask recall
The end-of-year recall question costs one minute. It gives (a) the department's current method on the same units, so the pilot measures the recall bias directly, and (b) the verified-to-recall ratio needed for the not-on-list domain (section 3.4).

---

## 8. Estimation

### 8.1 Notation
Inside district $d$ (index dropped): stratum $h$ has $N_h$ frame units, $n_h$ selected, $n'_h$ responding (phase 1), $m_h$ verified (phase 2, a subsample of the respondents).

### 8.2 Weights
- Design weight: $w^{(0)}_i = N_h / n_h$.
- Nonresponse adjustment and calibration (section 9): $w^{(1)}_i = w^{(0)}_i \cdot \phi_{c(i)} \cdot g_i$ for respondents, where $g_i$ is the calibration factor.
- Phase-2 weight: $w^{(2)}_i = w^{(1)}_i \cdot n'_h / m_h$ for verified units.

### 8.3 Two-phase ratio estimator (list frame)
Phase-1 estimate of the diary total:
$$\hat X = \sum_{i \in s_1} w^{(1)}_i x_i$$

Verified-to-diary ratio, estimated on phase 2, combined across the strata of the district:
$$\hat R = \frac{\sum_{i \in s_2} w^{(2)}_i y_i}{\sum_{i \in s_2} w^{(2)}_i x_i}$$

District list-frame total:
$$\hat Y_L = \hat R \, \hat X$$

**Why a combined ratio, not one ratio per stratum:** with about 4 verified units per stratum, separate ratios have a large small-sample bias. The combined ratio is stable. Its weakness: if diary under-reporting differs strongly between strata, one ratio is wrong for some of them. Fallback: separate ratios per *calibration group* (assisted vs not assisted) when each group has at least 20 verified units. The simulation includes this case (section 15, scenario S3).

**Why ratio and not regression:** a diary that reports zero harvest should give zero production. The ratio estimator goes through the origin; a regression estimator with an intercept does not.

### 8.4 Recall ratio (for the not-on-list domain and the comparison)
$$\hat R_{rec} = \frac{\sum_{i \in s_2} w^{(2)}_i y_i}{\sum_{i \in s_2} w^{(2)}_i r_i}$$
This assumes recall bias in not-on-list units is like recall bias in listed units of the district (assumption A8). The variance of $\hat Y_{NL}$ gets an extra term from $\hat R_{rec}$; the bootstrap (8.7) handles it by re-computing $\hat R_{rec}$ in each replicate.

### 8.5 District and pilot totals
$$\hat Y_d = \hat Y_{L,d} + \hat Y_{NL,d}, \qquad \hat Y = \sum_d \hat Y_d$$
List and area samples are selected independently, so their variances add. Districts are independent strata, so district variances add.

### 8.6 Variance (Taylor linearisation)
Residuals for verified units: $e_i = y_i - \hat R x_i$. For the list-frame total:

$$\hat V(\hat Y_L) = \underbrace{\sum_h N_h^2\left(\frac{1}{n'_h} - \frac{1}{N_h}\right) s^2_{y,h}}_{\text{phase 1: sampling units}} + \underbrace{\sum_h N_h^2\left(\frac{1}{m_h} - \frac{1}{n'_h}\right) s^2_{e,h}}_{\text{phase 2: diary error not removed by } \hat R}$$

$s^2_{y,h}$ and $s^2_{e,h}$ are sample variances computed on the verified units of stratum $h$ (only they have $y_i$). This is the standard double-sampling-for-ratio variance (Cochran ch. 12; Särndal et al. ch. 9), stratified. Take-all strata add nothing to the first term but do add to the second if they are subsampled for verification.

**Status (v0.2): cross-check only.** This formula treats the respondents as a simple random subsample inside each stratum. It has no term for the variation that the nonresponse adjustment and calibration (section 9) add, and it takes $s^2_{y,h}$ from about 4 verified units per stratum. In the v0.1 simulation it was about 12% below the true SD (simulated), and its intervals covered 90.5%. It is still reported, because a reader can check it by hand.

### 8.7 Primary variance: rescaled bootstrap
A Rao–Wu rescaled bootstrap (500 replicates). Inside each stratum, resample $n_h - 1$ of the $n_h$ *selected* units with replacement (respondents and nonrespondents together, because the nonresponse step needs both). Each unit carries its response and phase-2 status. Area-frame cells are resampled the same way inside cell strata. Rescale the weights, $w^*_i = w_i\,(1 - \lambda_h + \lambda_h\, t_i\, n_h/(n_h-1))$ with $\lambda_h = \sqrt{1-f_h}$ (the Rao–Wu–Yue value $\sqrt{m_h(1-f_h)/(n_h-1)}$ for $m_h = n_h - 1$ draws), $f_h = n_h/N_h$, and $t_i$ the number of times unit $i$ is drawn, then re-run the *whole* pipeline: propensity model, classes, calibration, $\hat R$, $\hat R_{rec}$, $\hat Y_{NL}$. $\hat V_{boot}$ is the variance of the 500 replicate totals.

Why primary: it carries every estimation step, including the nonresponse and calibration steps that the closed-form formula leaves out. The bootstrap is also the variance method for the composite estimator (section 12).

**Confidence interval:**
$$\hat Y_d \pm t_{0.975,\ df}\ \sqrt{\hat V_{boot}(\hat Y_d)}, \qquad df = m_d - H_d$$
($m_d$ verified units minus the number of strata with verified units). A $t$ multiplier instead of 1.96 protects coverage when $m_d$ is about 50. Take-all strata ($f_h = 1$) get $\lambda_h = 0$, so they add no sampling variance, as intended.

### 8.8 Productivity
$\hat P_d = \hat Y_d / \hat A_d$, with $\hat A_d$ = frame area + not-on-list area estimate. Variance by linearisation of a ratio, $\hat V(\hat P) \approx \hat A^{-2}[\hat V(\hat Y) + \hat P^2 \hat V(\hat A) - 2\hat P\,\widehat{Cov}(\hat Y,\hat A)]$, or from the bootstrap.

### 8.9 Design effect
Report Kish's weighting design effect, $deff_w = n\sum w_i^2 / (\sum w_i)^2$, in two forms for each district: (a) on the full weights, and (b) on the nonresponse-and-calibration factors $\phi_{c(i)} g_i$ only, pooled over strata. Form (b) is the real cost of nonresponse. Form (a) also counts the weight differences that Neyman allocation creates on purpose, which lower variance, so it overstates the cost.

---

## 9. Nonresponse and dropout

**Respondent:** a phase-1 unit whose diary, with monthly checks, covers all 12 months (a "no harvest" month counts as covered).

**Method: response-propensity classes, then calibration.**
1. Fit an **unweighted** logistic regression of response (1/0) on exactly three frame variables: log area, intensity proxy (assisted or not), and distance to the block office (if the frame lacks distance, use type instead). The model is fixed here, before any data are seen, so it cannot be chosen to fit a result.
2. Sort units by predicted propensity and cut into 5 classes (quintiles) inside each district.
3. Adjustment factor for class $c$: $\phi_c = \sum_{i \in c} w^{(0)}_i \,/\, \sum_{i \in c,\ \text{resp}} w^{(0)}_i$.
4. If any $\phi_c > 2$, merge that class with its neighbour (this caps extreme weights; it replaces ad-hoc trimming).
5. **Calibrate** the adjusted respondent weights $w^{(0)}_i\phi_{c(i)}$ so that, for each stratum $h$, the respondents reproduce the frame's known unit count $N_h$ and known total water area $A_h$. Use linear calibration (GREG weights) with the calibration factor bounded to $[0.3,\ 3]$ (iterate with truncation until the constraints hold or 20 iterations pass; record any stratum where they do not hold). If a stratum has fewer than 8 respondents, calibrate it to $N_h$ only (v0.3; was 4). If a stratum calibrated to both $N_h$ and $A_h$ still misses a constraint after 20 iterations, repeat its calibration to $N_h$ only and record the fallback (v0.3; v0.2 kept the truncated factors). A stratum with no respondents gets no weights and is recorded. The result is $w^{(1)}_i$.

**Why three variables.** A logistic model needs about 10 outcome events per parameter to be stable (Peduzzi et al. 1996). At 200 selected units and 85% response there are about 30 dropouts, so about 3 parameters. The v0.1 model (type, intensity, log area, distance and 9 block dummies, 14 parameters) had about 2 events per parameter; in simulation it removed only two thirds of the dropout bias (simulated: +6.1% with no adjustment, +2.3% after it).

**Why unweighted.** The fit only ranks units by response propensity. The design weights already enter in steps 3 and 5. An unweighted fit is less noisy when weights are unequal (simulated, v0.1 sensitivity run: bias +1.05% unweighted vs +2.29% weighted).

**Why calibrate to area.** Water area is known for every frame unit and is the strongest predictor of production. If respondents over-represent large ponds, their weighted area exceeds the frame total; calibration removes that excess, and with it most of the bias that runs through area. It also lowers variance, because the part of production that area explains no longer varies between samples. This is the GREG (generalised regression) idea (Deville and Särndal 1992; Särndal et al. ch. 6).

Classes are used instead of raw $1/\hat p_i$ weights because raw inverse propensities produce a few huge weights when $\hat p_i$ is small.

**Assumption A9 (missing at random given frame variables):** inside a class, dropouts produce like respondents. This can fail, for example if farmers with a bad year stop recording. The design checks it in two ways: (a) dropouts still get the end-of-year recall question, so recall of dropouts and of respondents can be compared; (b) simulation scenario S4 makes dropout depend on production and measures the bias.

**Report openly:** selected, responded, verified, dropped (with reasons), per stratum.

---

## 10. Plausibility checks (flag, never overwrite)

Checks run on upload and again at year end.

| Check | Rule | Level |
|---|---|---|
| Yield outlier | Modified z-score on log(production / area) within stratum: $M_i = 0.6745\,(u_i - \tilde u)/\mathrm{MAD}$; flag if $|M_i| > 3.5$ (Iglewicz–Hoaglin) | Pond-year |
| Event size | One event larger than a set multiple of the stratum's median event size per ha | Event |
| Seed consistency | Production far above what the stocked seed could produce (seed count × an upper survival rate × an upper harvest weight) | Pond-year |
| Duplicate | Same unit, same day, same quantity within 5% | Event |
| Diary vs verified | For phase-2 units, $|q_e - q^{ver}_e| / q^{ver}_e > 50\%$ | Event |

The modified z-score uses the median and the median absolute deviation (MAD), so the outliers it looks for do not distort the centre and spread.

**Rules:** a flag sends the record to a review queue. The reviewer records a resolution: confirmed, corrected (with evidence), or unresolved. The original value is never changed. A correction is a new version in the append-only log (section 13). The main estimate uses confirmed and corrected values. A sensitivity estimate without unresolved flagged records is reported beside it.

---

## 11. Small-area estimates (development blocks)

**Why:** with 200 units per district, a block (sub-district unit) may have only 10–20 sampled units. A direct block estimate then has a very wide CI.

**Fay-Herriot area-level model.** For block $b$:
$$\hat\theta_b = \theta_b + \varepsilon_b, \quad \varepsilon_b \sim N(0, \psi_b) \qquad \text{(sampling model)}$$
$$\theta_b = \mathbf{x}_b^\top \boldsymbol\beta + v_b, \quad v_b \sim N(0, \sigma_v^2) \qquad \text{(linking model)}$$

$\hat\theta_b$ is the direct estimate of block productivity (t/ha); $\psi_b$ is its sampling variance; $\mathbf{x}_b$ are block covariates from department data (frame water area, share of assisted units, seed supplied per ha).

The best predictor shrinks the direct estimate toward the model in proportion to its noise:
$$\tilde\theta_b = \gamma_b \hat\theta_b + (1-\gamma_b)\,\mathbf{x}_b^\top\hat{\boldsymbol\beta}, \qquad \gamma_b = \frac{\hat\sigma_v^2}{\hat\sigma_v^2 + \psi_b}$$

**Known weaknesses and the fixes used:**
- Direct $\hat\psi_b$ from 10–20 units is unstable. Fix: smooth it with a generalised variance function (GVF), a fitted relation of log variance on log sample size and log estimate.
- $\hat\sigma_v^2$ can be estimated as 0, which shrinks every block fully to the model. Fix: an adjusted REML estimator that stays positive (Li–Lahiri).
- Block totals must add to the district total. Fix: ratio benchmarking to the direct district estimate.

**MSE:** Prasad–Rao approximation. FH and direct estimates are always shown side by side, with their CIs, so users see what the model adds.

**Scope:** about 30 blocks across 3 districts is close to the lower limit for estimating $\sigma_v^2$. Statewide (all districts, all blocks) the model is much stronger. The pilot reports FH as experimental.

---

## 12. Rotating panel and composite estimator (year 2 onward)

**Rotation by PRN shift.** Each year, each unit's PRN is shifted: $u_i^{(t)} = (u_i + t\cdot\delta_h) \bmod 1$, with $\delta_h = n_h / (3N_h)$. The sample is still the $n_h$ smallest values, so about one third of each stratum's sample leaves each year and is replaced. Each unit stays at most about 3 years, which limits diary fatigue. New frame units get their own PRN and enter naturally (assumption A10: rotation rate one third; the department can change it).

**Composite estimator.** Two years share about two thirds of their units. The matched units measure change well. The composite estimate combines this year's direct estimate with last year's composite plus the matched change:
$$\hat Y''_t = (1-K)\,\hat Y_t + K\,(\hat Y''_{t-1} + \hat\Delta_t)$$
$\hat\Delta_t$ is the change estimated on matched units. $K$ (0 to 1) is chosen to minimise variance, which depends on the year-to-year correlation of unit production; it is estimated after year 2. Variance by the bootstrap, replicating the same units in both years.

**Pilot note:** the pilot covers one year, so the composite estimator is specified and tested in simulation (three simulated years) only.

---

## 13. Reproducibility and audit

**PRN generation (order-independent):**
$$u_i = \frac{\mathrm{int}\big(\mathrm{HMAC\text{-}SHA256}(\text{seed},\ \text{unit\_id})[0{:}8]\big)}{2^{64}}$$
Each unit's PRN depends only on the seed and its own ID. Adding or removing other units does not change it. A sequence of draws from one generator would change when the frame order changes.

Selecting the $n_h$ smallest PRNs in a stratum gives an exact SRSWOR sample (sequential simple random sampling, Ohlsson 1995).

Other random draws (phase-2 subsample, bootstrap) use `numpy.random.Generator(PCG64(...))` with child seeds from `SeedSequence(seed).spawn(k)`, one child per purpose, so purposes never share a stream.

**Commit–reveal of the seed:**
1. Before the frame is frozen, publish $H(\text{seed})$ (SHA-256 commitment).
2. Freeze the frame. Publish the frame file's SHA-256 hash.
3. Reveal the seed. Anyone can check it against the commitment and re-run the selection.

The department cannot choose a seed after seeing the frame, and cannot edit the frame after seeing the seed.

**Append-only, hash-chained log.** Every frame load, selection, upload, flag, review and estimate run is one log entry. Each entry stores the SHA-256 hash of the previous entry, so an edit to any past entry breaks the chain from that point.

**Estimate run record:** code version (git commit), frame hash, seed commitment, data snapshot hash, parameter file, outputs. Re-running the record gives the same numbers.

---

## 14. Standard references (not re-read for this draft)

- Cochran, W. G. (1977). *Sampling Techniques*, 3rd ed. Ch. 5 (stratification, Neyman allocation, √f rule), ch. 6 (ratio estimators), ch. 12 (double sampling).
- Särndal, C.-E., Swensson, B., Wretman, J. (1992). *Model Assisted Survey Sampling*. Ch. 9 (two-phase sampling), ch. 15 (nonresponse).
- Ohlsson, E. (1995). Coordination of samples using permanent random numbers. In *Business Survey Methods*.
- Hartley, H. O. (1962). Multiple frame surveys. *Proc. ASA*. Lohr, S. (2009). Multiple-frame surveys. *Handbook of Statistics* 29A.
- Little, R. J. A. (1986). Survey nonresponse adjustments for estimates of means. *Int. Stat. Review*.
- Kish, L. (1992). Weighting for unequal $P_i$. *J. Official Statistics*.
- Rao, J. N. K., Wu, C. F. J. (1988). Resampling inference with complex survey data. *JASA*.
- Fay, R. E., Herriot, R. A. (1979). Estimates of income for small places. *JASA*. Prasad, N. G. N., Rao, J. N. K. (1990). *JASA*. Li, H., Lahiri, P. (2010). *J. Multivariate Analysis*.
- Gurney, M., Daly, J. F. (1965). A multivariate approach to estimation in periodic sample surveys. *Proc. ASA*.
- Iglewicz, B., Hoaglin, D. (1993). *How to Detect and Handle Outliers*. ASQC.
- Deville, J.-C., Särndal, C.-E. (1992). Calibration estimators in survey sampling. *JASA* 87.
- Peduzzi, P. et al. (1996). A simulation study of the number of events per variable in logistic regression analysis. *J. Clinical Epidemiology* 49.
- Rao, J. N. K., Wu, C. F. J., Yue, K. (1992). Some recent work on resampling methods for complex surveys. *Survey Methodology* 18.

---

## 15. Simulation specification (Days 3–6)

All output of this section is **simulated**. It proves that the method behaves as claimed under stated assumptions. It says nothing about real Assam production.

### 15.1 Synthetic district
- $N$ = 20,000 listed units plus 1,600 not-on-list units (8% undercoverage, skewed toward small ponds).
- Area: lognormal, mean 0.17 ha (matches the state mean), with a long right tail. Tanks: a placeholder 2% of units, larger on average (replace with the frame's real share).
- True productivity: depends on type and intensity (assisted units higher), with unit-level lognormal noise. Calibrate the planning productivity so that the district total is plausible against the department's historical data once received; until then use a stated placeholder.
- Harvest events: 1–6 per unit-year, partial plus final.
- Diary error: $x_i = y_i (1 + \beta_D)\,\eta_i$, with under-reporting $\beta_D = -10\%$ and noise $\eta_i$ giving $\rho \approx 0.9$.
- Recall error: $r_i = y_i (1 + \beta_R)\,\xi_i$, $\beta_R = -25\%$, noisier than the diary.
- Dropout: logistic in frame variables, mean response 85%.

### 15.2 Estimators compared
| Code | Method |
|---|---|
| E0 | Area × one productivity figure (the current single-assumption method) |
| E1 | Recall-only stratified expansion |
| E2 | Diary-only stratified expansion (no verification) |
| E3 | **Proposed:** two-phase ratio + nonresponse classes + not-on-list domain |

### 15.3 Scenarios
| Code | What changes | What it tests |
|---|---|---|
| S1 | Base case | Coverage and bias when the assumptions hold |
| S2 | $\rho$ = 0.7 | A noisier diary |
| S3 | Diary bias −5% for assisted, −20% for not assisted | Combined vs separate ratio (8.3) |
| S4 | Dropout more likely in low-production years | Failure of A9 |
| S5 | Only 75% of phase-2 harvests verified | Failure of A7 |
| S6 | Three years with rotation | Composite estimator gain |

### 15.4 Metrics and acceptance criteria
1,000 replications per scenario.

**Confirmatory run (v0.2).** The v0.1 run is exploratory: its results led to the section 18 changes. The v0.2 run uses seeds that no earlier run used, fixed here before the run: `pop_seed = 20261102` (a new synthetic district from the same model) and `master_seed = 4417`. The v0.2 run reports its results as they come. If a criterion fails, the report says so; nothing is re-tuned on these seeds.

For each estimator: relative bias, RMSE, 95% CI coverage, mean CI width.

| # | Criterion |
|---|---|
| AC1 | E3 95% CI coverage (bootstrap interval, section 8.7) between 93% and 97% in S1. (Monte Carlo SE of coverage at 1,000 reps is 0.7 points, so a correct method lands in this band with high probability.) |
| AC2 | E3 absolute relative bias below 1% in S1. |
| AC3 | E1 and E0 show their bias in S1; E3 does not. |
| AC4 | (v0.2) Mean bootstrap SE of E3 within 10% of the empirical SD of E3 across replications in S1. The linearised SE is reported beside it, with its ratio to the empirical SD. (v0.1 compared linearised with bootstrap; it failed at 1.15, see section 18.) |
| AC5 | E3 meets RSE ≤ 7.5% at 200 selected units in S1. |
| AC6 | S2–S5 results are reported honestly, including any coverage failure, with the mitigation named. |
| AC7 | Re-running with the same seed and frame gives identical samples and estimates (byte-identical output). |

---

## 16. Assumptions

| ID | Assumption | Confirmed? | If wrong |
|---|---|---|---|
| A0 | No real data is used in the proposal; the department's data arrive after selection | The challenge page lists the data the department can provide; access at proposal stage is not confirmed (USPR: "Do not assume unconfirmed access") | Simulation-only evidence |
| A1 | Reference year = financial year | No | Change one parameter |
| A2 | Frame has stable unit IDs | No | Engine builds and freezes IDs |
| A3 | Scheme and seed records can be linked to frame units | No | Drop the intensity proxy; stratify by size and type only |
| A4 | Take-all = largest units of at least 2 ha, capped at 10% of the district sample | Design choice | Adjust the 2 ha cut-off after the frame is seen |
| A5 | Historical productivity by type is available for planning | Data promised, not confirmed | Use equal planning productivity across strata and a conservative $CV$ in section 6 |
| A6 | Target RSE 7.5% per district | Design choice; department may set its own | Re-run section 6 table |
| A7 | ≥ 90% of phase-2 harvests verified | No | Scenario S5 shows the cost |
| A8 | Recall bias of not-on-list units is like that of listed units | No | Report not-on-list domain with a wider CI |
| A9 | Dropout is random given frame variables | No | Scenario S4; recall of dropouts as a check |
| A10 | Rotation rate one third per year | Design choice | Change $\delta_h$ |

---

## 17. Open decisions for the project owner

1. **One-stage vs two-stage selection.** This draft selects water bodies directly (one stage). A two-stage design (villages first, with probability proportional to water area, then ponds) would cut enumerator travel for verification but widen CIs through clustering. The draft keeps one stage because the diary is phone-based and only the verified subsample needs travel. Could be revisited if the department's field-cost data say otherwise.
2. **Precision target** (A6): 7.5% RSE per district is a proposal, not a department figure.
3. **Verification rate** (30%) and **rotation rate** (one third).
4. **Pilot districts:** one high-production, one medium-intensity, one geographically distinct (challenge page). The final choice should come from the department's data.
5. **Take-all cap** (section 4.4): keep 10% of $n_d$, or raise it so that fewer units of 2 ha or more stay in sampled strata. Not changed in v0.3. Test it in a later version, on new seeds.

---

## 18. Changes from v0.1 to v0.2 (2026-11-01)

The v0.1 simulation (exploratory, 1,000 replications, simulated; `results/REPORT.md` of that run) found that E3 missed AC1 (coverage 90.5%), AC2 (bias +2.3%), AC4 and narrowly AC5 in S1. With full response the bias was −0.18%, so selection and the ratio estimator were sound; the faults were in nonresponse handling, the variance formula and two design rules. All changes below were written before the confirmatory run (section 15.4).

| # | Section | v0.1 | v0.2 | Reason |
|---|---|---|---|---|
| 1 | 8.6, 8.7 | Linearised variance primary | Bootstrap primary; linearised as cross-check | Linearised SE 12% too low (no nonresponse term); bootstrap matched the empirical SD |
| 2 | 9 | 14-parameter weighted propensity model | 3-variable unweighted model, fixed in advance | About 2 events per parameter; needs about 10 |
| 3 | 9 | Propensity classes only | Classes, then calibration to $N_h$ and area $A_h$ per stratum | Removes bias that runs through area; lowers variance |
| 4 | 4.4 | Take-all when Neyman probability > 1 | Largest units ≥ 2 ha, up to 10% of $n_d$ | Old rule never fired |
| 5 | 5.2 | $\kappa$ in allocation | Removed | Cancels in Neyman allocation |
| 6 | 6, 8.9 | One $deff_w$ | Two forms; planning value refers to the nonresponse part | Full-weight Kish $deff$ (2.5) counted intended Neyman inequality |
| 7 | 8.7 | Resample $n'_h - 1$ respondents | Resample $n_h - 1$ selected units | Nonresponse step needs nonrespondents |
| 8 | 15.4 | AC4: linearised vs bootstrap | AC4: bootstrap vs empirical SD | The primary variance must match the true sampling SD |

**Readings adopted from the simulation build** (the doc was ambiguous; these become the rule): collapse (4.5) is applied before the minimum-5 rounding (5.2 step 3); phase-2 size is $m_h = \max(2, \mathrm{round}(0.3\,n'_h))$; take-all units count inside $n_d$; in S1 every phase-2 harvest is verified (A7 holds exactly).

---

## 19. Changes from v0.2 to v0.3 (2026-11-01, post-confirmation)

The v0.2 confirmatory run (seeds 20261102 / 4417, simulated) met AC1 to AC7. It also showed a weakness: in 28.7% of S1 replications at least one stratum missed its calibration constraints, and in 77.5% a factor sat at a bound. The failures were in small tank strata (6 to 10 selected, about 5 respondents) and rarely in stratum 2 (`results/v0.2/REPORT.md` section 4, item 1). The v0.2 results stay as the confirmatory record. Nothing in them is re-tuned.

| # | Section | v0.2 | v0.3 | Reason |
|---|---|---|---|---|
| 1 | 9 step 5 | Calibrate to $N_h$ and $A_h$ when a stratum has 4 or more respondents | Same, with 8 or more respondents; fewer gives $N_h$ only | Two constraints with $g \in [0.3, 3]$ cannot hold with about 5 respondents |
| 2 | 9 step 5 | After 20 iterations, keep truncated factors (constraint missed) | Fall back to $N_h$ only for that stratum | The v0.2 rule left a stratum that matches neither constraint; the doc was silent (REPORT section 5, item 1) |
| 3 | 4.4, 17 | Cap behaviour not stated | Stated; cap unchanged; open decision 5 | 48 of 68 units of 2 ha or more stay in sampled strata |

Not changed: the frame, strata, allocation, sample size, propensity model, bootstrap, and the S4/S5 biases (no mitigation is simulated yet). The samples are the same kind as in v0.2; only the calibration step differs.

**v0.3 check run (post-confirmation, not confirmatory).** Seeds fixed here before the run: `pop_seed = 20261103`, `master_seed = 5521`. 1,000 replications, S1 to S5. Both seeds are new. The run reports results as they come; nothing is tuned on them either.

| # | Criterion (S1, simulated) |
|---|---|
| V1 | Share of replications in which any stratum ends with an unmet constraint it attempted (after the fallback) is at most 5%. Also report the v0.2-style share (any miss before fallback) and the share with a factor at a bound. |
| V2 | The v0.2 criteria AC1 to AC5 hold again on the new seeds (coverage 93% to 97%, absolute bias below 1%, bootstrap SE within 10% of the empirical SD, RSE at most 7.5%). Judge them as a replication on a new district, not as a tuned result. |
| V3 | S2 to S5 reported honestly, with the change against v0.2 (coverage, bias, RSE). |
| V4 | Byte-identical rerun (AC7) still holds. |

To separate the effect of the fix from the effect of a new district, the report also runs the **v0.2 rule (threshold 4, no fallback) on the new seeds**, using a config switch. Both runs use identical samples.

---

## 20. Items from the independent estimator review (2026-11-01, v0.4 candidates)

A read-only review of `estimate.py`, `variance.py` and `nonresponse.py` by a second tool (Codex, run on 2026-11-01) reported two findings. I confirmed both by reading the code. Neither changes a headline result in sections 18 and 19. Neither is tuned on any seed.

**20.1 Tied propensities were split by row order (fixed, no design change).** Section 9 step 2 sorts units by predicted propensity and cuts them into 5 classes. Units with exactly equal predicted propensity (equal log area, intensity proxy and distance, which a frame with rounded areas can produce) were ordered by their position in the input, so a different row order could move a unit across a class boundary and change the estimate. Rule from now on: ties are broken by the unit's permanent random number (section 13), which depends only on the seed and the unit ID. The code takes an optional tie-break key. The simulation passes the PRN of each selected unit. Without a key the old behaviour (input order) remains, only for callers that have no unit IDs. Expected effect on the simulation: none, because simulated areas are continuous and ties do not occur. A test checks that a shuffled sample gives the same classes when a key is given.

**20.2 Take-all strata add no phase-2 variance to the bootstrap (open).** Section 8.6 says a take-all stratum still adds the phase-2 term when only a subsample of it is verified. Section 8.7 says take-all strata get $\lambda_h = 0$ and add no sampling variance. The code follows 8.7: with $f_h = 1$ the weights never change, and the set of verified units is fixed in every replicate, so the random choice of which take-all units are weighed adds no variance. The two sections disagree about take-all strata that are subsampled for verification. The phase-1 part of the statement in 8.7 is right ($f_h = 1$ means no phase-1 sampling variance). The phase-2 part is not covered.
- Likely size (inference, not tested): small. About 20 take-all units and about 6 of them verified. Bootstrap SE over empirical SD was 1.03 (v0.2 seeds) and 0.976 (v0.3 seeds) in S1.
- Options for v0.4: (a) keep the bootstrap, and state in 8.7 that the phase-2 term of take-all strata is left out; (b) resample the verified status inside take-all strata ($m_h - 1$ draws among the verified, rescaled), so the term is included. Option (b) needs a test against a hand-computed phase-2 variance. Choose after the deck, on new seeds, and write the choice here before any run.
- **Decision (2026-11-01): option (b), specified in section 21.1.**
- Until then, the proposal limits (section 9.6) state that the interval leaves out the phase-2 variance of take-all units.

---

## 21. Design v0.4: specification before code (2026-11-01)

**Status: draft for owner review. No v0.4 code exists yet.** This section fixes what v0.4 builds, how each part is tested, which seeds are used, and what counts as a pass. It is written before any run. It follows the rule of sections 18 and 19: no statistical change without a written criterion first, and nothing tuned on a seed that was already used. Numbers are simulated; labels [ASSUMPTION] mark placeholders.

**Seeds used so far (never tune on these):** 20261101/2026 (v0.1), 20261102/4417 (v0.2, confirmatory), 20261103/5521 (v0.3 check).

| Part | `pop_seed` | `master_seed` | Run |
|---|---|---|---|
| A. Main v0.4 run (S1 to S5: take-all variance, productivity, plausibility checks) | 20261104 | 6609 | 1,000 reps |
| B. Fay-Herriot test (scenario F) | 20261105 | 7703 | 1,000 reps |
| C. Rotating panel (scenario S6) | 20261106 | 8815 | 1,000 reps |

**Z0 (no-regression check, runs first).** With every v0.4 feature switched off, `--cal-rule v0.3` on seeds 20261103/5521 (30 reps, S1) must give a `replications.csv` that is byte-identical to `results/v0.3`. This is an identity check on old seeds, not tuning. New features that draw random numbers use separate `SeedSequence` children, so they cannot move the S1 to S5 streams.

### 21.1 Take-all phase-2 variance (closes section 20.2: option b)

**Decision: option (b).** Reason: option (a) leaves a known gap in the interval. Option (b) closes it with a small, testable change. The choice is fixed now and does not depend on the result of any run.

**Rule.** Inside a take-all stratum $h$ ($f_h = 1$, $n'_h$ respondents, $m_h$ verified), each bootstrap replicate also resamples the *verified* units: draw $m_h - 1$ of the $m_h$ verified units with replacement and rescale their phase-2 weights with the Rao–Wu form of section 8.7, using the phase-2 fraction $\lambda_h = \sqrt{1 - m_h / n'_h}$. Phase-1 weights of take-all units stay fixed. If $m_h < 2$, add no term and record the stratum. Other strata are unchanged (the existing bootstrap already carries phase-2 status).

**Expected value of the added term** (the target of the test): $N_h^2\,(1/m_h - 1/n'_h)\, s^2_{e,h}$, the second term of section 8.6 for that stratum.

| # | Criterion | Check |
|---|---|---|
| T1 | On a fixed take-all stratum with known $e_i$, the bootstrap variance of the stratum's phase-2 contribution matches the hand formula above within 2% (large $B$, fixed seed), in a stratum with equal phase-2 weights (one propensity class, no calibration). With unequal calibrated weights the hand formula is only approximate (a first attempt came out 12% low); a second test through the full bootstrap uses a 6% tolerance against $(X/\sum w_2 x)^2$ times the formula. | Unit test, hand-computed |
| T2 | With $m_h = n'_h$ (all verified) the added term is zero. | Unit test |
| T3 | S1, part A: AC1 to AC5 hold (coverage 93% to 97%, bias below 1%, bootstrap SE within 10% of the empirical SD, RSE at most 7.5%). Judge them as a replication on a new district. | Run |
| T4 | Paired diagnostic on the v0.3 seeds (20261103/5521, same samples): report mean bootstrap SE with and without the term. Option (b) stays whatever this shows. | Run, report only |

After T1 to T3 pass, edit section 8.6, 8.7 and the proposal §9.6 (the take-all gap statement). If T3 fails, report it; do not re-tune.

### 21.2 Productivity estimand

**Target:** $P_d = Y_d / A_d$ (t/ha), $Y_d$ the district production (list plus not-on-list), $A_d$ the total water area: frame area plus the not-on-list area estimated from the area frame (section 3.4). The simulation truth is $Y_d / A_d$ with the true areas.

**Estimator:** $\hat P_d = \hat Y_d / \hat A_d$. **Variance and interval:** from the bootstrap. Each replicate re-computes $\hat Y^*_d$ and $\hat A^*_d$ and forms $\hat P^* = \hat Y^* / \hat A^*$, so their covariance enters automatically. The CI uses the same $t$ rule (df $= m_d - H_d$). The linearisation of section 8.8 is the cross-check.

| # | Criterion (S1, part A) |
|---|---|
| P1 | Absolute relative bias of $\hat P$ below 1%. |
| P2 | Bootstrap coverage of $P$ between 93% and 97%. |
| P3 | Bootstrap SE within 10% of the empirical SD; the linearised SE is reported beside it. |
| P4 | $\hat P$ is also reported for S2 to S5, with the same honest reading as AC6. |

### 21.3 Event-level data and plausibility checks (section 10)

**Why:** section 10 has five event-level rules, but the simulation produces unit-year totals only. Event rules cannot be tested without events.

**Event table (new, simulated).** One row per harvest event: `event_id`, `unit_id`, `date` inside the reference year, `q_diary`, `q_ver` (empty if not verified), `seed_count`. Construction: split each unit's $y_i$ over `n_events` with Dirichlet(1) shares; $q_{diary}$ uses the unit's $x_i$ with the same shares; $q_{ver}$ uses $y_i$ shares for verified events (rate `verify_prob`). The event sums reproduce $x_i$ and $y_i$ exactly. `seed_count` is a placeholder rule: [ASSUMPTION] survival 0.5, mean harvest weight 0.8 kg, so seed $=y_i / (0.5 \times 0.8\ \mathrm{kg})$ with lognormal noise.

**Module (new, read-only on the sample).** It implements the five checks of section 10 and returns a flag table: `unit_id`, `event_id` or none, `check`, `value`, `threshold`. It never changes a value. The dashboard flag queue reads this table (empty state stays if the table is empty).

**Fault injection (test design).** On a copy, inject at known positions: 2% duplicate events, 2% events scaled ×10, 2% units with seed count below one tenth of what the production needs, 2% diary-vs-verified gaps above 50%.

| # | Criterion |
|---|---|
| C1 | Recall at least 90% for duplicates and ×10 events; at least 80% for seed-inconsistent units and gap events. |
| C2 | On the clean data, the share of units with a yield-outlier flag is at most 5%, and the share of events with any flag is at most 5%. Report each check separately. |
| C3 | Event sums equal unit totals to 1e-9. |
| C4 | The input tables have identical hashes before and after the checks (flag, never overwrite). |
| C5 | Estimating on the injected copy with flagged records excluded moves $\hat Y$ closer to the clean estimate than estimating on the injected copy without exclusion (the sensitivity estimate of section 10). |

C1, C2 and C5 run on 200 replications of S1 data from part A seeds; C3 and C4 on every replication.

### 21.4 Fay-Herriot test (section 11), scenario F

**Population.** Same synthetic district model, with one addition: a block effect on productivity, $\theta_b = \bar\theta (1 + \sigma_b\, u_b)$ with $u_b \sim N(0,1)$, [ASSUMPTION] $\sigma_b = 0.15$ in the primary case. The effect is drawn from a separate `SeedSequence` child, and $\sigma_b = 0$ reproduces the old district. **Blocks:** 10 per district (about 20 sampled units per block at $n = 200$), as in `Config.n_blocks`. A second stress case uses 30 blocks (about 7 units per block).

**Covariates $\mathbf{x}_b$:** log mean frame area, share of assisted units. (Seed supplied per ha is named in section 11 but is not simulated; it is left out and stated.) Both are known for every frame unit. They are correlated with the true block effect only through the model's existing area and assisted structure, so the covariates are informative but not perfect.

**Procedure per replication:** direct block estimates from E3 and their bootstrap variances; GVF smoothing of $\hat\psi_b$; Li–Lahiri adjusted REML for $\hat\sigma_v^2$; shrinkage; ratio benchmarking to the direct district estimate; Prasad–Rao MSE. The code uses `numpy`/`scipy` only; no new dependency.

| # | Criterion (primary case, 10 blocks, simulated) |
|---|---|
| F1 | Mean over blocks of MSE(FH) / MSE(direct) at most 0.85. |
| F2 | Mean coverage of the Prasad–Rao 95% interval between 92% and 97%. |
| F3 | Benchmarked block totals equal the direct district total to 1e-9. |
| F4 | Report the share of replications where unadjusted REML gives $\hat\sigma_v^2 = 0$ (the reason for Li–Lahiri). |
| F5 | No-harm: with $\sigma_b = 0$, the mean MSE ratio is at most 1.05. |

Stress case (30 blocks): report F1 to F4 only. No pass or fail; the proposal states that FH is experimental (section 11).

### 21.5 Rotating panel and composite estimator (section 12), scenario S6

**Population over three years.** Unit productivity persists: $\mathrm{prod}_{it} = \mathrm{base}_i \exp\!\big(s\,(\sqrt{\rho_u}\, z_i + \sqrt{1-\rho_u}\, \varepsilon_{it}) - s^2/2\big)$ with [ASSUMPTION] $\rho_u = 0.6$, plus a district trend of +3% a year [ASSUMPTION]. Area and frame are fixed. Truth $Y_t$ is known for $t = 1, 2, 3$. A sensitivity case uses $\rho_u = 0.3$.

**Samples.** PRN shift as in section 12: $u^{(t)}_i = (u_i + t\,\delta_h) \bmod 1$, $\delta_h = n_h / (3N_h)$. Take-all units stay in every year. The matched share between two consecutive years must be about two thirds.

**Estimator.** Year 1: composite = direct E3. For $t \ge 2$: $\hat Y''_t = (1-K)\hat Y_t + K(\hat Y''_{t-1} + \hat\Delta_t)$. $\hat\Delta_t = \hat Y^{M}_t - \hat Y^{M}_{t-1}$, where $\hat Y^{M}$ is E3 computed on the matched units only, with year-$t$ weights recalibrated to the same $N_h$ and $A_h$ in both years. $K$ is estimated in each replication from the bootstrap replicates (variance-minimising combination of $\hat Y_t$ and $\hat Y''_{t-1} + \hat\Delta_t$), clipped to $[0, 0.8]$. The bootstrap resamples the same selected units in both years.

| # | Criterion (primary case, simulated) |
|---|---|
| G1 | Matched share between consecutive years in $[0.63, 0.70]$; no unit is sampled in more than 3 years. |
| G2 | Year-3 RMSE of the composite / RMSE of the direct estimate at most 0.95 (the gain). |
| G3 | Year-2 and year-3 ratio at most 1.00 (no harm). |
| G4 | Composite absolute relative bias below 1.5% in years 2 and 3. |
| G5 | Composite bootstrap-CI coverage between 93% and 97% in years 2 and 3. |
| G6 | In the $\rho_u = 0.3$ case, ratio at most 1.00 (no harm). The gain may vanish. |

### 21.6 R cross-check

A second implementation of E3 point estimates and the Rao–Wu bootstrap in R, in a new `crosscheck/` folder, run on one fixed sample from part A. **Criterion X1:** point estimate agrees to 1e-6 relative, bootstrap SE to within 3% (different random streams, so not identical). R needs an install and the owner's approval first. If not installed, X1 is reported as not done.

### 21.7 Run order and reporting

1. Z0. 2. Unit tests T1, T2, C3, C4, F3 (deterministic, no seeds). 3. Part A run, then part B, then part C. 4. One `REPORT.md` per part in `results/v0.4*/`, each criterion marked met, narrowly met, or not met, with the number and its Monte Carlo SE. Failures stay in the report. 5. Then update proposal §3 and §9, which cite only what the reports show.

### 21.8 Not in v0.4

Changing the take-all cap (open decision 5), the S4 mitigation (dropout recall comparison), the separate-ratio fallback test, and an S5 mitigation. They stay listed as limits.

---

## Glossary

- **Stratum (plural strata):** a group of similar units sampled separately, for example "small assisted ponds in district 1".
- **Neyman allocation:** a rule that gives more sample to strata that are large and variable.
- **Take-all (certainty) stratum:** units that are always in the sample, because each one matters too much to leave to chance.
- **Two-phase (double) sampling:** a cheap measurement on a large sample (diary) plus an expensive one on a subsample (weighing), linked by a model.
- **Ratio estimator:** scales the cheap total by the expensive-to-cheap ratio seen on the subsample.
- **Permanent random number (PRN):** a fixed random number per unit; the smallest ones form the sample, so samples are reproducible and can rotate.
- **Relative standard error (RSE):** standard error divided by the estimate; 7.5% means the estimate typically misses the truth by about 7.5%.
- **Coverage:** the share of 95% CIs that contain the true value over many repeated samples. A correct method gives about 95%.
- **Fay-Herriot model:** a small-area model that blends a noisy direct estimate with a covariate-based prediction, by how noisy the direct estimate is.
- **Composite estimator:** a time-series estimate that uses the overlap between years to reduce variance.
- **Design effect ($deff$):** the variance of the actual design divided by the variance of a simple random sample of the same size.
- **Modified z-score:** an outlier score built from the median and MAD instead of the mean and SD.
