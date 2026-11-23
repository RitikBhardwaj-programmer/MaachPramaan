# NESFIC 2026 — Solution Proposal for NESFIC-D-32

**Challenge:** Scientific Sample Survey for Pond and Tank Aquaculture Production Estimation (Fishery Department, Assam)
**Applicant:** Ritik Bhardwaj (solo applicant), B.Tech. Information Technology, NIT Srinagar
**Title:** Maach Pramaan ("fish proof") — an auditable sample survey for Assam's pond and tank fish production
**Version:** 1.0, November 2026. This proposal follows the 12 components of the Uniform Solution Proposal Requirements. Sections 3 and 9 are written from the simulation reports (runs v0.2 to v0.5 and the Fay-Herriot run). All results are simulated; no real Assam data has been used.
**Code, design document and run reports:** https://github.com/RitikBhardwaj-programmer/MaachPramaan. Paths such as `results/v0.5` and `docs/design.md` refer to this repository.

**At a glance.** Assam's pond and tank production is now estimated as water area × one assumed productivity, with no margin of error. Maach Pramaan replaces that with a scientific sample survey: about 200 ponds per district drawn by an auditable random rule, a short phone diary for every harvest, and enumerators weighing the harvests on a subsample of farms to correct the diaries. The engine turns this into district totals with 95% confidence intervals that anyone can re-run from the published seed. On five simulated districts with known truth (no real data used), the estimate's average error (bias) was at most 0.7% in the base case, and its intervals held the truth in 93.6% to 96.1% of 1,000 repeats; recall alone under-counted by about 27%. Field forms, the engine, an audit log and a dashboard exist as a working prototype on simulated data.

---

## 1. Problem understanding & user workflow

**The problem.** Assam has about 5.6 lakh ponds and tanks covering about 97,000 ha (NEDFI databank, 2023-24), most of them small (mean about 0.17 ha) and spread across villages. Their output is now estimated mainly from farmer recall and a single productivity figure applied to water area. The challenge statement lists the results: weak recall, harvests that are missed or counted twice, unrecorded home consumption and farm-gate sales, and one productivity assumption that ignores stocking, species, feeding and management. Published 2023-24 totals for the State differ between sources (about 4.74 to 4.99 lakh MT), which shows how uncertain the current figure is.

**Users and beneficiaries.**
| User | Need |
|---|---|
| Directorate of Fisheries, Assam (district and State officers) | Defensible district and State production estimates with stated uncertainty, every year |
| Field staff and enumerators | Simple digital schedules that work offline in villages |
| Fish farmers in the sample | A short harvest diary that takes under two minutes per harvest |
| Directorate of Economics & Statistics, ICAR-CIFRI, auditors | Methods and data they can check and reproduce |
| Planners (schemes, seed supply, credit) | Reliable production and productivity by district, type and intensity |

**Current workflow (as described in the challenge).** Resource data (water area) × an assumed productivity, supported by recall reports → a single figure without a confidence interval.

**Gaps addressed.**
1. No probability sample: results cannot carry a margin of error.
2. Recall bias: farmers under-report or forget harvests.
3. Partial harvests are missed or double-counted.
4. One productivity figure for all ponds.
5. The resource list is incomplete or out of date, and nothing measures by how much.
6. The method cannot be reproduced or audited by a third party.

**Intended outcome.** A documented, repeatable sample survey that produces district and State production estimates **with 95% confidence intervals**, from diaries checked by field weighing, and that any reviewer can re-run from the frozen frame and the published seed.

---

## 2. Proposed solution & key features

An open-source survey engine that covers the whole chain: **design → select → capture → verify → estimate → audit**. Field capture uses KoboToolbox / ODK Collect (free, offline, already used in government surveys); the engine does what those tools do not do: sample design, estimation with uncertainty, and a verifiable audit trail.

| Module | What it does | What changes versus today |
|---|---|---|
| Frame manager | Loads the updated fishery-resource frame, freezes it with a cryptographic hash, checks IDs and areas | A versioned frame instead of a working list |
| Sample designer | Stratifies by district, type, size and intensity proxy (scheme and seed records); Neyman allocation; take-all class for the largest farms | Sample effort goes where variation is |
| Selector | Selects with permanent random numbers from a published, committed seed; rotates one third of the sample each year | Anyone can re-run the selection; panels rotate without re-drawing |
| Field schedules | Listing, per-harvest diary (one record per harvest event), monthly check, weighing verification, end-of-year recall, in English and Assamese | Harvest-level records instead of yearly recall |
| Verification | A random subsample of farms has every harvest weighed by an enumerator | Diary error is measured, not assumed |
| Coverage check | A sample of 1 km² grid cells is fully listed to find ponds missing from the list | List incompleteness is measured and corrected |
| Estimator | Two-phase ratio estimator, nonresponse weighting and calibration to known area, bootstrap confidence intervals | Every estimate carries a 95% interval |
| Quality checks | Outlier and consistency flags (yield, seed, duplicates, diary vs weighed) sent to a review queue | Flag, review, keep the original; never silently overwrite |
| Dashboard | District and State estimates with intervals, response and verification rates, flags, coverage | Uncertainty and data quality are visible |
| Audit log | Append-only, hash-chained log of every load, selection, upload, review and estimate run | Tamper-evident, reproducible results |

