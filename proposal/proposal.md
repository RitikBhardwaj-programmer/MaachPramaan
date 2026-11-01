# NESFIC 2026 — Solution Proposal for NESFIC-D-32

**Challenge:** Scientific Sample Survey for Pond and Tank Aquaculture Production Estimation (Fishery Department, Assam)
**Applicant:** [NAME] (solo applicant) · **Advisor:** [TO NAME — statistics faculty, if confirmed]
**Working title:** [TO CHOOSE] — an open, reproducible survey engine for aquaculture production estimates
**Draft:** 0.2, 2026-11-01. Sections 3 and 9 are written from the simulation results (v0.2 confirmatory, v0.3 follow-up). Section 3 will need updating when the dashboard exists. Text in [brackets] is for the applicant to fill or confirm.

> Drafting notes (delete before submission): follows the 12 components of the Uniform Solution Proposal Requirements (USPR). Portal field limits are not known yet (behind login); each section is written so it can be cut to its first paragraphs. All simulation numbers must stay labelled "simulated". No real Assam data has been used.

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

The five field schedules exist as working XLSForms (section 3.3). The wireframes below show the first two as they appear on a phone, and the dashboard layout. The dashboard is a **design sketch, not built yet**.

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

**Dashboard (statistician and district officer), planned layout.**

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

### 3.3 Prototype maturity (state at 2026-11-01; confirm at submission)

| Component | State | Evidence |
|---|---|---|
| Statistical design | Written, version 0.3 | `docs/design.md`; changes are written before each test run |
| Selection and estimation engine | Working in Python, on simulated data only | 42 automated tests pass |
| Simulation | Done: confirmatory run (v0.2) and a labelled follow-up (v0.3) | Section 9 |
| Field schedules | Five XLSForms, English and Assamese, pass ODK Validate | Assamese labels are machine-drafted and still need a native-speaker check |
| Dashboard | Not built | Layout above; will run on simulated output |
| Seed commitment and hash-chained audit log | Specified in the design (section 13), not coded | Planned for the prototype stage |
| Fay-Herriot block estimates, rotating panel | Specified, not coded | Planned for the MVP stage |

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
- **Estimator:** total = (weighted diary total) × (weighed ÷ diary ratio on the verified subsample), plus an area-frame estimate for ponds missing from the list.
- **Nonresponse:** response-propensity classes, then calibration to the frame's known counts and water area.
- **Uncertainty:** Rao–Wu rescaled bootstrap re-running the whole pipeline; 95% intervals with a t multiplier.
- **Sub-district:** Fay-Herriot small-area model for development blocks, shown beside direct estimates (experimental in the pilot).
- **Over time:** composite estimator using the overlap between years.

**Data flow.** Frame (department) → frozen and hashed → selection list → forms on phones → sync to Kobo/ODK server → nightly export → engine (checks, flags, estimates) → dashboard and run records → audit log.

**Integrations.** Imports the department's resource frame, scheme beneficiary records and fish-seed records (CSV/Excel). Exports estimates and microdata in CSV for DES and ICAR-CIFRI.

---

## 5. Development methodology & intermediate steps

| Step | Output |
|---|---|
| 1. Requirements with the department | Confirmed frame fields, reference year, precision target, pilot districts |
| 2. Statistical design | Design document (done in draft: strata, allocation, estimators, variance, assumptions) |
| 3. Simulation proof | Synthetic district with known truth; coverage, bias and stress tests (done in draft; see section 9) |
| 4. Engine prototype | Selection, estimation, bootstrap, audit log, with automated tests |
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
| Lead developer and survey methods | [NAME], [programme, institution] | Python, statistics, data engineering; built the engine and simulation | All |
| Statistical advisor | [TO NAME — statistics faculty, if confirmed] | Survey sampling, small-area estimation | Design review, validation |
| Field and domain partner | Directorate of Fisheries (as offered in the challenge) | Aquaculture practice, field operations | Requirements, field test, pilot |
| Possible collaborators | DES Assam, ICAR-CIFRI (as named in the challenge, subject to department arrangements) | Official statistics, inland fisheries methodology | Review, cross-check |

**Indicative manpower.** Development (Nov – May): 1 full-time developer, advisor 2–4 hours per month. Pilot (per district, one year): about 2 enumerators and 1 supervisor, sized from the verification workload [to confirm with department norms].

