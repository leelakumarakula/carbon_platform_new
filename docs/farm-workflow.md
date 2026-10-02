# Farm workflow (Phase 2)

Code: `backend/app/services/{farm_service,farm_history_service,gis_service}.py`, state machine `FARM_MACHINE` in
`backend/app/services/workflows.py`. Farmer onboarding is in [farmer-workflow.md](farmer-workflow.md); decisions D1–D6 and
assumptions A1–A7 are listed there.

## Farm status

```
DRAFT ─▶ SUBMITTED ─▶ GIS_REVIEW ─▶ VERIFIED ─▶ INACTIVE
  ▲  │      │                  └──▶ REJECTED ─▶ INACTIVE
  │  └──────┴── withdraw / reopen / reactivate ──▶ DRAFT
```

| Transition | Requires | Who |
|---|---|---|
| DRAFT → SUBMITTED | a valid current boundary; a current ownership or tenure record; farmer registered and not suspended. Land, crop and practice history are recommended but not required. | farms.manage |
| SUBMITTED → GIS_REVIEW | — | farms.review |
| GIS_REVIEW → VERIFIED | no OPEN or CONFIRMED_CONFLICT overlaps; a verified current ownership record; farmer KYC verified; reviewer ≠ submitter | farms.review |
| GIS_REVIEW → REJECTED | a reason | farms.review |
| SUBMITTED → DRAFT (withdraw), VERIFIED / REJECTED / INACTIVE → DRAFT (reopen) | a reason. A reopened farm must be reviewed again. | farms.manage |

Boundaries, ownership and history can only be edited in DRAFT, which is why corrections go through reopen.

### Boundaries and GIS

- **Input:** drawn in the map editor, pasted GeoJSON, or an uploaded GeoJSON or KML file. KML files that
  contain DOCTYPE or ENTITY declarations are refused. Accepted shapes are Polygon and MultiPolygon in
  WGS84 / SRID 4326, with at most `FARM_MAX_VERTICES` (5000) vertices.
- **Validation runs on SQL Server, not in the browser:**
  - `geometry::IsValidDetailed` rejects self-intersections and other invalid shapes.
  - `EnvelopeAngle() > 90` means the ring was wound the wrong way, so it is reoriented.
  - `STArea` gives the authoritative area in m² and ha.
  - `STLength` gives the perimeter, and `EnvelopeCenter` the centroid.
- **Warnings** do not block saving:
  - the area is above `FARM_AREA_WARNING_HA` (1000 ha);
  - the declared and measured areas differ by more than `FARM_DECLARED_AREA_WARNING_PCT` (25%).
- **Versioning.** Every save creates a new `farm_boundaries` version. The previous version becomes
  SUPERSEDED, and a filtered unique index allows only one CURRENT boundary.
- **Overlaps** are checked against every other CURRENT boundary in the same environment:
  - The check uses the spatial index `six_farm_boundaries_boundary`, `STIntersects` and `STIntersection().STArea()`.
  - Intersections below `FARM_OVERLAP_MIN_AREA_M2` (1 m²) count as shared edges and are ignored.
  - Each overlap records its relation (PARTIAL / CONTAINS / WITHIN / EQUAL), area and percentage.
  - **Overlaps are flagged for review, never rejected automatically**: OPEN → CLEARED or
    CONFIRMED_CONFLICT. Saving a newer boundary makes old flags OBSOLETE.
  - When the other farm belongs to another organization, its name, farmer and shape are hidden, and only a
    platform-level reviewer can clear the flag (`CROSS_ORG_OVERLAP`).
- **Spatial queries:** `/farms/spatial/at-point` (`STContains`) and `/farms/spatial/near` (`STDistance`, up to 50 km).

### Ownership, history and evidence

- **The farmer is not assumed to own the land.**
  - `farm_ownership` records the owner (farmer, individual, organization, government or community) and the
    operator relationship: owner, tenant, lessee, sharecropper, and so on.
  - Each record also holds the share, validity dates and title reference, and needs its own verification.
  - Ending a record sets `valid_to`; nothing is deleted.
- **History is version-preserving.** Land-use, crop and practice history (HISTORICAL / CURRENT / PROPOSED)
  share one model:
  - **Amend** writes a new version and keeps the old one with `is_current=0`.
  - **Retract** marks the record retracted with a reason. Both are visible in `/versions`.
  - Each version carries its `source` (FARMER_CLAIM, FIELD_OBSERVATION, DOCUMENT, …) and its own
    `verification_status`.
- **Evidence** (`farm_evidence`) links a claim to a document, photo or GPS point:
  - The capturer cannot review their own evidence.
  - Satellite or remote-sensing evidence can be recorded manually only. Its adapter comes in Phase 5, and
    no automated "satellite confirmation" is produced.

### Documents

- **Upload checks.** Uploads are checked for:
  - size (`MAX_UPLOAD_BYTES`, 15 MB);
  - file type, sniffed from the content (PDF, PNG, JPEG, WebP; GeoJSON or KML for geospatial files);
  - malware, through the `MalwareScanner` hook.
- **Storage.** Each file gets a SHA-256 checksum and is stored through the `ObjectStorage` adapter.
- **Versions.** Versions are append-only (database trigger), and downloads go through the API only.
- **Restricted documents.** KYC and bank-proof documents are RESTRICTED. They can be read only by:
  - the farmer;
  - farmer managers;
  - KYC and bank reviewers.

  Other staff get `RESTRICTED_DOCUMENT`.