**User interaction.** The farmer records each harvest on a phone form (or a paper card copied by the enumerator). The enumerator visits monthly, weighs harvests on verification farms, and does the year-end recall. District officers see the dashboard. A State statistician or auditor re-runs any estimate from the run record.

---

## 3. User journey, wireframes & prototype

### 3.1 User journey

```
Department            Statistician            Enumerator              Farmer                 Officer / auditor
    |                      |                       |                     |                          |
 1. frame  ------------> 2. freeze frame
    (CSV)                   (SHA-256 hash)
                         3. commit seed (hash published)
                         4. design + select (PRN) ---> selection list
                                               5. listing visit (consent, area, GPS,
                                                  species, stocking, feeding)
                                                                    6. harvest diary: one phone
                                                                       form per harvest event
                                               7. monthly check (finds missed events)
                                               8. weigh every harvest on ~30% of
                                                  farms (announced ahead)
                                               9. year-end recall + not-on-list interview
                         10. estimate: checks and flags -> weights -> ratio -> bootstrap
                         11. review flag queue (original values kept)
                         12. reveal seed, publish run record ----------------------------> 13. re-run, check, use
```

A farmer touches steps 5, 6 and 7 only. Each submission is one short form. The statistician owns steps 2 to 4 and 10 to 12. Step 13 is what makes the estimate auditable: with the frozen frame, the revealed seed and the code version, a reviewer can re-run the selection and the estimates and compare.

### 3.2 Screens and wireframes

The five field schedules exist as working XLSForms (section 3.3). The wireframes below show the first two as they appear on a phone, and the dashboard layout. A first dashboard is built on simulated output (section 3.3); the layout below is the target for the MVP.

**Harvest diary (farmer, phone, English and Assamese).** One submission per harvest event. When the whole harvest has one use ("all sold" or "all used at home"), the kilogram split questions do not appear.

```
+-----------------------------+      +-----------------------------+
| Harvest record      EN | অ  |      | How was it used?            |
|                             |      |  ( ) All sold               |
| Pond ID   [ P-004217 ]      |      |  ( ) All used at home       |
| Date      [ 2026-11-01 ]    |      |  ( ) Divided in parts  -->  |
| Type      ( ) Partial       |      |      sold      [ 40 ] kg    |
|           ( ) Final         |      |      home      [ 12 ] kg    |
| Fish      [ Indian major    |      |      gift/labour/other ...  |
|             carps      v ]  |      |                             |
| Quantity  [ 52 ] kg         |      | Note: parts add to 52 kg    |
|                             |      |                             |
| [ Back ]          [ Next ]  |      | [ Back ]         [ Submit ] |
+-----------------------------+      +-----------------------------+
```

A warning appears as a note when a value looks wrong (for example one harvest above 2,000 kg). The farmer can always continue; the record is flagged for review and never blocked or overwritten.

**Verification form (enumerator).** The enumerator scans or types the event code, picks "weighed" or "crates", and enters the weight or the crate count and crate weights. The form shows the farmer's stated amount beside the verified amount and the relative difference, and flags a difference above 50%.

**Dashboard (statistician and district officer), target layout.**

```
+--------------------------------------------------------------------+
| D-32 production estimate      Reference year [2026-27 v]  SIMULATED|
+----------------+---------------------------------------------------+
| District       |  Estimated production (t)  with 95% interval       |
| [ All       v ]|   District A   ----[=====o=====]----               |
| Type [ All  v ]|   District B   ------[===o===]------               |
|                |   District C   ---[========o========]---           |
+----------------+---------------------------------------------------+
| Response   | Verified events | Not-on-list share | Flags to review |
|  88% (n)   |   54% (n)       |  7.3%             |  12 open        |
+--------------------------------------------------------------------+
| Flag queue: id | rule | value | diary vs verified | [Keep][Edit*]  |
|             (* an edit adds a new value; the original stays)        |
+--------------------------------------------------------------------+
| Run record: frame hash | seed | code version | [Download CSV]      |
+--------------------------------------------------------------------+
```

