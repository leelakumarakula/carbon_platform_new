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
| KYC_VERIFIED → ACTIVE | the *current version* of every active consent definition marked `required_for_activation` is GRANTED | farmers.manage |
| ACTIVE ⇄ SUSPENDED | a reason | farmers.manage |

- **Identity privacy.** The ID number is never stored in clear text. Only its last 4 digits are kept, plus
  a keyed HMAC fingerprint (`DATA_ENCRYPTION_KEY`) used to find duplicates. A matching fingerprint sets
  `possible_duplicate`, and the reviewer must confirm explicitly (`DUPLICATE_REVIEW_REQUIRED`). Name and date
  of birth are locked after verification (`IDENTITY_LOCKED`).
- **Contacts** are deactivated, never deleted.
- **Consents** are configuration (decision D3). `consent_definitions` holds `consent_type`, `version`, title,
  `text_version` and `required_for_activation`; administrators with `consents.configure` publish a type or its next
  version (the previous version is RETIRED, never edited). Today the only definition is `DATA_PROCESSING` v1,
  required for activation; no other consent type has been invented.
- Each farmer grant references the definition version it was given against and records the consent-text version,
  language, capture method and time (`granted_at`). Withdrawing keeps the row (WITHDRAWN, with reason); granting a
  newer version marks the older grant SUPERSEDED. Nothing is overwritten.
- **Agreements**: DRAFT → SIGNED → TERMINATED / EXPIRED, or DRAFT → VOID. Numbers `AGR-YYYY-nnnnnn`. Signing
  needs the farmer to be registered and not suspended.
- **Bank accounts**: PENDING_VERIFICATION → VERIFIED / REJECTED → INACTIVE. The account number is encrypted
  with Fernet and only the last 4 digits are ever returned. The verifier must not be the person who added the
  account. No payout is made in Phase 2; payouts are Phase 11.
- **Self-service.** A user with `farmers.self` who is linked to the farmer (`link-user`) can see and edit only
  their own record (`GET /farmers/me`). They cannot verify their own KYC.
- **Codes** come from SQL Server sequences: `FRM-YYYY-nnnnnn` and `FARM-YYYY-nnnnnn`.

## Farm

The farm workflow (status, boundaries and GIS, ownership, history, evidence, documents) is in
[farm-workflow.md](farm-workflow.md).

## Decisions (approved 2 Oct 2026)

| # | Decision |
|---|---|
| D1 | Farmer, farm, agreement, bank-account and overlap transitions as implemented (including A1–A3 below) are approved |
| D2 | Agreement statuses DRAFT / SIGNED / TERMINATED / EXPIRED / VOID and bank statuses PENDING_VERIFICATION / VERIFIED / REJECTED / INACTIVE are internal platform workflow states |
| D3 | DATA_PROCESSING remains the only required consent; consent types are versioned configuration |
| D4 | Operational roles are delegated through `users.assign_roles`; privileged permissions stay restricted (see roles-permissions.md) |
| D5 | Cross-organization overlaps are cleared only by the Platform GIS Specialist |
| D6 | The basemap tile source is configuration (`MAP_TILE_*`), not code |

## Assumptions (approved through D1–D3 unless noted)

| # | Assumption |
|---|---|
| A1 | KYC_PENDING → REGISTERED when KYC is rejected, so the farmer can resubmit |
| A2 | SUSPENDED → ACTIVE (reinstatement) |
| A3 | Farm SUBMITTED → DRAFT (withdraw), VERIFIED / REJECTED / INACTIVE → DRAFT (reopen), DRAFT → INACTIVE |
| A4 | Agreement statuses DRAFT / SIGNED / TERMINATED / EXPIRED / VOID, and bank-account statuses PENDING_VERIFICATION / VERIFIED / REJECTED / INACTIVE |
| A5 | Only `DATA_PROCESSING` consent is required before ACTIVE — now the `required_for_activation` flag of its consent definition (D3) |
| A6 | Thresholds: overlap 1 m²; large-farm warning 1000 ha; declared-area warning 25%; 5000 vertices |
| A7 | Farm verification requires farmer KYC verified and a verified ownership record |

## Not in Phase 2

- **Offline capture and sync.** The data model supports it (`source`, timestamps), but offline mode is not built.
- **Storage and scanning adapters.** The S3 / MinIO adapter and a real antivirus engine are still to come;
  `local` storage and the signature-only scanner are for development.
- **Notifications** are in-app only. The SMS, email and WhatsApp adapters come later.
- **Basemap.** Tiles come from `MAP_TILE_URL` / `MAP_TILE_ATTRIBUTION` / `MAP_TILE_MAX_ZOOM` / `MAP_TILE_SUBDOMAINS`,
  served to the SPA by `GET /api/v1/config/client` (decision D6). The default OpenStreetMap public server is for
  development only; production needs a licensed or self-hosted tile service (no code change required).
