# Phase 12B — Production hardening, storage, observability, external events: discovery and design

> **Discovery only.** No application code, migration, dependency, configuration or database was changed. Two documents were added: this
> report and [phase-12b-decision-lock.md](phase-12b-decision-lock.md).
> Baseline: commit `c057c42` (`phase-12a-background-jobs`), working tree clean, development database at migration `0017`, about 185 MB
> free on C:.

Tags used throughout:

- **[REPO]** — verified in the repository, with file / line references.
- **[SPEC]** — stated in the master specification. The copy available in this workspace is the Phase 4 → 12 master implementation
  prompt (§22 Phase 12, §23 Notifications, §40 performance acceptance, §42 provider interfaces, the open-decision list).
- **[ASSUMPTION]** — technically necessary inference.
- **[OPEN]** — not defined anywhere; locked in the decision lock (`Dn`).

---

## 1. Executive summary

1. **Most of Phase 12B depends on facts the repository and the specification do not contain.** The specification lists production
   hosting, data residency, the notification provider, the production payment provider and the production registry integration as
   **open decisions** [SPEC]. Without them, these have no target:
   - the S3 provider, Redis hosting, backup storage and the monitoring platform;
   - webhooks and notification delivery.
2. **What is clearly required and buildable now** [SPEC §22 + REPO gaps]:
   - an S3-compatible storage adapter (the storage abstraction exists; production refuses local storage);
   - a real malware-scanning adapter (the hook exists; today it reports `NOT_SCANNED`);
   - a Redis-backed rate limiter (the protocol exists; today it is per process);
   - a backup strategy + restore test;
   - structured logs for the whole application;
   - performance fixes for verified hot spots;
   - a small set of evidence-based security fixes.
3. **What should stay deferred** (verified):
   - **Calculation and report workers.** No production calculation module is registered (`app/calculation/registry.py:14`,
     `_MODULES = ()`), so no real long calculation exists. Both paths are already bounded by size guards.
   - **Provider polling and webhooks.** Every runtime adapter is MANUAL (payment, payout, registry) or a no-op (LIMS); there is no
     contracted provider.
   - **External notification delivery.** No provider has been selected [SPEC: "notification provider" is an open decision].
4. **Recommended split into three implementable sub-phases**, plus deferred items (decision D1):
   - **12B-I — Document storage & safety:** the S3 adapter, then the AV adapter and quarantine.
   - **12B-II — Runtime hardening:** Redis rate limiter, security fixes, JSON logging, health split, listing performance.
   - **12B-III — Operations:** backup / restore runbook and restore-verification tooling, production Redis / S3 / monitoring
     configuration.
5. **Development-machine constraint (decision D51).** About 185 MB free, no Docker / WSL / Redis.
   - MinIO's server binary (~100 MB) and ClamAV (signature databases of several hundred MB) cannot run here.
   - `boto3` / `botocore` (~90 MB installed) should be avoided.
   - Real-service integration tests for S3 and antivirus need another test host, or are reported as not run.
6. **Counts:** 51 decisions — 21 business, 30 technical; 30 require sign-off; 10 block implementation; 8 are safe to implement without a
   further decision; 6 contradictions.

---

## 2. Repository inspection (verified facts)

