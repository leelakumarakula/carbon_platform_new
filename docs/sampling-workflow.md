# Stratification, sampling design and field collection (Phase 5)

All geometry decisions are made by **SQL Server** (`geography`). This covers:
- union and area of strata;
- containment of points in farm and project boundaries;
- distances between points and to GPS fixes.

Python only proposes candidate coordinates (`rules/sampling_points.py`, pure and seeded).

## Strata (`project_strata`, `stratum_characteristics`, `stratum_farms`)

- **Contents:** a stratum is a set of participating farms plus characteristics:
  - SOIL_TYPE, CROP, LAND_USE, MANAGEMENT_PRACTICE, IRRIGATION, GEOGRAPHY, CLIMATE, OTHER.
- **Geometry and area:** the stratum geometry is the SQL Server `UnionAggregate` of the farms' current boundaries.
  `area_hectares` comes from SQL Server.
- **Farm rules:**
  - A farm may belong to only one current stratum (`FARM_ALREADY_STRATIFIED`).
  - Farms must be ACTIVE participants of the project (`FARM_NOT_IN_PROJECT`).
- **Versioned** (`record_id`, `version`, `is_current`):
  - DRAFT strata are edited in place.
  - An APPROVED stratum is never silently modified. A change needs a reason (`REASON_REQUIRED`) and creates a
    new DRAFT version (`REVISION_EXISTS` if one is already open).
  - Approving the revision supersedes the old version.
- **Approval:**
  - needs `sampling.review` (GIS specialist / field supervisor), not by the creator;
  - is refused when the methodology's `stratification_variables` are configured and a required characteristic is
    missing (`CHARACTERISTICS_REQUIRED`).

## Sampling design (`sampling_designs`, `sampling_design_versions`, `sampling_design_strata`)

- **Scope:** one design (code) per monitoring period, with versions DRAFT → APPROVED → SUPERSEDED. Only one version
  is APPROVED.
- **Parameters:**
  - statistical design: STRATIFIED_RANDOM, SIMPLE_RANDOM, SYSTEMATIC_GRID or OTHER;
  - target precision and confidence;
  - CV and minimum detectable difference;
  - sampling method;
  - depth top/bottom;
  - minimum distance between points;
  - repeat-sampling note;
  - random seed (generated if omitted, always stored);
  - per-stratum **sample count**.
- **Sample counts** are configured explicitly. There is **no "1 sample per X acres" rule**.
- **Methodology values:** configured values (depth, design, minimum samples, precision, confidence) are enforced
  (`METHODOLOGY_REQUIREMENT`). Others are listed as CONFIGURATION_REQUIRED gaps, and `requirement_source` becomes
  PROJECT_CONFIGURED.
- **Strata:** only APPROVED strata can be allocated.
- **Approval:** needs `sampling.review`, not by the creator.

## Sampling points (`sampling_points`)

`POST /sampling-designs/{id}/generate-points` (`sampling.manage`, approved version, once per version):

1. **Candidates per stratum:**
   - Random designs use seeded uniform candidates in the stratum's bounding box.
   - SYSTEMATIC_GRID uses a seeded-offset grid with spacing √(area/n), tightened until enough nodes fall inside.
2. **Containment:** SQL Server keeps candidates inside a farm boundary of the stratum and returns the farm and
   boundary (`STIntersects`, one round trip per batch).
3. **Spacing:**
   - Points keep `min_distance_m` from each other.
   - They keep ≥ 1 m (`SAMPLING_DUPLICATE_DISTANCE_M`) from every existing point of the period, measured by SQL
     Server.
   - The project-boundary containment is double-checked.
4. **All or nothing:** if a stratum cannot fit its count within the attempt budget, nothing is written
   (`INSUFFICIENT_AREA`).
5. **Codes:** points get `SP-YYYY-NNNNNN` codes.
6. **Older versions:** PLANNED or ASSIGNED points of older design versions are cancelled.

The same seed and boundaries reproduce the same points.

### Relocation (`sampling_point_relocations`)