### 3.3 Prototype maturity (state at 2026-11-09)

| Component | State | Evidence |
|---|---|---|
| Statistical design | Written, version 0.5 | `docs/design.md`; every change and its pass criteria are written before the run that tests it |
| Selection and estimation engine | Working in Python, on simulated data only | 140 automated tests pass |
| Simulation | Recorded runs on six synthetic districts (the first exploratory); 1,000 repeats per scenario in the main runs | Section 9 |
| Data-quality checks | Coded: duplicates, gaps, seed consistency, ×10 slips, diary vs weighed, yield outliers; flag only, never overwrite | Section 9.4 |
| Productivity (t/ha) with interval | Coded and tested in simulation | Section 9.2 |
| Field schedules | Five XLSForms, English and Assamese, pass ODK Validate | Assamese labels are machine-drafted and still need a native-speaker check |
| Dashboard | First version built (Streamlit) on simulated output: estimates with intervals, quality tiles, coverage over repeats, run record | Flag queue and district filter not yet connected |
| Seed commitment and hash-chained audit log | Coded: seed commit and reveal, frame hash, append-only hash-chained log | Unit tests (`tests/test_audit.py`) |
| Fay-Herriot block estimates | Coded and tested in simulation; experimental | Section 9.5 |
| Rotating panel and composite estimator | Coded and tested in simulation; no precision gain yet | Section 9.5 |

No real Assam data has been used. The prototype is shown on simulated data and will be rebuilt on the department's frame when it is available.

---

## 4. Technology & solution architecture

**Stack (all open source).**
| Layer | Choice | Why |
|---|---|---|
| Field capture | XLSForm on KoboToolbox or ODK Collect (Android, offline) | Free, proven in government surveys, no custom app to maintain |
| Storage | Parquet files + DuckDB (embedded SQL) for the pilot; PostgreSQL for State scale | Simple to host; scales without a redesign |
| Engine | Python: numpy, pandas, scipy, statsmodels | Standard, auditable numerical stack |
| Cross-check | R `survey` and `sae` packages on the same data | An independent implementation checks the estimates |
| Dashboard | Streamlit | Fast to build, runs on a department server |
| Audit | SHA-256 hashes, HMAC-based random numbers, hash-chained log | Standard cryptographic primitives; no blockchain needed |
| Hosting | A department or State Data Centre server; no foreign cloud dependency | Data stays in the State's control |

**Methods (summary; full statistical design in the attached design document).**
- **Sampling unit:** one pond or tank in the updated resource frame.
- **Strata:** district × type × size class × intensity proxy; a take-all class for the largest farms (≥ 2 ha).
- **Allocation:** Neyman allocation inside each district, equal precision target across districts.
- **Selection:** permanent random numbers from HMAC-SHA256(seed, unit ID); rotation of one third per year.
- **Estimator:** total = (weighted diary total) × (weighed ÷ diary ratio on the verified subsample), plus an area-frame estimate for ponds missing from the list. The ratio uses only harvests that were both recorded and weighed.
- **Verification rate:** about 30% of responding farms to start; a mid-year check raises it (up to 80%) when the predicted error is above the precision target.
- **Nonresponse:** farmers who stop the diary still answer the year-end recall, which stands for all dropouts in their stratum (double sampling); the rest by response-propensity classes, then calibration to the frame's known counts and water area.
- **Uncertainty:** Rao–Wu rescaled bootstrap re-running the whole pipeline, including which of the largest farms are weighed; 95% intervals with a t multiplier.
- **Productivity:** production ÷ water area (t/ha), with its own interval.
- **Sub-district:** Fay-Herriot small-area model for development blocks, shown beside direct estimates (experimental in the pilot).
- **Over time:** one third of the sample rotates each year, so each farm keeps a diary for about three years; a composite estimator using the overlap is tested but not yet relied on (section 9.5).

**Data flow.** Frame (department) → frozen and hashed → selection list → forms on phones → sync to Kobo/ODK server → nightly export → engine (checks, flags, estimates) → dashboard and run records → audit log.

**Integrations.** Imports the department's resource frame, scheme beneficiary records and fish-seed records (CSV/Excel). Exports estimates and microdata in CSV for DES and ICAR-CIFRI.

---

## 5. Development methodology & intermediate steps