| Area | Findings [REPO] |
|---|---|
| Storage | `integrations/storage.py`:<br>• `ObjectStorage` Protocol (`put` / `get` / `exists`) + `LocalFileStorage`.<br>• 12A added the optional `iter_objects`.<br>• `STORAGE_BACKEND=s3` raises "not implemented yet (S3 adapter planned for Phase 12)".<br>• Local storage is refused in production.<br>• Keys are server-generated: `{environment}/{YYYY}/{MM}/{uuid hex}`. |
| Documents | `models/documents.py`:<br>• `documents` (status ACTIVE / **QUARANTINED** / ARCHIVED, sensitivity, `current_version`) and append-only `document_versions`: `storage_key` unique, `checksum_sha256`, `scan_status` NOT_SCANNED / CLEAN / INFECTED / ERROR, `scan_detail`.<br>• 31 categories; 5 restricted (KYC_ID, BANK_PROOF, BUYER_KYC_DOCUMENT, PAYOUT_EVIDENCE, RECONCILIATION_EVIDENCE). |
| Upload path | `document_service._validate` / `_store` / `create_document`:<br>• content sniffing (never the filename); per-category PDF-only rules; size ≤ `MAX_UPLOAD_BYTES` (15 MB, enforced while reading in `deps.read_upload`);<br>• synchronous `get_scanner().scan(data)` — EICAR → `MALWARE_UPLOAD_BLOCKED` security event + refusal;<br>• `put` to storage **before** the DB commit (orphan possible — documented, detected by the 12A scan);<br>• SHA-256 stored; `DOCUMENT_UPLOADED` audit. |
| Download path | `document_service.download` / `read_verified`:<br>• streamed through the API after the entity resolver's permission check;<br>• refused while QUARANTINED;<br>• **re-hashes every read** (mismatch → CRITICAL `DOCUMENT_INTEGRITY_FAILURE`);<br>• every download audited (`DOCUMENT_DOWNLOADED`).<br>No signed URLs exist. |
| Quarantine | The QUARANTINED status is checked on download, and `require_attached` requires ACTIVE (quarantined documents cannot back a business record). **Nothing sets QUARANTINED today.** |
| Malware | `integrations/malware.py`: `SignatureScanner` (EICAR only; `NOT_SCANNED` otherwise; never claims CLEAN); `MALWARE_SCANNER=signature`; a real AV adapter is "planned for Phase 12". |
| Generated documents | `ORDER_CONFIRMATION` (Phase 10) and `CALCULATION_REPORT` (Phase 8A) go through the same document store. The PDF writer is in-house, deterministic and text-only (`reports/pdf.py`, 72 lines). |
| Rate limiting | `core/rate_limit.py`: in-memory fixed window per process ("Redis backend required before running multiple API workers"). Applied to:<br>• global per IP (`GLOBAL_RATE_LIMIT_PER_MINUTE=600`, middleware);<br>• login per IP and per IP+email (`LOGIN_RATE_LIMIT_PER_MINUTE=10`) + DB lockout (`MAX_FAILED_LOGINS=5`, `LOCKOUT_MINUTES=15`).<br>Refresh, uploads, job APIs and admin password reset have **only** the global limit. There is no public self-service password reset. |
| Tokens | JWT HS256 access tokens (15 min); rotating refresh tokens stored as SHA-256 with reuse detection that revokes the whole session (`auth_service.refresh`); refresh cookie httpOnly + SameSite=Strict + path-scoped + `Secure` enforced in production. |
| Headers / CORS | Secure headers, CSP on API responses, HSTS in production, explicit `CORS_ORIGINS` (`core/middleware.py`, `main.py`). |
| API docs | `main.py`: `docs_url="/docs"` and the OpenAPI JSON are **always on**, including production. |
| Health | `GET /api/v1/health`: public; returns status, database and **environment**. 12A added the authenticated `/jobs/status` (database, broker, worker heartbeats, counts). |
| Logging | `logging.basicConfig` plain text (`main.py`); `api_access_logs` row per API request (own transaction); 12A JSON lines on `app.jobs` only. No metrics, traces or alerts. |
| Redis / Celery (12A) | `REDIS_URL` = broker only; Celery: JSON, no result backend, late ack, reject-on-worker-lost, prefetch 1, queues default / maintenance, beat schedule; compose Redis bound to 127.0.0.1 with AOF + noeviction. No production guard on `REDIS_URL` scheme / authentication. |
| SQL Server | SQL Server 2022 **RTM 16.0.1000.6** (dev). Dev DB `carbon_platform` recovery model **FULL** (log 136 MB, no log backups); test DB SIMPLE (`manage.py create_db`). RCSI on. Pool 10 + 20. 266 declared indexes; 10 hand-written spatial indexes; 24 spatial predicates in services. |
| Query patterns | • Several listings load whole tables and filter in Python: `order_service.visible_orders`, `marketplace_service.listings`, `payment_service.visible_refunds`, `finance_service.visible_projects`.<br>• Listings run lazy expiry (writes) inside GET loops.<br>• Mappers do per-row `db.get` lookups (e.g. lab 41, MRV 18, finance 17, calculation 17 call sites).<br>• 93 endpoints return unpaginated `list[...]`; 11 return `Page[...]`. |
| Calculation | `calculation_service.execute` is synchronous: input-snapshot hash check, freshness check, module resolution (`registry.resolve` — **no module registered**), `NOT_PRODUCTION_READY` block in production, outputs + hashes stored; size guard `CALCULATION_MAX_INPUT_ROWS=20000` (BLOCKED `INPUT_TOO_LARGE`). |
| Reports | `calculation_report.generate`:<br>• APPROVED runs only; input / output hash checks;<br>• size guard `CALCULATION_REPORT_MAX_ROWS=20000` (`REPORT_TOO_LARGE`);<br>• deterministic content + SHA-256, PDF SHA-256;<br>• a new version supersedes the current one (`REPORT_UNCHANGED` if identical); stored as a CALCULATION_REPORT document; `verify` re-renders. |
| Adapters | Payment: `ManualPaymentAdapter` only (TEST adapter in tests; `ingest_event` exists, **no route**). Payout: `ManualPayoutAdapter` only. Registry: `ManualRegistryAdapter` only. LIMS: `NoLimsAdapter`. No webhook route anywhere. |
| Notifications | `notifications` table (channel IN_APP / EMAIL / SMS / WHATSAPP; status PENDING / SENT / FAILED; `retry_count`). `notification_service.notify` writes IN_APP rows (SENT) **in the caller's transaction**. 14 call sites, Phases 2–5 only (farm verified, farmer KYC, project submitted / returned / approved, MRV plan / dataset, sample assigned, field collection returned…). No provider; no external channel. The frontend polls the unread count every 60 s. |
| Secrets | `.env` (never committed): `SECRET_KEY`, `JWT_SECRET`, `DATA_ENCRYPTION_KEY` (one Fernet key — no rotation support). |
| Deployment docs | `docs/deployment.md`: production checklist (HTTPS, proxy headers, Redis limiter before multi-process, real scanner + S3 before real uploads, back up SQL Server full + log, a retention policy for `api_access_logs` to be set, background jobs). No RPO / RTO and no restore procedure. |
| Tests | 366 backend + 128 frontend + E2E. Local storage root in a temp directory for tests; snapshot-based concurrency suites; fakeredis TCP server for the 12A broker test. |

---

## 3. Storage (12B-1)

**A–C. Current state** [REPO]:
- Files live on the **local filesystem** behind an **abstracted storage service** (`ObjectStorage`); the database keeps metadata only.
- Already present:
  - content-based MIME validation (magic bytes, not extension);
  - safe filename normalization (extension derived from the detected type);
  - per-category type rules and a 15 MB size limit;
  - SHA-256 at upload **and** on every download;
  - immutable versioning (new upload = new key, append-only versions);
  - a malware hook and the QUARANTINED status (unused);
  - orphan detection (12A).
- **Missing:** an S3 adapter, encryption at rest, deletion, and any use of quarantine.

**D. Categories needing object storage.** All 31 categories. Every uploaded or generated document goes through the same store. The five
restricted categories and the evidence categories (payment / refund / payout / reconciliation / cost / registry / verification / lab)
are the most sensitive.

