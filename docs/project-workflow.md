# Project workflow (Phase 3)

Code: `backend/app/services/{project_service,project_farm_service,catalog_service}.py`, state machine in
`backend/app/services/workflows.py` (`PROJECT_MACHINE`). Every status change is checked against the machine and
its readiness checklist. Each change writes three records in the same transaction:
- a `workflow_events` row;
- an `audit_logs` row;
- an append-only `project_status_history` row with who, when, why and the request ID.

Phase 3 builds the project data structure only. **No methodology is selected and nothing is calculated, verified
or issued.** `projects.methodology_status` stays `NOT_SELECTED`; Phase 4 adds methodology selection.

## Entities (spec §41: farmer ≠ farm ≠ project ≠ participation ≠ carbon rights)

| Concept | Table | Notes |
|---|---|---|
| Project | `projects` | code `PRJ-YYYY-nnnnnn`, organization-scoped, `environment` |
| Participation | `project_farms` | farm + farmer + period + farm boundary version used. Removal ends it; nothing is deleted |
| Carbon rights | `project_carbon_rights` | holder, share, agreement / document / reference, validity, review status |
| Team | `project_participants` | the user must already hold the role. A project role never adds permissions |
| Standard / activity | `project_standards`, `project_activities` | selection history, one current row each |
| Crediting period | `project_crediting_periods` | proposed periods; replacing one supersedes it |
| Baseline metadata | `project_baselines` | versioned period, description and data sources. No calculation |
| Boundary | `project_boundaries` | derived by SQL Server and versioned. GIS review is recorded per version |
| Documents | `project_documents` → `documents` | PROJECT_DESIGN, CARBON_RIGHTS, BASELINE_DATA, AGREEMENT, GEOSPATIAL_FILE, OTHER |
| Status history | `project_status_history` | append-only (trigger) |
| Catalog | `standards`, `activities`, `standard_activities` | reference entries; environment-scoped (DEMO entries cannot be used by LIVE projects) |

## Project status

The database allows all 20 lifecycle states of spec §8. Phase 3 implements only these transitions:

```
DRAFT ─▶ DATA_COLLECTION ─▶ ELIGIBILITY_REVIEW ─▶ STANDARD_SELECTED ─▶ ACTIVITY_SELECTED
  │            ▲   │                │                    │                    │
  │            │   └──▶ CLOSED      └─(returned)─▶ DATA_COLLECTION ◀─(re-open)┘
  └──▶ CLOSED  └────────────────────────────────────────────────────────────────
```

| Transition | Endpoint | Who | Requires |
|---|---|---|---|
| DRAFT → DATA_COLLECTION | `start-data-collection` | projects.manage | a Project Manager on the team |
| DATA_COLLECTION → ELIGIBILITY_REVIEW | `submit` | projects.manage | see the submit checklist below |
| ELIGIBILITY_REVIEW → STANDARD_SELECTED | `approve-eligibility` | projects.review, **not the submitter** | GIS accepted the current boundary; all active carbon-rights records verified; no OPEN farm overlap flags; a standard selected |
| ELIGIBILITY_REVIEW → DATA_COLLECTION | `return` | projects.review | a reason |
| STANDARD_SELECTED → ACTIVITY_SELECTED | `confirm-activity` | projects.manage | the activity is offered under the selected standard |
| STANDARD_SELECTED / ACTIVITY_SELECTED → DATA_COLLECTION | `reopen` | projects.manage | a reason; eligibility must be reviewed again |
| DRAFT / DATA_COLLECTION / STANDARD_SELECTED / ACTIVITY_SELECTED → CLOSED | `close` | projects.manage | a reason (terminal in Phase 3) |

Submit (DATA_COLLECTION → ELIGIBILITY_REVIEW) requires all of the following:
- at least one farm;
- every farm still VERIFIED, with an ACTIVE farmer;
- an active carbon-rights record for every farm;
- a valid, up-to-date project boundary;
- a standard and an activity selected;
- a proposed crediting period;
- baseline metadata;
- a Project Manager on the team.