| Step | Output |
|---|---|
| 1. Requirements with the department | Confirmed frame fields, reference year, precision target, pilot districts |
| 2. Statistical design | Design document (done, version 0.5: strata, allocation, estimators, variance, assumptions) |
| 3. Simulation proof | Synthetic districts with known truth; coverage, bias and stress tests (done for the main design; see section 9) |
| 4. Engine prototype | Selection, estimation, bootstrap, audit log, with automated tests (done on simulated data) |
| 5. Field schedules | XLSForms in English and Assamese, validated; field-tested with a few farmers |
| 6. MVP | Engine + forms + dashboard on the department's real frame for the pilot districts |
| 7. Testing and refinement | Re-run the simulation on the real frame's size distribution; independent R cross-check; usability fixes from field staff |
| 8. Validation readiness | Run record, operations manual, enumerator training material |

Each step ends with a reviewable artefact. Statistical changes are written into the design document **before** they are tested, so results cannot be tuned after the fact.

---

## 6. Development timeline & milestones

Aligned with the NESFIC programme stages (prototype Nov 2026 – Feb 2027, Demo Day Feb 2027, MVP Feb – May 2027).

| Period | Milestone | Deliverable | Dependency |
|---|---|---|---|
| Nov 2026 | M1 Design and simulation | Design document v1, simulation report | — |
| Dec 2026 | M2 Requirements confirmed | Frame specification, pilot districts, precision target | Department meeting |
| Dec 2026 – Jan 2027 | M3 Engine prototype on the real frame | Selection list for the pilot districts; frame hash and seed commitment | Frame received |
| Jan 2027 | M4 Forms field test | Revised XLSForms; Assamese labels checked by native speakers | Field staff access |
| Feb 2027 | M5 Demo Day prototype | End-to-end demo: forms → engine → dashboard | M3, M4 |
| Feb – Apr 2027 | M6 MVP | Dashboard, flag review queue, audit log, R cross-check | — |
| May 2027 | M7 Ready for pilot validation | Operations manual, training material, run record | — |

The pilot itself runs over one full reference year (April – March) after M7.

---

## 7. Data & information requirements

**Development and testing need no real data.** The engine is developed and tested on simulated districts calibrated to published Assam figures. This is stated as an assumption: access to department data at the proposal stage is not confirmed, and none is assumed.

**For the MVP and the pilot (listed by the department as available, subject to its arrangements):**
| Data | Format | Use | Processing |
|---|---|---|---|
| Updated fishery-resource frame | CSV/Excel with unit ID, location, type, area | Sampling frame, strata, calibration totals | De-duplication, ID check, hash and freeze |
| Historical production | Tables by district and type | Planning productivity, sample sizes, plausibility bounds | Aggregation only |
| Fish-seed supply records | Tables by farm or village | Intensity proxy; seed-consistency check | Linkage to frame IDs |
| Scheme beneficiary records | Lists | Intensity proxy | Linkage to frame IDs |
| Access to sampled farms and field support | — | Diaries, weighing, recall | Enumerator scheduling |
| Free Sentinel-2 imagery | GeoTIFF | Stratifies the 1 km² grid cells for the coverage check | Water index; no pond census from imagery |

**Assumptions** (each with a fallback in the design document): the frame has stable IDs; scheme and seed records can be linked to frame units; most verification-farm harvests can be announced a day ahead.

**Dependencies.** Calibrated scales for enumerators; mobile coverage at least weekly for sync (forms work offline in between).

---

## 8. Team, manpower & expertise

| Role | Person | Expertise | Phases |
|---|---|---|---|
| Lead developer and survey methods | Ritik Bhardwaj, B.Tech. Information Technology (2024–2028), NIT Srinagar | Python, statistics, data engineering; built the engine and simulation with AI coding assistants (see below) | All |
| Field and domain partner | Directorate of Fisheries (as offered in the challenge) | Aquaculture practice, field operations | Requirements, field test, pilot |
| Possible collaborators | DES Assam, ICAR-CIFRI (as named in the challenge, subject to department arrangements) | Official statistics, inland fisheries methodology | Review, cross-check |

**Indicative manpower.** Development (Nov – May): 1 full-time developer. Pilot (per district, one year): about 2 enumerators and 1 supervisor, 3 enumerators if diaries prove noisy and weighing doubles. Estimate: listing, monthly checks, weighing visits and year-end recall come to about 400 enumerator-days a year, against about 220 working days per enumerator; to be confirmed with department norms.

**Critical specialist skills.** Survey sampling and variance estimation; field-protocol design for weighing; Assamese language review of forms.

**Use of AI tools.** The code, simulation reports, documents and Assamese draft labels were produced with AI assistants: Anthropic Claude Code for building and OpenAI Codex for read-only code review. The applicant set the requirements, took the design decisions and is responsible for the result. No human statistician has reviewed the work yet; review by DES Assam or ICAR-CIFRI is sought for the pilot.

