# Farmer & farm workflow (Phase 2)

Code: `backend/app/services/{farmer_service,farm_service,farm_history_service,gis_service,document_service}.py`,
state machines in `backend/app/services/workflows.py`. Every transition is validated by its state machine and
written to `workflow_events` and `audit_logs` in the same transaction. Transitions that need data first
return `REQUIREMENTS_NOT_MET` with the missing checklist items. The UI shows the same checklist
(`readiness`) before you try.

## Farmer

```
DRAFT ─▶ REGISTERED ─▶ KYC_PENDING ─▶ KYC_VERIFIED ─▶ ACTIVE ⇄ SUSPENDED
              ▲             │ (KYC rejected)
              └─────────────┘
```

| Transition | Requires | Who |
|---|---|---|
| DRAFT → REGISTERED | full name; village or district and country; an active phone contact | farmers.manage |
| REGISTERED → KYC_PENDING | `POST /kyc`: ID type, ID number, KYC document | farmers.manage (or the farmer, self-service) |
| KYC_PENDING → KYC_VERIFIED / REGISTERED | `POST /kyc/decision` by **someone other than the submitter** | farmers.kyc_verify |
| KYC_VERIFIED → ACTIVE | every consent in `FARMER_REQUIRED_CONSENTS` is GRANTED | farmers.manage |
| ACTIVE ⇄ SUSPENDED | a reason | farmers.manage |

- **Identity privacy.** The ID number is never stored in clear text. Only its last 4 digits are kept, plus
  a keyed HMAC fingerprint (`DATA_ENCRYPTION_KEY`) used to find duplicates. A matching fingerprint sets
  `possible_duplicate`, and the reviewer must confirm explicitly (`DUPLICATE_REVIEW_REQUIRED`). Name and date
  of birth are locked after verification (`IDENTITY_LOCKED`).
- **Contacts** are deactivated, never deleted.
- **Consents** are versioned. Each grant records the consent-text version, language, capture method and time.
  Withdrawing a consent keeps the row (status WITHDRAWN, with the reason). A new grant is a new row.
- **Agreements**: DRAFT → SIGNED → TERMINATED / EXPIRED, or DRAFT → VOID. Numbers `AGR-YYYY-nnnnnn`. Signing
  needs the farmer to be registered and not suspended.
- **Bank accounts**: PENDING_VERIFICATION → VERIFIED / REJECTED → INACTIVE. The account number is encrypted
  with Fernet and only the last 4 digits are ever returned. The verifier must not be the person who added the
  account. No payout is made in Phase 2; payouts are Phase 11.
- **Self-service.** A user with `farmers.self` who is linked to the farmer (`link-user`) can see and edit only
  their own record (`GET /farmers/me`). They cannot verify their own KYC.
- **Codes** come from SQL Server sequences: `FRM-YYYY-nnnnnn` and `FARM-YYYY-nnnnnn`.

## Farm

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

## Assumptions (not in the specification; need confirmation)

| # | Assumption |
|---|---|
| A1 | KYC_PENDING → REGISTERED when KYC is rejected, so the farmer can resubmit |
| A2 | SUSPENDED → ACTIVE (reinstatement) |
| A3 | Farm SUBMITTED → DRAFT (withdraw), VERIFIED / REJECTED / INACTIVE → DRAFT (reopen), DRAFT → INACTIVE |
| A4 | Agreement statuses DRAFT / SIGNED / TERMINATED / EXPIRED / VOID, and bank-account statuses PENDING_VERIFICATION / VERIFIED / REJECTED / INACTIVE |
| A5 | Only `DATA_PROCESSING` consent is required before ACTIVE (`FARMER_REQUIRED_CONSENTS`) |
| A6 | Thresholds: overlap 1 m²; large-farm warning 1000 ha; declared-area warning 25%; 5000 vertices |
| A7 | Farm verification requires farmer KYC verified and a verified ownership record |

## Not in Phase 2

- **Offline capture and sync.** The data model supports it (`source`, timestamps), but offline mode is not built.
- **Storage and scanning adapters.** The S3 / MinIO adapter and a real antivirus engine are still to come;
  `local` storage and the signature-only scanner are for development.
- **Notifications** are in-app only. The SMS, email and WhatsApp adapters come later.
- **Basemap.** The OpenStreetMap public tiles are for development only. Production needs a licensed or
  self-hosted tile service.