A design document is recommended but not required.

There are no transitions into METHODOLOGY_REVIEW or later states (CALCULATED, VERIFIED, ISSUED, ACTIVE, …). A test
proves they are unreachable. Later phases add them.

**Editing rules.** Farms, carbon rights, crediting period, baseline, standard and project details can change only
in DRAFT and DATA_COLLECTION. The activity can also change in STANDARD_SELECTED. The team and documents can change
in any state except CLOSED. Anything else is refused with `PROJECT_NOT_EDITABLE`.

## Adding a farm

- The farm must be **VERIFIED**, its farmer **ACTIVE**, and it must belong to the project's organization and
  environment.
- The request records the participation period, the farm boundary version in use (for lineage) and **at least
  one carbon-rights record**. The rights must be evidenced by a signed farmer agreement, a CARBON_RIGHTS document
  attached to the project, or a reference text.
- **Conflicts are shown, never auto-rejected** (spec §41):
  - Open or confirmed farm-overlap flags and active participation in another project with overlapping dates are
    returned as `CONFLICTS_REQUIRE_ACKNOWLEDGEMENT`.
  - The farm can be added once the conflicts are acknowledged with a note.
  - A snapshot of the conflicts is stored on the participation; the eligibility reviewer decides.
- Removing a farm sets `REMOVED`, ends its participation and active carbon-rights records, recomputes the
  boundary, and keeps everything.

## Project boundary (SQL Server geography)

- `geography::UnionAggregate` over the **current** boundaries of the active farms. SQL Server computes:
  - the area, with overlapping farm areas counted once;
  - the plain sum of farm areas;
  - the internal overlap (sum − union);
  - the validity check.
- Computed automatically when farms are added or removed, and again at submit if any farm boundary changed. It can
  also be recomputed on demand.
- **Stale detection.** If a farm's boundary changes (Phase 2 re-open), the project boundary is flagged stale, GIS
  review is refused (`BOUNDARY_STALE`), and submit recomputes it.
- **Overlaps with other projects.** Other projects whose boundaries intersect are stored with the version and
  shown for review. Another organization's project is shown without its code.
- **GIS review.** A GIS reviewer (`farms.review` in the project's organization) marks the current version ACCEPTED
  or ISSUES.

## Assumptions (to confirm)

| # | Assumption |
|---|---|
| P1 | Order: data collection → eligibility review → STANDARD_SELECTED (approval confirms the route) → ACTIVITY_SELECTED (PM confirms). Standard and activity *references* may be recorded while collecting data |
| P2 | ELIGIBILITY_REVIEW → DATA_COLLECTION (returned), STANDARD/ACTIVITY_SELECTED → DATA_COLLECTION (re-open), early states → CLOSED |
| P3 | Only farms of the project's own organization can join (no cross-organization participation model yet) |
| P4 | Projects are owned by PROJECT_DEVELOPER, FIELD_PARTNER or FARMER_GROUP organizations |
| P5 | Project types: AGRICULTURAL_LAND_MANAGEMENT, AGROFORESTRY, RICE_CULTIVATION, GRASSLAND_MANAGEMENT, OTHER (classification only) |
| P6 | Carbon-rights statuses ACTIVE / ENDED / VOID with a separate review status UNVERIFIED / VERIFIED / REJECTED; the recorder cannot review |
| P7 | Crediting-period statuses: PROPOSED / SUPERSEDED / CANCELLED now; CONFIRMED / ACTIVE / ENDED reserved for later phases. Overlapping proposed periods are refused |
| P8 | Eligibility review is done by `projects.review` (QA Officer). GIS boundary review uses the existing `farms.review` |
| P9 | The DEMO standards and activities are illustrative reference entries, not statements of any programme's rules |

## Not in Phase 3

Methodology catalog, candidates, applicability and confirmation (Phase 4); MRV, sampling, laboratory, calculation,
VVB, registry, credits, marketplace and payouts (later phases). Project-level access scoping by team membership is
not enforced yet: access is organization-scoped.