**E. Never in Redis:** any file content, document metadata beyond ids, KYC or bank data, storage keys combined with credentials, signed
URLs, or business state. 12A already restricts payloads to identifiers.

**F. What moves to S3-compatible storage:** every new document version (identical keys and hashes), plus a one-off migration of
existing local files where an environment has any (D9).

**AWS S3 vs MinIO** (no automatic choice — D2):

| Aspect | AWS S3 | MinIO (self-hosted) |
|---|---|---|
| Fit with the spec | "S3-compatible storage for production" [SPEC] | "MinIO for local development" [SPEC]; can also run in production self-hosted |
| Operations | managed durability (multi-AZ), versioning, Object Lock, lifecycle, KMS | operator-run: disks, erasure coding, upgrades, TLS, backups |
| Encryption | SSE-S3 / SSE-KMS / SSE-C | SSE-S3 / SSE-KMS (with KES) / SSE-C |
| Data residency | region choice | wherever it is hosted |
| Local dev | not needed (MinIO or any S3-compatible endpoint) | server binary ~100 MB — **cannot run on this machine** (D51) |

**Proposed architecture** [ASSUMPTION, for D2–D11]:
- **Adapter.** `S3ObjectStorage` implements `put` / `get` / `exists` / `iter_objects` with an S3 SDK (D3).
  - It is configured by the existing `OBJECT_STORAGE_*` settings plus region / TLS.
  - It is selected by `STORAGE_BACKEND=s3`.
  - The key format is unchanged.
- **Credentials:**
  - an access key per environment from the secret store;
  - application credentials allow put / get / list only — **no delete**;
  - deletion (if ever) runs under a separate operational identity (D10).
- **Bucket layout:** one bucket per environment (`…-live`, `…-demo`), private, Block Public Access, bucket versioning on (D4, D8).
- **Encryption:** SSE (S3- or KMS-managed) at minimum. Client-side encryption is an option for restricted categories (D5).
- **Checksum:**
  - SHA-256 stays the authority (DB) and is re-verified on download;
  - additionally send `x-amz-checksum-sha256` (or Content-MD5) on put, so the store rejects corrupted uploads.
- **Upload strategy:** server-side (the API already receives, sniffs, size-limits and scans the bytes). Files ≤ 15 MB need no multipart
  and no direct-to-bucket uploads (D7).
