# NESFIC 2026 — Solution Proposal for NESFIC-D-32

**Challenge:** Scientific Sample Survey for Pond and Tank Aquaculture Production Estimation (Fishery Department, Assam)
**Applicant:** [NAME] (solo applicant) · **Advisor:** [TO NAME — statistics faculty, if confirmed]
**Working title:** [TO CHOOSE] — an open, reproducible survey engine for aquaculture production estimates
**Draft:** 0.1, 2026-11-01. Sections 3 and 9 wait for the confirmatory simulation results. Text in [brackets] is for the applicant to fill or confirm.

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

[PENDING — after the confirmatory simulation and the dashboard. Planned content:]
- User-flow diagram: frame freeze → seed commit → selection → listing → diary and monthly checks → verification → year-end recall → estimation → review → publication.
- Screens: harvest diary (phone), verification form, dashboard (district estimate with CI, response and verification rates, flag queue).
- Prototype maturity: working estimation engine with tests; simulation evidence; XLSForm schedules validated with pyxform; dashboard on simulated data. [Confirm the state at submission.]

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

[PENDING — after the confirmatory simulation run (design v0.2, fresh seeds). Planned content:]
- Simulation method: synthetic district with known true output; 1,000 repeated samples per scenario.
- Headline: 95% interval coverage of the proposed estimator, bias, and comparison with recall-only, diary-only and area × productivity methods (all labelled simulated).
- Stress tests: noisier diaries, unequal under-reporting, dropout linked to yield, incomplete verification — reported whether or not they pass.
- Reproducibility test: identical output from identical seed and frame.
- Software quality: automated tests (counts at submission), XLSForm validation.
- Honest record: the exploratory run found faults that were fixed in design v0.2 before the confirmatory run; both are documented.
- Prior work: FAO inland-fisheries sampling guidance, USDA NASS list-plus-area frames, World Bank harvest-diary studies, WorldFish satellite pond mapping (cited in the design document).

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
