# Data lineage

Target chain (spec section 35), and which links exist after each phase:

```
CREDIT → REGISTRY → VERIFICATION → CALCULATION RUN → METHODOLOGY VERSION → INPUT DATASET → LAB RESULT → SAMPLE
       → SAMPLING POINT → STRATUM → FARM → PROJECT → FARMER
```

| Link | Where it is stored | Phase |
|---|---|---|
| Farmer → farm | `farms.farmer_id` (operator); owner(s) in `farm_ownership` | 2 |
| Farm → boundary version | `farms.current_boundary_id`; every version kept in `farm_boundaries` | 2 |
| Farm → history | versioned `farm_land/crop/practice_history` (`record_id`, `version`, `is_current`) | 2 |
| Project → farm participation | `project_farms` with the **farm boundary version** and area used when the farm joined | 3 |
| Participation → carbon rights | `project_carbon_rights` (agreement / document / reference, review) | 3 |
| Project boundary → farm boundaries | `project_boundaries.farm_boundary_ids` (exact versions in each union) | 3 |
| Project → standard / activity | `project_standards`, `project_activities` (history) | 3 |
| Project → methodology + version | `project_methodologies` (LOCKED) with the evaluation result, specialist review and the three rule-set revisions | 4 |
| Methodology version → candidate decision | `methodology_evaluations` (facts snapshot, engine version) → `methodology_evaluation_results` (per-rule results) → `project_methodology_reviews` | 4 |
| Project → MRV plan version | `mrv_plans` (locked `project_methodology_id`, methodology version, measurement definitions, CONFIGURATION_REQUIRED gaps and who acknowledged them) | 5 |
| Monitoring period → plan | `monitoring_periods.mrv_plan_id`, `methodology_version_id` | 5 |
| Stratum → farms (boundary versions) | `project_strata` (versioned, SQL Server union geometry) → `stratum_farms.farm_boundary_id` | 5 |
| Sampling point → design version → stratum version | `sampling_points` (`design_version_id`, `stratum_id`, `farm_boundary_id`); the design version stores the **random seed** and allocations, so generation is reproducible | 5 |
| Sampling point → relocations | `sampling_point_relocations` (old/new location, distance, reason, requester, reviewer) | 5 |
| Field collection → point, collector, GPS, evidence | `field_collection_records` (versioned, `supersedes_id`) → `mrv_evidence` (`document_id`, SHA-256) | 5 |
| Monitoring record → measurement → plan | `monitoring_records` (versioned) | 5 |
| MRV dataset → everything above | `mrv_datasets.snapshot` (frozen JSON of plan, period, design versions, strata, points, accepted collections, records, evidence checksums) + `snapshot_sha256`, re-verified on approval; `mrv_qa_reviews` | 5 |
| Field collection → (later) physical sample → lab result | Decision V2: sample-based parameters (SOC, bulk density, …) are authoritative only as an APPROVED laboratory result. Phase 5 stores no analytical value; the field collection record is the anchor of the Phase 6 sample (`lab_samples.field_collection_id`) | 5 → 6 |
| Monitoring record → authority | Decision V2-B: each snapshot record carries `origin` (METHODOLOGY / PROJECT_CONFIGURED), `measurement_source`, `data_role` and `authoritative`. User-created/custom measurements are supplementary observations and are not authoritative laboratory results or authoritative calculation inputs. Authoritative analytical parameters originate from methodology-defined monitoring rules and their declared measurement provenance. A calculation may only use authoritative methodology records and approved laboratory results | 5 |
| Field collection version → sample → root sample / splits | `lab_samples` (`field_collection_id` kept forever, `root_sample_id`, `parent_sample_id`, point, farm, period, methodology version, engagement) | 6 |
| Sample → custody | `sample_custody_events` (append-only, ordered `sequence_no`, actor / organization / side / seal / shipment / document) and `lab_shipment_items` (receipt condition, observed seal) | 6 |
| Methodology rule → test → result versions | `lab_tests` (engagement, rule, MRV plan measurement, retest chain) → `lab_results` (versioned, supersedes, report document + SHA-256, analyst, source) → `lab_result_qa_reviews` (append-only) | 6 |
| Approved laboratory result → everything above | `GET /lab/results/{id}/lineage`: result → versions → test → sample / root → field collection version → point → stratum → farm → project → locked methodology rule → plan measurement, plus shipments, receipts, QA reviews, custody. Exactly one APPROVED result per root sample + rule | 6 |
| Calculated value → run → methodology version, calculation rules, module and engine versions | `calculation_runs` (frozen lock, `input_snapshot` + `input_sha256`, `output_sha256`, net result) → `calculation_outputs` (rule, inputs, earlier outputs) → `calculation_inputs` (source type, ID, version, exact value, unit) → approved lab result / monitoring record / stratum version → sample, field collection, point, stratum, farm, farmer, project (`GET /calculations/runs/{id}/lineage`); recalculations linked by `recalculation_of_run_id`, supersession by `superseded_by_run_id` | 7 |
| Approved run → findings, report, readiness | `calculation_findings` (+ events; targets inside the run) → `calculation_reports` (content and PDF SHA-256) → `calculation_readiness_reviews` (manifest + SHA-256 referencing project, periods, methodology lock, dataset snapshot, MRV evidence, laboratory reports, run hashes, report hashes, findings, QA) — in the run lineage API | 8A |
| VVB decision → assignment → submission → readiness → manifest → report → run | `verification_decisions` (report + manifest SHA-256, VVB organization, user) → `verification_assignments` (COI, replacement chain) → `verification_submissions` (readiness review, run, report, manifest SHA-256; SUPERSEDED / INVALIDATED never mutated) → Phase 8A readiness and below; findings and corrective actions with append-only events. `GET /verification/decisions/{id}/lineage` (embeds the Phase 7 run lineage for calculation readers) | 8B |
| Credit batch → issuance → registry submission → VVB decision | `credit_serial_ranges` (verbatim registry serials) → `credit_batches` (registry-stated vintage) → `credit_issuances` (registry issuance ID, evidence SHA or API hash, confirmer; corrections reference the original) → `registry_submissions` (frozen registry-submission-v1 snapshot + SHA-256 referencing the decision, verification submission, readiness, report, run, methodology, dataset) → `registry_project_registrations` (registry project ID) → the 8B / 7 chains. `GET /credits/batches/{id}/lineage` ends at farms and farmer codes | 9A |
| Retirement → ledger entries → positions → batch | `credit_retirements` (registry retirement reference, registry-stated date and serials, RETIREMENT_CERTIFICATE) → its RETIREMENT_REQUEST / RETIRE entries → consumed `credit_positions` (each `created_by_entry_id` back through TRANSFER_COMPLETE / RESERVE / … entries) → OPEN_INVENTORY → `credit_batches` → the 9A chain (credits.read only; holders stop at the batch). `GET /credits/retirements/{id}/lineage` | 9B |
| Ownership history | every movement is one posted `credit_ledger_entries` row with its input (consumed) and output (created) positions, actor and confirmer; conservation (inputs = outputs; open = issued) checked by a DB trigger | 9B |
| Order → listing → 9B reservation / transfer → batch | `orders` / `order_items` (price and quantity snapshots) → `marketplace_listings` (disclosure snapshot + SHA-256) → the item's 9B `credit_reservations` and `credit_transfers` (`purpose_reference` = item code) → the TRANSFER_COMPLETE ledger entry → `credit_batches` → the 9A chain (credits.read only; buyers stop at the batch). `GET /orders/{id}/lineage` | 10 |
| Payments, refunds | `payments` (evidence PDF, recorder, confirmer) → append-only `payment_events` (payload SHA-256) → `refunds` (evidence, requester, approver); money is never linked to a carbon quantity | 10 |
| Revenue, payouts | — | 11 |

Reverse lineage, from a farm up to its projects, works through `project_farms` (`GET /projects/my-participation` for the
farmer's own farms; project farms lists for staff). Every link above is written in the same transaction as its
audit-log entry.