- **Download strategy:** keep streaming through the API, so permission, audit and integrity re-hash stay on every download.
  - Presigned URLs (the spec's "signed access") would skip all three.
  - If adopted, presigned URLs should be limited to large, non-restricted files, very short expiry, and audited at issuance (D6).
- **Lifecycle:** none until retention periods exist (D48). Noncurrent versions are kept.
- **Orphans:** 12A detection stays. With S3, a two-stage tag-then-delete becomes possible but needs sign-off (D10).
- **Write-before-commit ordering:** unchanged. An orphan is harmless and detected (D11).

---

## 4. Antivirus / malware scanning (12B-2)

**Where the scan happens today** [REPO]: `document_service._store` → `get_scanner().scan(data)`, **synchronously, before `put` and
before the version row is added**. An INFECTED result writes a CRITICAL security event and refuses the upload. Every other result stores
`scan_status` on the **immutable** version row.

**Architectures compared:**

| Option | Behaviour | Fit |
|---|---|---|
| A — synchronous scan before acceptance (current hook) | the user waits for the scan (files ≤ 15 MB); an infected file is never stored; the result is final on the immutable version row | matches every existing workflow (evidence can be referenced immediately); no new states |
| B — upload → QUARANTINED → background scan → ACTIVE | the document exists but cannot be downloaded or referenced (`require_attached` requires ACTIVE) until CLEAN | changes many Phase 6–11 flows (payment / refund / payout evidence, VVB evidence, lab reports become usable only later); `scan_status` cannot be updated on the append-only version row — a new append-only `document_scans` table is required |
| C — storage-event → scan worker | as B, triggered by the bucket | needs provider events (D2); same state change as B |

**Recommendation** (D12): **A** for acceptance, plus **background rescans** (a new append-only scan-history table) when signatures
update or for files uploaded while the scanner was degraded. A later INFECTED rescan moves the document to QUARANTINED: it can no
longer be downloaded or referenced, a CRITICAL security event is raised, and existing references stay but are flagged.

- **While scanning (A):** the request waits; nothing is stored until the scan returns.
- **Allowed states:** version `scan_status` CLEAN / NOT_SCANNED (TEST / DEMO signature scanner) / ERROR (only if D14 allows degraded
  acceptance); document ACTIVE / QUARANTINED.
- **Scan failure or scanner unavailable:** **OPEN** (D14). The options are to refuse the upload (fail closed) or to accept it as
  `ERROR` + QUARANTINED with a mandatory background rescan.
- **Can a malicious file become visible?** Not for a detected signature (refused before storage; a rescan quarantines it). Detection
  depends on the engine's signatures. Quarantine already blocks download and reference.
- **SHA-256:** unchanged; scanning is read-only.
- **Rescanning:** needed for defence in depth (new signatures), recorded append-only (D15).
- **Audit:** `MALWARE_UPLOAD_BLOCKED` exists. Add `DOCUMENT_SCANNED` / `DOCUMENT_QUARANTINED` / `DOCUMENT_RESCAN_INFECTED` with engine
  name, signature version and result. Results are immutable.
- **Environments:** TEST keeps the EICAR signature scanner. DEMO uses the signature scanner honestly labelled NOT_SCANNED (or the real
  engine if hosted). LIVE requires a real engine (deployment.md already says so).
- **Engines (no provider is chosen — D13):**
  - ClamAV via `clamd` INSTREAM (GPL-2.0 daemon; Linux service; signature databases of several hundred MB; the Python side can speak
    the INSTREAM protocol in ~50 lines without a dependency);
  - a storage-native malware scanning service (depends on D2);
  - commercial scanning APIs (would send documents, including KYC, to a third party — a data-residency question, D50).

  These are listed options, not recommendations of a vendor.

---

## 5. Rate limiting (12B-3)

| Surface | Today [REPO] | Gap |
|---|---|---|
| Login | per IP and per IP+email (10 / min) + DB lockout (5 failures → 15 min) | per process only |
| Refresh | global per-IP limit only | no specific limit (reuse detection exists) |
| Password reset | admin-only endpoint (no public reset flow) | — |
| Public endpoints | `/health`, login, refresh, OpenAPI / docs | `/docs` open in production (security finding F1) |
| API | global per-IP 600 / min | no per-user / per-organization dimension |
| Uploads | global limit + 15 MB per file | no upload-rate limit |
| Job APIs | Platform-Admin only + global limit | — |
| Webhooks | none exist | — |

**Is a distributed limiter required?** Only when more than one API process or instance runs. The code itself states it is required
before multi-process deployment [REPO]. The production topology is undefined (D50). Recommendation (D18): implement a Redis backend
behind the existing `RateLimitBackend` Protocol, using the already-installed `redis` package, enabled when Redis is configured.

**Options:**
- **in-memory:** today; correct only for a single process.
- **SQL-backed:** durable but adds write load on every request.
- **Redis-backed:** atomic `INCR` + `EXPIRE` per window key; fits.
- **gateway / proxy:** edge limits (recommended *in addition*, D21).

**Keys:** `{env}:rl:{scope}:{dimension}:{window}`, for example `live:rl:login:ip:1.2.3.4` and `live:rl:login:ipemail:…` with a hashed
email (never raw personal data in Redis keys).

**Fail-open vs fail-closed on Redis outage:** **OPEN** (D20). Recommendation: degrade to the per-process limiter; the DB lockout still
applies; never fully open.

**Trusted proxies:** uvicorn `--proxy-headers` with `--forwarded-allow-ips` restricted to the proxy (D21).

**Limits:** existing values are configuration defaults. New limits (refresh, uploads, per user / organization, burst) are **OPEN**
(D19); no numbers are proposed.

---

## 6. Production Redis (12B-4)

Redis stays **transport + rate-limit counters only**; SQL Server stays the system of record (12A D3).

| Option | Availability | Celery broker | Rate limiter | Notes |
|---|---|---|---|---|
| A — managed Redis | provider SLA, replicas, automatic failover | yes | yes | TLS + auth built in; region = data residency |
| B — self-hosted single | single point of failure | yes | yes | simplest; jobs wait in SQL during an outage (12A) |
| C — Sentinel (primary + replicas) | automatic failover | yes (kombu `sentinel://`) | yes (client support) | more operations |
| D — Cluster | sharded | **not supported by the Celery Redis transport** | possible | exclude for the broker |

**Requirements for any option** (D23):
- Redis ≥ 7; TLS (`rediss://` with certificate verification); ACL users (broker vs limiter);
- no public exposure;
- `maxmemory` with **noeviction** for the broker database (evicting queued messages is unacceptable; the limiter keys expire by TTL);
- AOF `everysec` (optional — SQL republishes after loss);
- monitoring of memory, connections and latency;
- connection pool sizing per process.

Backups are not required for business correctness (Redis can be cleared; 12A recovers from SQL).

**Gap:** there is no production guard yet that refuses a non-TLS / unauthenticated `REDIS_URL` to a non-local host (security finding F8).

---

## 7. Backup / restore (12B-5)

- **Current state** [REPO]:
  - deployment.md says "back up SQL Server (full + log)";
  - dev DB FULL recovery, test DB SIMPLE;
  - no restore procedure, restore test, RPO / RTO, backup encryption or backup retention.
- **Spec:** "backup strategy", "restore test" [SPEC §22].
- **Recommended method** (D26; values OPEN):
  - full (weekly) + differential (daily) + transaction-log backups (interval derived from the RPO) — the frequencies are placeholders
    for D25;
  - `WITH CHECKSUM`; backup encryption (certificate); off-host / immutable storage;
  - backup retention ⟨OPEN⟩.
- **RPO / RTO:** **OPEN** (D25) — not invented.
- **Restore test** (D27, an existing spec requirement): a scripted restore to a separate database followed by verification:
  - `alembic current`;
  - trigger presence;
  - ledger conservation (positions sum = issued);
  - calculation input / output hashes; settlement snapshot hashes; calculation report hashes;
  - `document_versions` keys present in object storage with matching SHA-256 (sampled).

  It is run on a schedule, with results recorded.
- **Records that must be preserved** (all append-only or immutable today):
  - audit / workflow / security / login / access logs;
  - credit ledger (entries, positions, reservations, transfers, retirements);
  - money ledger (revenue, settlements, entitlements, payouts, transactions, reconciliations, adjustments);
  - laboratory results, custody, QA;
  - calculation runs, inputs, outputs, QA, reports;
  - pre-verification and verification (findings, decisions);
  - registry submissions, issuances, batches, serials;
  - marketplace orders, payments, refunds;
  - job history.
- **Object storage** needs its own protection: bucket versioning + replication or separate backup (D28). Because objects are never
  deleted by the application, restoring the DB to an earlier point still finds every referenced file; newer objects become harmless
  orphans.
- **Keys:** `DATA_ENCRYPTION_KEY` must be backed up separately (bank numbers are unreadable without it); `JWT_SECRET` / `SECRET_KEY`
  rotate on restore if compromised (D30).
- **Dev-machine observation:** the dev DB uses FULL recovery without log backups, so its log grows (136 MB now, on a nearly full disk).
  Recommendation for development only (D29): SIMPLE recovery or periodic log backups — your machine, your call.

---

## 8. Performance (12B-6)

**Likely high-volume tables:**
- `audit_logs`, `workflow_events`, `api_access_logs` (one row per request);
- `background_jobs` / attempts (about 300 rows / day with the 12A defaults);
- `credit_ledger_entries` / positions;
- `sampling_points`, field collections, lab tests / results;
- calculation inputs / outputs; notifications.

**Verified hot spots** [REPO]:
1. **Whole-table scans with Python filtering:**
   - `order_service.visible_orders` (all orders, then `side()` per row, then lazy expiry per row);
   - `marketplace_service.listings` (all listings, lazy expiry per row);
   - `payment_service.visible_refunds` (all refunds + `db.get(Order)` per row);
   - `finance_service.visible_projects` (all projects).

   Cost grows with the whole table, not with the caller's data.
2. **Writes during GET:** listing endpoints run lazy expiry (`ls.run` transactions) inside read loops. Correctness is fine; latency and
   locking under load are not. With 12A sweeps, read-path expiry could become cheaper (check only).
3. **N+1 mappers:** per-row `db.get` lookups (lab 41, MRV 18, finance 17, calculation 17, registry 15, ledger 14, marketplace 12 call
   sites).
4. **Pagination:** 93 list endpoints return everything; only 11 are paginated.
5. **Synchronous heavy operations:** calculation (≤ 20,000 input rows), report (≤ 20,000 rows), sampling-point generation
   (rejection sampling bounded by `SAMPLING_MAX_ATTEMPTS_PER_POINT`), GIS area / overlap (SQL Server spatial, 10 spatial indexes).
6. **Long transactions:** none found beyond the bounded ones above. Ledger / finance transactions lock a few rows in a fixed order.

**Strategy** (D31–D33):
- Define volumes and SLOs (OPEN).
- Build a TEST-only synthetic data generator (farms, sampling points, lab results, orders, ledger movements).
- Measure baselines with pytest timing + SQL Server Query Store / execution plans (no new dependency).
- Fix the verified hot spots first: SQL-side scoping (organization predicates), keyset or limit pagination, eager loading.
- Re-measure.

API changes (list → page) need sign-off because they change response contracts (D32).

---

## 9. Calculation workers (12B-7)

- **Current state** [REPO]:
  - create → freeze (readiness, frozen input snapshot + SHA-256) → execute (synchronous: hash check, freshness check, module
    resolution, production-readiness block, outputs + output hash) → QA → approve;
  - immutable runs; recalculation creates a new run;
  - **no module is registered.**
- **If moved to Celery later** (design only):
  - **Payload and state:**
    - the job payload is the run id only;
    - new run state(s) for queued / executing would be needed (a Phase 7 state-machine change);
    - the worker re-checks the snapshot hash, freshness, module and production readiness under a lock on the run;
    - outputs are written in one transaction with the output hash;
    - idempotent by run status (only INPUTS_FROZEN executes).
  - **Retries and cancellation:**
    - only transient errors are retried; `CalculationBlocked` is final (BLOCKED);
    - cancellation only while queued.
  - **Limits and progress:**
    - a soft time limit; a memory limit per worker process;
    - concurrency 1 per host on a `calculation` queue;
    - progress is optional (row counts).
  - **Determinism and audit:**
    - deterministic by construction (frozen snapshot + module version);
    - QA unchanged; audit unchanged plus the job audit.
  - **Never** accept a client-supplied carbon quantity; the module stays authoritative.
- **Recommendation:** **DEFERRED** (D34). There is no real workload or module, both paths are bounded, and an asynchronous state change
  to Phase 7 has no current benefit. Revisit when a production module and real volumes exist.

## 10. Report generation (12B-8)

- **Current state** [REPO]: deterministic text-only PDF; APPROVED runs only; content + PDF SHA-256; versioned; stored as a
  CALCULATION_REPORT document; `verify` re-renders; synchronous below 20,000 rows.
- **Asynchronous flow if needed:** request → job (run id) → worker → same `generate` → document store → hashes → job SUCCEEDED → the UI
  shows the report.
- **Recommendation:** **DEFERRED** (D35), for the same reasons as D34. The 12A framework already supports it.

---

## 11. External provider polling (12B-9)

| Provider | Runtime adapter [REPO] | Contract | Polling |
|---|---|---|---|
| Payment | `ManualPaymentAdapter` (TEST adapter in tests only) | none | **DEFERRED** |
| Payout | `ManualPayoutAdapter` | none | **DEFERRED** |
| Registry | `ManualRegistryAdapter` per account | none | **DEFERRED** |
| LIMS | `NoLimsAdapter` | none | **DEFERRED** |
| Satellite / weather / land records | settings only (`SATELLITE_PROVIDER=mock`), no runtime use | none | out of scope |

There are no real providers, so polling is DEFERRED (D36). The design inputs (idempotency key = our code, status mapping, out-of-order
handling, reconciliation) already exist in the Phase 10 / 11 outbox and status-query code paths.

## 12. Webhooks (12B-9)

- **Required?** No — no provider sends events (D37). Phase 10 D17 forbids a public webhook route until a provider is contracted.
- **Design for when one is contracted:**
  - a provider-specific route;
  - HMAC / asymmetric signature verification over the raw body;
  - a timestamp tolerance window ⟨provider-defined⟩;
  - replay protection through the unique `(provider, external_event_id)` (already in `payment_events`);
  - persist the raw event hash + metadata (append-only), return 2xx quickly;
  - enqueue a background job → the existing `ingest_event` / `_apply` under row locks (the 12A outbox);
  - retries via job retries; DEAD → FAILED job visible to operators;
  - ordering handled by state-machine guards (out-of-order events become IGNORED / UNMATCHED, as in Phase 10);
  - audit and environment isolation (a LIVE endpoint never accepts TEST events).
- **No business mutation in the HTTP request itself.**

## 13. Notifications (12B-10)

- **Exists** [REPO]: the in-app notification store, `notify()` in the caller's transaction, a bell UI with 60 s polling, channels
  declared but unused, and PENDING / FAILED / `retry_count` columns.
- **Spec §23 events vs current wiring** (all in-app):
  - wired: farm verified, sample assigned (plus project / MRV / KYC events not in §23);
  - **not wired:** sample received, lab result available, retest required, calculation complete, QA issue, VVB finding, verification
    complete, registry status, credit issued, order paid, transfer, retirement, payout.
- **Recipients** for the unwired events are not defined (D40).
- **External delivery:** the provider is an open decision [SPEC] (D39).
- **Delivery architecture** (D41, when a provider exists):
  - the business transaction writes a PENDING notification row (outbox; no external call inside critical transactions — Phase 10 / 11
    financial transactions stay free of side effects);
  - a job delivers it, then records SENT / FAILED with `retry_count`;
  - idempotency by notification id;
  - consent / opt-out and the language (`farmers.preferred_language` exists) are business decisions (D42).
- **Not to be built:** fake deliveries or a mock provider at runtime.

## 14. Observability (12B-11)

- **Exists:** request id (header + audit), `api_access_logs`, `security_events`, JSON job logs, `/jobs/status`.
- **Missing:**
  - **metrics:** API latency / error rate, queue depth, job latency / retry rate, DB / Redis health, storage / scan / webhook failures;
  - **dashboards;**
  - **alerts:** DEAD / FAILED jobs, no worker heartbeat, broker unreachable, CRITICAL security events, integrity failures, scan
    failures, 5xx rate;
  - **traces;**
  - **structured application logs** (only `app.jobs` is JSON).
- **Separated:**
  - logs — stdlib JSON formatter, no dependency;
  - metrics — Prometheus text endpoint (small client library) or an OpenTelemetry metrics exporter;
  - traces — OpenTelemetry (several packages, larger) — can defer;
  - alerts — in the chosen platform.
- **Minimum production observability** (D44): JSON logs with request / job correlation; a metrics surface for the signals above;
  alert rules for the critical list; worker / broker health.
- **Options** (no vendor chosen — D43): Prometheus + Grafana + Alertmanager (self-hosted), a cloud provider's monitoring, a SaaS
  APM / logging service, or an OpenTelemetry collector forwarding to any of these.

---

## 15. Security hardening (12B-12) — evidence-based findings

| # | Finding (evidence) | Severity | Component | Mitigation | Phase |
|---|---|---|---|---|---|
| F1 | Swagger UI and OpenAPI JSON always enabled, including production (`main.py:22-24`) | Low–Medium | API | disable in production, or require authentication | 12B-II |
| F2 | Restricted documents (KYC IDs, bank proofs, payout / reconciliation evidence) are plaintext files in local storage; S3 encryption is undefined | Medium | storage | SSE / client-side encryption per D5; local storage is already refused in production | 12B-I |
| F3 | Upload scanning is signature-only (`NOT_SCANNED` for every real file) | High for LIVE uploads | documents | real AV adapter (D12–D14); deployment.md already requires it before real uploads | 12B-I |
| F4 | Rate limiter per process | Medium when scaled out | auth / API | Redis backend (D18) | 12B-II |
| F5 | Refresh endpoint has only the global per-IP limit | Low | auth | dedicated limit (value OPEN, D19); reuse detection already exists | 12B-II |
| F6 | Body-size middleware checks `Content-Length` only (chunked JSON bodies are not size-limited there; file uploads are bounded by `read_upload`) | Low | middleware | proxy `client_max_body_size` + uvicorn limits (D21) | 12B-II |
| F7 | One Fernet `DATA_ENCRYPTION_KEY`, no rotation; HS256 JWT secret, no key id / rotation | Medium (operational) | secrets | MultiFernet-style rotation; JWT `kid` rotation; secret store (D30) | 12B-III |
| F8 | No production guard on `REDIS_URL` (plain `redis://` to a remote host, without auth, is accepted) | Medium | jobs / broker | refuse non-TLS / unauthenticated non-local broker in production (D23) | 12B-II |
| F9 | Public `/health` reveals the environment name | Low | API | liveness / readiness without detail (D46) | 12B-II |
| F10 | `api_access_logs` keep IP + user agent indefinitely (personal data); no retention | Low–Medium (privacy) | audit | retention decision (D48) | business |
| F11 | Dev SQL Server is 2022 RTM without cumulative updates | Informational (dev) | infrastructure | production must run a patched CU | deployment |
| F12 | Celery messages are unsigned | Low (JSON, ids only, Redis ACL) | jobs | optional message signing | defer |

Verified as **not** gaps:
- **CSRF:** the refresh cookie is SameSite=Strict, httpOnly and path-scoped; the access token is a bearer token held in memory.
- **CORS:** explicit origins.
- **Headers:** CSP / HSTS / nosniff / frame-deny.
- **Refresh-token reuse:** detected and revokes the session.
- **Upload type spoofing:** prevented by content sniffing.
- **Download integrity:** re-hashed on every read.

## 16. Data retention

| Data | Status |
|---|---|
| Audit / workflow / security / login logs | append-only, never deleted by the application — **period NOT DEFINED** |
| `api_access_logs` | deployment.md asks for a policy — **NOT DEFINED / NEEDS BUSINESS DECISION** |
| Documents, lab reports, evidence, generated reports | immutable versions; no deletion — **NOT DEFINED** |
| Calculation runs / inputs / outputs / reports | immutable — **NOT DEFINED** |
| Credit ledger, money ledger, registry, verification records | immutable — **NOT DEFINED** (likely legal / registry-driven) |
| Job history (12A) | kept; purge infrastructure present, no period — **NOT DEFINED** |
| Webhook events | none exist |
| Notifications | none — **NOT DEFINED** |
| Logs / metrics (future platform) | **NOT DEFINED** |
| Backups | **NOT DEFINED** (D26) |
| Samples (physical) | out of scope (Phase 6: custody ends at ANALYSED) |

**DEFINED:** only the *behaviour* — immutability and append-only (triggers). No retention *period* is defined anywhere. All periods
need a business decision (D48).

## 17. DEMO / TEST / LIVE per component

| Component | DEMO | TEST | LIVE |
|---|---|---|---|
| Object storage | separate bucket (or local in dev); DEMO documents only | local temp or a test bucket; synthetic files | S3-compatible bucket, encrypted, versioned |
| Malware scanning | signature scanner (honestly NOT_SCANNED) or the real engine if hosted | EICAR signature + engine stub tests | real engine required; policy per D14 |
| Rate limiting | same code; per environment key prefix | in-memory | Redis-backed with fallback |
| Redis | shared or separate DB, prefixed | fakeredis / test Redis | managed / self-hosted per D22, TLS + auth |
| Backup / restore | DEMO data in the same DB (backed up with it) | restore drills on test copies | per D25 / D26 |
| Performance tests | never | synthetic generator only | never on LIVE data |
| Calculation / report workers | deferred (no DEMO module; blocked runs stay blocked) | — | deferred |
| Provider polling / webhooks | none | TEST adapters only (existing) | none until contracted |
| Notifications | in-app only; no external delivery | in-app; no external delivery | in-app; external only with a provider |
| Monitoring | environment label on every signal | test assertions on emitted logs / metrics | production platform per D43 |

Never faked: payments, registry, credits, payouts, verification, external provider success.

## 18. Dependency / infrastructure impact (proposed, not installed)

| Package / service | Reason | Prod | Dev | License | Security notes | Disk | Docker | Windows | Linux |
|---|---|---|---|---|---|---|---|---|---|
| `minio` (Python SDK) | S3 API client for AWS S3 / MinIO / any S3-compatible store (D3) | yes | yes | Apache-2.0 | TLS, SigV4; credentials from the secret store | SDK < 1 MB, but it pulls `urllib3`, `pycryptodome`, `argon2-cffi` (not installed today; verified) — about 10 MB in total (`certifi`, `cffi`, `typing_extensions` already present) | no | yes | yes |
| stdlib SigV4 client (alternative, no package) | minimal put / get / head / list over `urllib` with AWS Signature V4 | yes | yes | — | more code to own and test; must handle TLS verification and retries | 0 | no | yes | yes |
| `boto3` / `botocore` (alternative) | AWS SDK | — | — | Apache-2.0 | — | **~90 MB** | no | yes | yes — **not recommended here** |
| ClamAV `clamd` (service) | antivirus engine option (D13) | service | service | GPL-2.0 (service; called over a socket) | signature updates (`freshclam`) | engine + signatures: several hundred MB — **not on this machine** | optional | yes (ClamWin / ClamAV for Windows) | yes |
| `prometheus-client` (optional) | metrics endpoint (D44) | if D43 selects Prometheus | yes | Apache-2.0 | expose behind auth / internal network | < 1 MB | no | yes | yes |
| OpenTelemetry SDK + exporters (optional) | traces / metrics | if D43 selects OTel | — | Apache-2.0 | — | several MB | no | yes | yes |
| MinIO server (dev / test service) | local S3 endpoint | optional | optional | AGPL-3.0 (server) | — | ~100 MB binary | optional | yes | yes — **not on this machine** |
| Redis 7 (service) | broker + limiter (12A) | service | service | RSAL / SSPL / AGPL (Redis 7.4+ licensing; Valkey BSD fork as an alternative) | TLS / ACL | — | optional | WSL / Docker | yes |

No package is needed for JSON logging, health split, restore verification, performance harness or security fixes F1 / F5 / F8 / F9.

## 19. Proposed Phase 12B boundary

| Group | Classification | Rationale |
|---|---|---|
| 12B-1 Storage (S3 adapter, encryption, versioning, migration tool) | **MUST IMPLEMENT** | spec §22; production refuses local storage, so nothing can go live without it |
| 12B-2 Malware scanning (real adapter, rescans, quarantine use) | **MUST IMPLEMENT** | spec §22; deployment.md requires it before real uploads; F3 |
| 12B-3 Rate limiting (Redis backend, refresh limit) | **SHOULD IMPLEMENT** | required for multi-process (repo note); F4 / F5 |
| 12B-4 Production Redis (configuration + guard) | **SHOULD IMPLEMENT** (guard + docs); hosting **business** | F8 |
| 12B-5 Backup / restore (runbook + verification tooling) | **MUST IMPLEMENT** (spec "restore test"); values **business** | |
| 12B-6 Performance (verified hot spots + harness) | **SHOULD IMPLEMENT** | spec §22 / §40; evidence in §8 |
| 12B-7 Calculation workers | **CAN DEFER** | no module, bounded |
| 12B-8 Report workers | **CAN DEFER** | bounded, deterministic |
| 12B-9 Provider polling / webhooks | **OUT OF SCOPE** until a contract | no provider |
| 12B-10 Notifications — in-app event wiring | **SHOULD IMPLEMENT** once recipients are decided (D40) | spec §23 |
| 12B-10 Notifications — external channels | **CAN DEFER** until a provider (D39) | |
| 12B-11 Monitoring / alerting (JSON logs, metrics surface, health split) | **SHOULD IMPLEMENT** (minimum); platform **business** | spec §22 |
| 12B-12 Security fixes F1 / F5 / F6 / F8 / F9 | **SHOULD IMPLEMENT** | evidence-based |

**Sub-phases** (D1):
- **12B-I — Storage & document safety:** 12B-1, 12B-2.
- **12B-II — Runtime hardening:** 12B-3, 12B-4 guard, 12B-6, 12B-11 minimum, 12B-12, 12B-10 in-app wiring if D40 is decided.
- **12B-III — Operations:** 12B-5, production configuration for Redis / S3 / monitoring once hosting is decided.
- **Deferred:** 12B-7, 12B-8, 12B-9, external notifications.

---

## FINAL DISCOVERY REPORT

**A. Current architecture.**
- Angular SPA → FastAPI modular monolith → SQL Server 2022 (system of record; RCSI; triggers for immutability) + local file storage
  behind `ObjectStorage`.
- Redis as the Celery broker (12A) + Celery worker / beat.
- External adapters are MANUAL or no-op; there is no runtime mock provider.

**B. Phase 12A capabilities.** SQL-backed jobs + append-only attempts; outbox publication + recovery; claims / leases; bounded retries;
environment isolation; the SYSTEM actor; expiry sweeps; orphan detection; retention framework (no policy); job RBAC / UI / status;
fakeredis broker tests.

**C. Phase 12B proposed architecture.**
- **Storage:** S3 adapter (same keys, SHA-256 authoritative, SSE, versioning, no-delete credentials), downloads still through the API.
- **Malware:** synchronous AV at acceptance + append-only rescans + quarantine on later detection.
- **Rate limiting:** Redis-backed with fallback.
- **Redis:** production guard (TLS / auth).
- **Backups:** full / diff / log + automated restore verification.
- **Performance:** SQL-side scoping + pagination for hot listings.
- **Observability:** JSON logs + metrics surface + alert rules + health split.
- **Security:** fixes F1 / F5 / F6 / F8 / F9.
- **Notifications:** in-app event wiring (once recipients are decided); external delivery via outbox → job when a provider exists.

**D. Sub-phases:** 12B-I storage & document safety · 12B-II runtime hardening · 12B-III operations · deferred: calculation / report
workers, provider polling / webhooks, external notifications.

**E–G. Decisions:** D1–D51 in [phase-12b-decision-lock.md](phase-12b-decision-lock.md), with the recommended option and the sign-off
requirement for each.

**H. Production blockers:**
- hosting and data residency (D50);
- S3 provider (D2) and file encryption (D5);
- AV engine (D13) and scanner-outage policy (D14);
- RPO / RTO (D25) and backup method / retention (D26);
- Redis hosting (D22);
- monitoring platform (D43);
- secret management / rotation (D30);
- retention periods (D48).

**I. Security blockers:** a real AV before LIVE uploads (F3); encryption of restricted documents (F2 / D5); Redis TLS / auth guard (F8)
before a remote broker; Swagger off in production (F1).

**J. Infrastructure blockers:** this machine (about 185 MB free, no Docker / WSL / Redis / MinIO / ClamAV) cannot host S3 or AV
integration tests (D51); production platform undefined (D50).

**K. External integration blockers:** no contracted payment / payout / registry / LIMS / notification provider, so polling, webhooks
and external notifications stay deferred.

**L. Dependencies:** `minio` SDK (D3, about 10 MB with its dependencies) or a stdlib SigV4 client (no package); optional `prometheus-client` (D44); no `boto3`; ClamAV / MinIO / Redis as external
services, not Python packages.

**M. Migration impact:**
- `0018` (only if D12 / D15 is accepted): an append-only `document_scans` table + scan audit actions.
- Possibly notification event additions (no schema change needed).
- No change to Phase 1–12A tables. Storage needs no schema change (same keys).

**N. API impact:**
- none for storage (same endpoints);
- upload errors such as `SCANNER_UNAVAILABLE` (per D14);
- rescan / quarantine admin endpoints (D16);
- `/health/live` and `/health/ready`;
- optional metrics endpoint;
- `/docs` disabled in production;
- pagination parameters on hot listings (D32, sign-off).

**O. Frontend impact:**
- quarantine / scan state on document panels;
- admin rescan / quarantine view;
- paginated lists where D32 applies;
- notifications for newly wired events.

**P. Testing impact:**
- S3 adapter unit tests with a stubbed HTTP layer, and an integration test against a real S3 endpoint where one exists (D51);
- AV adapter tests against a stub INSTREAM server, and EICAR against a real `clamd` where one exists;
- Redis limiter tests (fakeredis);
- restore-verification test on a snapshot;
- performance harness on synthetic TEST data;
- security tests for F1 / F5 / F8 / F9.

**Q. DEMO / TEST / LIVE:** see §17.

**R. Explicitly deferred:**
- calculation workers (D34) and report workers (D35);
- provider polling (D36) and webhooks (D37);
- external notification delivery (D39, D41, D42);
- orphan deletion (D10);
- traces; Celery message signing (F12).

**S. Proposed implementation order** (not started):
1. lock the decisions;
2. 12B-II items that are safe without decisions (F1 / F8 / F9 fixes, JSON logging, health split, restore-verification script,
   performance harness);
3. 12B-I storage adapter (after D3, D5);
4. AV adapter + rescans (after D12–D14);
5. Redis limiter (after D20) + refresh limit (after D19);
6. performance fixes (after D32);
7. in-app notification wiring (after D40);
8. 12B-III operations configuration (after D22, D25, D26, D43, D50).

None of these steps is implemented by this document.