**Critical specialist skills.** Survey sampling and variance estimation; field-protocol design for weighing; Assamese language review of forms.

---

## 9. Testing, validation & evidence

**All numbers in this section are simulated.** No real data has been used, and access to department data at this stage is not assumed. The simulation shows how the method behaves when the true answer is known. It does not show what Assam's production is.

### 9.1 Method

A synthetic district has 20,000 listed water bodies and 1,600 that are not on the list. Its mean area (about 0.17 ha) and total area are set from published Assam figures; other parameters are assumptions. The parameters are in the open code, each tagged as documented, sourced or assumed. The true production of every water body is known, so the true district total is known (14,439.8 t, simulated). Each test draws 200 water bodies, runs the full survey (non-response, diaries, weighing on a subsample, recall) and produces an estimate with a 95% interval. This is repeated 1,000 times per scenario. Two measures follow:
- **Bias:** the average error of the estimate, as a share of the truth. Near zero is good.
- **Coverage:** the share of the 1,000 intervals that contain the truth. A correct 95% interval should land near 95%. The accepted band was fixed in advance at 93% to 97%.

Four estimators are compared on the same samples: area × a single productivity figure (E0, today's method, with a placeholder of 4.89 t/ha), farmer recall only (E1), diary only (E2), and the proposed diary-plus-weighing estimator (E3).

### 9.2 Main result (base case S1)

| Estimator | Bias | 95% interval coverage |
|---|---|---|
| E0 Area × one productivity figure | +14.65% | no interval |
| E1 Recall only | −27.11% | 8.0% |
| E2 Diary only | −12.25% | 38.7% |
| **E3 Proposed (diary corrected by weighing)** | **+0.68%** | **96.1%** |

Recall alone under-counts by about a quarter, and a diary alone by about an eighth. Their intervals almost never contain the truth, because they are centred on the wrong value. The proposed estimator has a small bias, and its intervals contain the truth in 96.1% of repeats (Monte Carlo standard error 0.6 points). Its relative standard error is 6.95%, below the 7.5% target; the bootstrap standard error is 1.03 times the real spread of the estimates, so the reported uncertainty is about right. (Figure 1: `results/v0.2/coverage_plot.png`, first 100 intervals per scenario; the E0 gap depends on the placeholder productivity and must not be read as an error of the department.)

### 9.3 Stress tests

| Scenario | What goes wrong | E3 bias | Interval coverage | Reading |
|---|---|---|---|---|
| S2 | Diaries are noisier (correlation with truth 0.7 instead of 0.9) | +1.62% | 96.0% | Intervals stay honest but widen: RSE 11.7%. Expected fix (inference, not simulated): more verified units or a larger sample |
| S3 | Diary under-reporting differs by group (−5% and −20%) | +0.66% | 96.1% | One ratio still gives an unbiased total |
| S4 | Farmers drop out when their yield is poor | +3.97% | 95.7% | **Bias is real.** Frame variables cannot see a yield shock. Mitigation: compare the recall of dropouts with that of respondents; not simulated yet |
| S5 | Only 75% of harvests on verification farms are weighed | −1.92% | 93.1% | **At the bottom of the band.** Mitigation: announce harvests a day ahead; report the verified share |

I report these whether or not they pass. S4 and S5 show where the design needs field discipline.

### 9.4 Honest record

1. **Exploratory run first.** The first version of the design (v0.1) failed four of its own criteria: bias +2.3%, interval coverage 90.5%, and the standard-error check. The faults were in the non-response step, the variance formula and two design rules.
2. **Fix, then test on new data.** The fixes were written into the design document before any new run (section 18 of the design). The confirmatory run used a new synthetic district and new seeds, and nothing was tuned on them. Result: all seven criteria met in the base case.
3. **A later change, and its cost.** The confirmatory run showed that the area-calibration step fails in about 29% of repeats, in small tank strata. Design v0.3 changed that step. On a third district (new seeds, labelled post-confirmation, not confirmatory), the change removed every unmet calibration constraint (35.9% to 0.0% on identical samples) and cut base-case bias from +0.55% to +0.09%. It also **lowered interval coverage**: 93.6% in the base case (inside the band, 0.6 points above its lower edge) and 90.7% in S5 (outside). We report both numbers. The takeaway is that the method is sound but its intervals have little margin when verification is incomplete, so the pilot must track the verified share.
4. **Which result is confirmatory.** In the exploratory run, the bootstrap interval was adopted as the main interval after the results were seen, so its 96.4% coverage there is post hoc. Only the v0.2 run, with the bootstrap fixed in advance, is confirmatory.

### 9.5 Reproducibility and software quality

- **Same seed, same frame, same output.** Two runs of the same 30 repeats gave byte-identical files (SHA-256 identical), for both the confirmatory and the follow-up seeds.
- **Selection does not depend on list order.** Each unit's random number comes from HMAC-SHA256 of the seed and the unit ID, so re-sorting the frame changes nothing (tested).
- **42 automated tests pass.** They cover selection, allocation, take-all, calibration (including the fallback), a hand-computed ratio and variance, and a property test that weights stay valid.
- **Field forms.** All five XLSForms pass ODK Validate. The Assamese labels are machine-drafted and need a native-speaker check before field use.
- **Not yet done:** independent cross-check in R (`survey`); the rotating-panel scenario; the productivity estimate; Fay-Herriot block estimates; field testing with farmers.

### 9.6 Limits

- The synthetic district is a model. Real within-stratum spread may be larger: the simulated coefficient of variation is about 1.6 against 0.7 in the planning table. The sample will be re-sized from year-one data, and the intervals stay valid at any size.
- Coverage is checked on one synthetic population per run. The v0.3 follow-up shows that a different district moves coverage by one to two points.
- The interval leaves out one small source of variance: which of the largest (take-all) farms get weighed. An independent code review found this gap. It is recorded in the design document (section 20.2) with two options to close it. The effect is probably small (inference, not tested): the bootstrap standard error matched the real spread within 3% in the base case.
- The pilot, not the simulation, decides whether farmers keep diaries and whether harvests are announced.

### 9.7 Prior work

FAO inland-fisheries sampling guidance, USDA NASS list-plus-area frames, World Bank harvest-diary studies, WorldFish satellite pond mapping (sources are cited in the design document).

---

## 10. Security, privacy, safety & compliance

| Area | Approach |
|---|---|
| Personal data | Farmer name and phone kept only in the field system; the analysis data uses pseudonymous unit IDs. Collected under informed consent recorded in the listing form. Handled in line with the Digital Personal Data Protection Act, 2023 (purpose limitation, minimal data, retention limits) [confirm department policy]. |
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
| Fresh sample every year | Noisy year-to-year change | Rotating panel with composite estimator |
| Satellite pond mapping (e.g. WorldFish, Bangladesh) | Area, not production; small ponds are hard to see at 10 m | Imagery only guides the coverage check |

**Basis of differentiation.** Proven statistical behaviour by simulation before field use, and reproducibility by design: committed seed, permanent random numbers, frozen frame.

**IP and dependencies.** Released under an open-source licence [choose: Apache-2.0 or MIT] so the department owns and can maintain it. Dependencies: Python scientific stack, KoboToolbox/ODK, Streamlit, R `survey`/`sae` (all open source).

---

## 12. Resources, risks & pilot validation

**Cost drivers (indicative).** Development: developer time, a small server. Pilot: enumerator days (driven mainly by verification visits), calibrated scales, phones or tablets, mobile data. Mostly existing department field staff can be used [confirm].

**Key risks and mitigations.**
| Risk | Mitigation |
|---|---|
| Frame lacks stable IDs or linkable scheme/seed records | Engine builds and freezes IDs; stratify by size and type only if linkage fails |
| Farmers stop keeping diaries | Two-minute form, monthly checks, dropout weighting and calibration; dropout reported openly |
| Harvests on verification farms not announced | Unverified events counted and reported; simulation shows the effect |
| Real variation larger than planned | Sample re-sized from year-one data; intervals stay honest even if wider |
| Small samples per block | Fay-Herriot estimates shown beside direct ones, marked experimental |
| Solo developer | Open code, design document and tests let others maintain it; advisor review |

**Pilot validation (after development).** Three contrasting districts, as the challenge suggests (high-production, medium-intensity, geographically distinct), chosen from the department's data. About 200 farms per district, about 50 of them with weighed harvests, plus about 30 grid cells per district for the coverage check (sizes to be confirmed from the real frame). Over one reference year, compare: the proposed estimate with its interval; the department's current figure; recall versus weighed amounts on the same farms (a direct measure of recall bias); and the measured share of ponds missing from the list. Success criteria are agreed with the department before the pilot starts.