- **Request:** the assigned collector or a sampling manager requests a new location with a reason.
  - The new location must be inside the same farm (`OUTSIDE_FARM`).
  - It must not duplicate another point (`DUPLICATE_POINT`).
  - Only one request may be pending (`RELOCATION_PENDING`).
- **Recorded:** old and new coordinates, the SQL Server distance, requester and time.
- **Decision:** a `sampling.review` holder (not the requester) approves or rejects with notes. Only an approval moves
  the point, audited as `SAMPLING_POINT_UPDATED`.

## Assignment (`sampling_assignments`)

- **Who:** supervisors (`sampling.assign`) assign points, singly or in bulk, to users holding `sampling.collect` in
  the project organization (`NOT_A_COLLECTOR`). A planned date must fall within the period (`OUTSIDE_PERIOD`).
- **Reassigning** marks the old assignment REASSIGNED. Completing a collection marks it COMPLETED.
- **Collectors** see only their own points (`mine=true`; collectors without `mrv.read` are always limited). They
  never approve anything.

## Field collection (`field_collection_records`)

`IN_PROGRESS → SUBMITTED → ACCEPTED | RETURNED`, plus `RETURNED → SUBMITTED` and `ACCEPTED → SUPERSEDED`
(correction).

- **Code:** `FIELD-YYYY-NNNNNN`.
- **Start:** only the assigned collector, while the period is ACTIVE or DATA_COLLECTION. One open record per point.
- **Recorded:**
  - collection time;
  - GPS (lat/lon/accuracy, stored as `geography`);
  - actual depth;
  - sample quantity and unit;
  - observations;
  - the checklist items completed, against the checklist version frozen on the record (platform default
    `PLATFORM-DEFAULT-1`: `location_confirmed`, `depth_measured`, `sample_labelled`, `photo_taken`).
- **GPS checks:** SQL Server computes the **distance from the planned point** and whether the GPS lies **inside the
  farm**.
- **Submit requires:**
  - time, GPS, depth;
  - the full checklist;
  - at least one FIELD_PHOTO;
  - a date within the period and not in the future;
  - the minimum number of field photos recorded on the record (platform default 1);
  - a deviation note when the GPS is further than the record's tolerance (platform default 30 m) or outside the farm.

  On submit the point becomes COLLECTED.
- **Review** (`sampling.review`, not the collector) ACCEPTS or RETURNS with notes. A return sends the point back to
  ASSIGNED.
- **Corrections** of an accepted record create a new version (`supersedes_id`, reason). The accepted version stays
  until the new one is accepted.

The mobile screens are `/field` and `/field/collections/:id`:
- large touch targets;
- device GPS via `navigator.geolocation`, with manual entry as a fallback;
- camera capture for photos.

Offline capture is not built yet (listed in the known limitations).

## Decisions (Phase 5 review, approved 3 Oct 2026)

- **S1 — GPS tolerance 30 m and duplicate threshold 1 m** are kept as **platform defaults**, not universal methodology
  requirements. A methodology version may configure `gps_max_distance_m` / `duplicate_point_distance_m`. The value used and
  its source are stored on the design version and on every field record; historical records never change.
- **S2 — the four checklist items and at least one photo per sample** are kept as **platform defaults** (checklist version
  `PLATFORM-DEFAULT-1`). They are not presented as VM0042, CCTS or other methodology requirements. A methodology version may
  configure `field_checklist` / `min_photos_per_sample`. Each record stores the checklist version, the items completed, the
  collector, timestamps, photos and evidence; changing the checklist never alters historical records.

See the table "Platform defaults vs methodology requirements" in [mrv-workflow.md](mrv-workflow.md).

## Assumptions needing confirmation (OPEN DECISION REQUIRED)

- **S3** — Strata may be approved by the GIS specialist or the field supervisor (`sampling.review`).
- **S4** — Sampling-point generation algorithms (seeded random / grid) are project-configured. If a methodology
  prescribes an algorithm, it must be configured as a SAMPLING rule and implemented then.