---

## 9. Testing, validation & evidence

**All numbers in this section are simulated.** No real data has been used, and access to department data at this stage is not assumed. The simulation shows how the method behaves when the true answer is known. It does not show what Assam's production is.

### 9.1 Method

A synthetic district has 20,000 listed water bodies and 1,600 that are not on the list. Its mean area (about 0.17 ha) and total area are set from published Assam figures; other parameters are assumptions. The parameters are in the open code, each tagged as documented, sourced or assumed. The true production of every water body is known, so the true district total is known (for example 14,439.8 t in the confirmatory run, simulated). Each test draws 200 water bodies, runs the full survey (non-response, diaries, weighing on a subsample, recall) and produces an estimate with a 95% interval. This is repeated 1,000 times per scenario. Two measures follow:
- **Bias:** the average error of the estimate, as a share of the truth. Near zero is good.
- **Coverage:** the share of the 1,000 intervals that contain the truth. A correct 95% interval should land near 95%. The accepted band was fixed in advance at 93% to 97%.

Four estimators are compared on the same samples: area × a single productivity figure (E0, today's method, with a placeholder of 4.89 t/ha), farmer recall only (E1), diary only (E2), and the proposed diary-plus-weighing estimator (E3).

**The rule since the confirmatory run.** Each design change and its pass criteria are written into the design document first. The run then uses a new synthetic district and seeds that were never used before, and nothing is tuned after it. Failures stay in the report. The runs so far:

| Run | Purpose | Seeds (population / master) | Report |
|---|---|---|---|
| v0.1 | Exploratory: first test of the design | 20261101 / 2026 | `results/v0.1-exploratory` |
| v0.2 | **Confirmatory**: fixes from v0.1, fixed in advance | 20261102 / 4417 | `results/v0.2` |
| v0.3 | Follow-up: calibration fallback (post-confirmation) | 20261103 / 5521 | `results/v0.3` |
| v0.4 | Take-all variance and productivity; data-quality checks | 20261104 / 6609 | `results/v0.4`, `results/v0.4-plausibility` |
| v0.4 FH | Fay-Herriot block estimates | 20261105 / 7703 | `results/v0.4-fh` |
| v0.4 panel | Rotating panel over three years | 20261106 / 8815 | `results/v0.4-panel` |
| v0.5 | Fixes for the weak scenarios | 20261107 / 9931 | `results/v0.5` |

### 9.2 Main result (base case S1)

Confirmatory run (v0.2):

| Estimator | Bias | 95% interval coverage |
|---|---|---|
| E0 Area × one productivity figure | +14.65% | no interval |
| E1 Recall only | −27.11% | 8.0% |
| E2 Diary only | −12.25% | 38.7% |
| **E3 Proposed (diary corrected by weighing)** | **+0.68%** | **96.1%** |

Recall alone under-counts by about a quarter, and a diary alone by about an eighth. Their intervals almost never contain the truth, because they are centred on the wrong value. The proposed estimator has a small bias, and its intervals contain the truth in 96.1% of repeats (Monte Carlo standard error 0.6 points). Its relative standard error is 6.95%, below the 7.5% target; the bootstrap standard error is 1.03 times the real spread of the estimates, so the reported uncertainty is about right. (Figure 1: `results/v0.2/coverage_plot.png`, first 100 intervals per scenario; the E0 gap depends on the placeholder productivity and must not be read as an error of the department.)

**The result repeats on new districts.** The same base case on four more synthetic districts, each with new seeds:

| Run (design version) | True total (t) | E3 bias | Coverage | Relative standard error | E1 recall bias |
|---|---|---|---|---|---|
| v0.2 (confirmatory) | 14,439.8 | +0.68% | 96.1% | 6.95% | −27.1% |
| v0.3 | 14,838.5 | +0.09% | 93.6% | 7.00% | −26.8% |
| v0.4 | 14,935.8 | +0.06% | 94.6% | 7.14% | −27.1% |
| v0.4, Fay-Herriot district (block effect added) | 13,470.4 | +0.02% | 96.1% | 6.47% | −27.6% |
| v0.5 (current design) | 14,358.7 | +0.10% | 95.3% | 6.99% | −27.7% |

Every row is inside the 93% to 97% band and below the 7.5% precision target. The current design (v0.5) uses about 70 weighed farms per district instead of 55, because its mid-year check adds verification when the predicted error is high.

**Productivity (t/ha).** The design also estimates productivity, production ÷ water area, with its own interval. Base case: bias +0.04%, coverage 94.7% (v0.4); bias +0.12%, coverage 95.0% (v0.5). It behaves like the total because water area is estimated with little error.

### 9.3 Stress tests

The first column is the confirmatory v0.2 run. The second is design v0.5 (three fixes written into the design before the run; new district and new seeds, 1,000 repeats each; `results/v0.5/REPORT.md`). All numbers are simulated.

| Scenario | What goes wrong | v0.2: bias / coverage | v0.5: bias / coverage | Reading |
|---|---|---|---|---|
| S2 | Diaries are noisier (correlation with truth 0.7 instead of 0.9) | +1.62% / 96.0%, RSE 11.7% | +0.25% / 94.6%, **RSE 8.3%** | Intervals stay honest. v0.5 raises verification mid-year when the predicted error is too high (up to 80% of respondents); RSE falls from 11.7% to 8.3% but **does not reach the 7.5% target**, and verification visits more than double. A noisy diary is a cost question |
| S3 | Diary under-reporting differs by group (−5% and −20%) | +0.66% / 96.1% | +0.12% / 95.8% | One ratio still gives an unbiased total |
| S4 | Farmers drop out when their yield is poor | **+3.97%** / 95.7% | **+0.55%** / 96.1% | **Fixed.** Dropouts still answer the year-end recall (70% assumed); their recall, corrected by the weighed/recall ratio, stands for all dropouts (double sampling for non-response) |
| S5 | Only 75% of harvests on verification farms are weighed | **−1.92%** / 93.1% | **+0.22%** / 94.6% | **Fixed.** The weighed/diary ratio now uses only the harvests that were both recorded and weighed |
| S4x (stress) | As S4, and dropouts recall 10% worse | n/a | −0.11% / 95.3% | The S4 fix tolerates this |
| S5x (stress) | Farms that under-report are weighed less often | n/a | **−4.15% / 86.9%** | **Fails, as expected.** No formula can fix weighing that avoids the under-reporters; it needs unannounced spot checks and a per-farm verified share |

I report these whether or not they pass. S2 and S5x show where the design needs money and field discipline rather than statistics.

### 9.4 Data-quality checks (flag, never overwrite)

Each harvest record is checked, and a doubtful one goes to a review queue with its original value kept. Tested on simulated harvests with planted errors (v0.4 district, 200 repeats; `results/v0.4-plausibility`):

| Planted error | Share caught | Pass mark |
|---|---|---|
| Duplicate harvest | 100% | 90% |
| Seed stocking inconsistent with harvest | 100% | 80% |
| Missing harvest (gap) | 100% | 80% |
| Weight entered ×10 | 73.3% | 70% |

False alarms on clean records were low for each rule (0.02% to 4.9%), except the diary-vs-weighed check: it flagged **8.7% of clean harvests against an 8% limit**, and all rules together 12.9% against 12%. Both limits are **not met** and were not re-tuned. In practice the review queue would hold about one harvest in eight. The ×10 check misses about a quarter of slips, mostly on small harvests, where a tenfold value still looks normal.

### 9.5 Block estimates and the rotating panel (experimental)

District samples are too small for direct block estimates (about 18 farms per block). The Fay-Herriot model (a small-area model that blends each block's own noisy estimate with a prediction from block features) was tested on a district with real differences between blocks (v0.4 estimator; `results/v0.4-fh`). Against the direct block estimate it cut the mean squared error to **0.55** (pass mark 0.85), with **95.0%** interval coverage, and it did no harm when blocks do not differ (0.52). All five criteria were met.

The run also found a defect that the criteria do not catch. The step that smooths each block's variance uses the block's own estimate, so a block that comes out low by chance is trusted more. Before the final scaling to the district total, block estimates came out 4.7% low on average (26% with 30 smaller blocks). After it, single blocks were still off by up to 10%. The fix (smoothing without the block's own estimate, plus a per-block bias criterion) is listed for the next version and not yet tested. Block estimates therefore stay **experimental**, shown beside the direct estimates.

**Rotating panel (three years, `results/v0.4-panel`).** The composite estimator, which combines this year's estimate with last year's plus the change measured on farms in both samples, stayed unbiased (−0.4% or less) with 94% to 95% coverage and did no harm. But it gave almost no gain: year-3 error 0.983 of the direct estimate's, against a target of 0.95 (**not met**). The rotation rule also missed its own limit: about 9% of farms stayed in the sample more than three years in a row. The panel stays in the design for continuity and to spread the diary burden, not for precision; rotation by explicit groups is listed for the next version.

### 9.6 Honest record

1. **Exploratory run first.** The first version of the design (v0.1) failed four of its own criteria: bias +2.3%, interval coverage 90.5%, and the standard-error check. The faults were in the non-response step, the variance formula and two design rules.
2. **Fix, then test on new data.** The fixes were written into the design document before any new run (section 18 of the design). The confirmatory run used a new synthetic district and new seeds, and nothing was tuned on them. Result: all seven criteria met in the base case.
3. **A later change, and its cost.** The confirmatory run showed that the area-calibration step fails in about 29% of repeats, in small tank strata. Design v0.3 changed that step. On a third district (new seeds, labelled post-confirmation, not confirmatory), the change removed every unmet calibration constraint (35.9% to 0.0% on identical samples) and cut base-case bias from +0.55% to +0.09%. It also **lowered interval coverage**: 93.6% in the base case (inside the band, 0.6 points above its lower edge) and 90.7% in S5 (outside). We report both numbers. The takeaway is that the method is sound but its intervals have little margin when verification is incomplete, so the pilot must track the verified share.
4. **Which result is confirmatory.** In the exploratory run, the bootstrap interval was adopted as the main interval after the results were seen, so its 96.4% coverage there is post hoc. Only the v0.2 run, with the bootstrap fixed in advance, is confirmatory.
5. **Fixing the weak scenarios (v0.5).** S4, S5 and S2 were fixed in the design first, with pass criteria, before any run. A separate read-only review by an AI tool, on throw-away seeds, then found four faults in the first code, among them a stopping-rule bias in the mid-year rule. These were fixed before the confirmation run. On a new district, the S4 and S5 fixes pass, the base case still meets every criterion (coverage 95.3%, bias +0.10%, RSE 6.99%), and S2 misses its precision target (8.3% against 7.5%). The cost is extra weighing: about 70 weighed farms per district instead of 55 in the base case.
6. **A gap found by review, then closed.** A separate read-only code review by an AI tool found that the interval left out which of the largest (take-all) farms get weighed. The fix was specified with three tests (design section 21.1); all three pass, and base-case coverage with the fix is 94.6% on a new district.
7. **Checks that fail their own limits.** The diary-vs-weighed check raises more false alarms than its limit allows at full district size (section 9.4), the block-estimate run found a bias that its criteria missed, and the rotating panel missed its gain and time-in-sample limits (section 9.5). All are reported, not re-tuned.

### 9.7 Reproducibility and software quality

- **Same seed, same frame, same output.** Two runs of the same 30 repeats gave byte-identical files (SHA-256 identical), for both the confirmatory and the follow-up seeds. With the v0.5 changes switched off, the new code reproduces 150 of 150 rows of the earlier run exactly.
- **Selection does not depend on list order.** Each unit's random number comes from HMAC-SHA256 of the seed and the unit ID, so re-sorting the frame changes nothing (tested).
- **140 automated tests pass.** They cover selection, allocation, take-all, calibration (including the fallback), hand-computed ratios and variances, the v0.5 fixes, the data-quality checks, Fay-Herriot, the rotating panel and the audit log. Deliberately broken versions of the v0.5 code (7 of 7) are caught by the tests.
- **Separate AI review.** Read-only reviews of the estimator code by AI tools found two faults in v0.3 and four in the first v0.5 code; each was fixed before the run that tested it. These reviews do not replace a human statistician's review.
- **Field forms.** All five XLSForms pass ODK Validate. The Assamese labels are machine-drafted and need a native-speaker check before field use.
- **Not yet done:** a paired check of the take-all variance fix on identical samples; an independent cross-check in R (`survey`); field testing with farmers.

### 9.8 Limits

- The synthetic district is a model. Real within-stratum spread may be larger: the simulated coefficient of variation is about 1.6 against 0.7 in the planning table. The sample will be re-sized from year-one data, and the intervals stay valid at any size.
- Coverage is checked on one synthetic population per run. Five districts gave base-case coverage between 93.6% and 96.1%, so a different district moves coverage by one to two points.
- The pilot, not the simulation, decides whether farmers keep diaries and whether harvests are announced.
- The v0.5 fixes rest on stated assumptions: weighing does not follow a farm's diary error; dropouts recall like respondents; about 70% of dropouts answer the year-end recall. The stress tests show the first is critical (bias −4.2% when it fails) and the second is not (−0.1% with a 10% recall shift). The pilot measures all three.

### 9.9 Prior work

FAO inland-fisheries sampling guidance, USDA NASS list-plus-area frames, World Bank harvest-diary studies, WorldFish satellite pond mapping (sources are cited in the design document).

---

## 10. Security, privacy, safety & compliance

| Area | Approach |
|---|---|
| Personal data | Farmer name and phone kept only in the field system; the analysis data uses pseudonymous unit IDs. Collected under informed consent recorded in the listing form. Handled in line with the Digital Personal Data Protection Act, 2023 (purpose limitation, minimal data, retention limits). Any added department data policy is to be confirmed at the requirements step (M2). |
| Access control | Role-based access on the Kobo/ODK server and the dashboard (enumerator, supervisor, district officer, statistician) |
| Hosting | On a department or State Data Centre server; no third-party analytics |
| Integrity | Frame hash, seed commitment, hash-chained append-only log; each estimate run records the code version and data hash |
| Auditability | Anyone with the frozen frame and revealed seed can re-run the selection and the estimates |
| Human review | Automated checks only flag records; a reviewer decides, and the original value is always kept |
| Interoperability | Open formats (CSV, Parquet, XForm); estimates exportable to DES |
| Safety | Weighing protocol avoids handling live fish beyond normal harvest practice; no field step adds risk to farmers |

---

## 11. Innovation & differentiation

**Novel element.** One open, reproducible pipeline that joins sample design, field capture, harvest-level verification, estimation with uncertainty and a tamper-evident audit trail. Existing tools cover parts: KoboToolbox, ODK and Survey Solutions capture data; R and Stata estimate. No tool found joins design, capture, verification, estimation and audit (search-based finding, not exhaustive).

**Prior art and how this differs.**
| Existing approach | Limitation | This proposal |
|---|---|---|
| Area × fixed productivity | No error estimate; ignores management differences | Probability sample with confidence intervals |
| Yearly recall surveys | Recall bias; missed partial harvests | Per-harvest diary corrected by weighing |
| List-only sampling | Silent undercoverage | Area-frame check measures and corrects it |
| Fresh sample every year | Noisy year-to-year change; no continuity | Rotating panel: two thirds of farms carry over, each keeps a diary about three years |
| Satellite pond mapping (e.g. WorldFish, Bangladesh) | Area, not production; small ponds are hard to see at 10 m | Imagery only guides the coverage check |

**Basis of differentiation.** Proven statistical behaviour by simulation before field use, and reproducibility by design: committed seed, permanent random numbers, frozen frame.

**IP and dependencies.** Released under the Apache License 2.0, so the department can use, change and maintain it without licence fees; every contributor also grants the patent rights their code needs. Dependencies: Python scientific stack, KoboToolbox/ODK, Streamlit, R `survey`/`sae` (all open source).

---

## 12. Resources, risks & pilot validation

**Cost drivers (indicative).** Development: developer time, a small server. Pilot: enumerator days (driven mainly by verification visits), calibrated scales, phones or tablets, mobile data. Whether existing department field staff can do this work is not confirmed; it is a question for the requirements step (M2), and if they cannot, enumerator pay is an added cost.

**Key risks and mitigations.**
| Risk | Mitigation |
|---|---|
| Frame lacks stable IDs or linkable scheme/seed records | Engine builds and freezes IDs; stratify by size and type only if linkage fails |
| Farmers stop keeping diaries | Two-minute form, monthly checks; dropouts still answer the year-end recall, which stands for all dropouts (removes the yield-related bias in simulation); dropout reported openly |
| Harvests on verification farms not announced | Ratio uses only harvests both recorded and weighed (removes the bias in simulation); unverified events counted; unannounced spot checks, because weighing that avoids under-reporting farms still biases the total |
| Diaries noisier than planned | Mid-year check raises the weighing rate (up to 80% of respondents) when the predicted error is above 7.5%; budget for up to about twice the planned weighing visits |
| Real variation larger than planned | Sample re-sized from year-one data; intervals stay honest even if wider |
| Small samples per block | Fay-Herriot estimates shown beside direct ones, marked experimental; in simulation they cut the mean squared block error by about 45%, but single blocks can be off by up to 10% until the variance-smoothing fix is tested |
| Solo developer, no statistical advisor | Open code, design document and tests let others maintain it; main estimator changes get a read-only AI code review before the run that tests them; statistical review by DES Assam or ICAR-CIFRI sought for the pilot |

**Pilot validation (after development).** Three contrasting districts, as the challenge suggests (high-production, medium-intensity, geographically distinct), chosen from the department's data. About 200 farms per district, about 55 to 70 of them with weighed harvests (more if diaries prove noisy), plus about 30 grid cells per district for the coverage check (sizes to be confirmed from the real frame). Over one reference year, compare: the proposed estimate with its interval; the department's current figure; recall versus weighed amounts on the same farms (a direct measure of recall bias); and the measured share of ponds missing from the list. Success criteria are agreed with the department before the pilot starts.
