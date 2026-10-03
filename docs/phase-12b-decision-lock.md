# Phase 12B — Decision lock (for human review)

> **No implementation.** This document prepares the Phase 12B decisions for sign-off. No application code, migration, dependency,
> configuration or database was changed. Source: [phase-12b-discovery.md](phase-12b-discovery.md) (sections 2–19, findings F1–F12) and
> the master specification. Baseline commit `c057c42`; latest migration `0017`.

## How to read this document

Every decision states:
- **Type:** BUSINESS (policy, hosting, cost, compliance, values) or TECHNICAL.
- **Status:**
  - OPEN DECISION — undefined; must be chosen;
  - EXISTING REQUIREMENT — already fixed by the spec or an earlier locked decision;
  - RECOMMENDATION — discovery proposes an answer;
  - DEFERRED — not in 12B.
- **Sign-off:** whether your approval is needed.
- **Blocker:** whether it must be settled before the related implementation starts.

No limit, interval, retention period, RPO / RTO, vendor or price is proposed as a requirement. Values you must supply appear as
`⟨TO SELECT⟩`.

---

## D1–D51

### D1 — Phase 12B scope and sub-phases
- **Current repository behaviour:** 12A delivered job infrastructure only; §22 hardening items remain.
- **Specification requirement:** §22 Phase 12 "production hardening" (security, storage, observability, performance, database, workers).
- **Contradiction:** none. Not every §22 item has a target yet (hosting, providers undefined).
- **Options:**
  - A — implement everything at once;
  - B — sub-phases 12B-I storage & document safety / 12B-II runtime hardening / 12B-III operations, with calculation / report workers,
    provider polling / webhooks and external notifications deferred;
  - C — operations only.
- **Recommended option:** B.
- **Consequences:** smaller, testable increments. Production go-live still needs 12B-I + 12B-III.
- **Must NOT be implemented:** deferred groups without their own decision.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / Yes / **Yes**

### D2 — Object storage provider (AWS S3 vs MinIO vs other S3-compatible)
- **Current repository behaviour:** `LocalFileStorage` only; `STORAGE_BACKEND=s3` raises "not implemented"; local storage is refused in
  production.
- **Specification requirement:** "MinIO for local development; S3-compatible storage for production" (EXISTING requirement for the
  *API*). The provider is not named.
- **Contradiction:** the spec wants MinIO for local development, but this machine cannot run MinIO (D51).
- **Options:** AWS S3 · self-hosted MinIO · another S3-compatible service.
- **Recommended option:** none — depends on hosting / data residency (D50). The code targets the S3 API, so it is provider-agnostic.
- **Consequences:** affects the encryption options (D5), backups (D28) and AV options (D13).
- **Must NOT be implemented:** vendor-specific APIs beyond S3; any public bucket.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / No (production blocker)

### D3 — S3 client library
- **Current repository behaviour:** no S3 client installed.
- **Specification requirement:** none.
- **Contradiction:** none.
- **Options:**
  - `boto3` / `botocore` (~90 MB);
  - `minio` SDK (works with any S3-compatible store; about 10 MB with `urllib3`, `pycryptodome`, `argon2-cffi`);
  - a stdlib SigV4 client (no package; more code to own).
- **Recommended option:** `minio` SDK (smallest maintained option). Fall back to stdlib SigV4 if disk does not allow.
- **Consequences:** a new runtime dependency (license Apache-2.0).
- **Must NOT be implemented:** `boto3` on this machine.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / Yes / **Yes**

### D4 — Bucket layout and object keys
- **Current repository behaviour:** keys `{env}/{YYYY}/{MM}/{uuid hex}`, server-generated, unique per version.
- **Specification requirement:** "access control" [§22].
- **Contradiction:** none.
- **Options:**
  - one bucket per environment (LIVE, DEMO) with unchanged keys;
  - one bucket with environment prefixes;
  - separate buckets for restricted categories.
- **Recommended option:** one private bucket per environment, Block Public Access, unchanged keys (restricted categories protected by
  D5, not by a separate bucket).
- **Consequences:** environment isolation at the bucket level; no key migration.
- **Must NOT be implemented:** client-chosen keys, public ACLs.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / No / No

### D5 — Encryption at rest for files
- **Current repository behaviour:** local files are plaintext. Bank account numbers are Fernet-encrypted in the database. 5 restricted
  categories exist.
- **Specification requirement:** "encryption where appropriate" [§22].
- **Contradiction:** none.
- **Options:**
  - SSE-S3 (provider-managed keys);
  - SSE-KMS (customer-managed keys, audit);
  - client-side encryption (application-held key) for restricted categories;
  - SSE + client-side for restricted categories.
- **Recommended option:** none proposed as a requirement (compliance choice). Minimum SSE for all objects.
- **Consequences:** client-side encryption needs key management (D30) and makes provider-side AV (D13 option) impossible.
- **Must NOT be implemented:** storing encryption keys with the objects or in Redis.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / **Yes**

### D6 — Download path (API streaming vs presigned URLs)
- **Current repository behaviour:** every download is streamed through the API: permission resolver, `DOCUMENT_DOWNLOADED` audit,
  SHA-256 re-hash, QUARANTINED refusal.
- **Specification requirement:** "signed access" [§22].
- **Contradiction:** a presigned URL skips the per-download permission check, audit and integrity re-hash.
- **Options:**
  - keep API streaming for everything;
  - presigned URLs for all files;
  - presigned URLs only for large non-restricted files (short expiry, audited at issuance).
- **Recommended option:** keep API streaming. Interpret "signed access" as authenticated, audited access. Presigned URLs only later,
  for non-restricted files.
- **Consequences:** API bandwidth carries file traffic (files ≤ 15 MB).
- **Must NOT be implemented:** presigned URLs for restricted categories; long-lived URLs; persisting signed URLs.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / Yes / No

### D7 — Upload path
- **Current repository behaviour:** server-side: read ≤ 15 MB, sniff, validate, scan, then store.
- **Specification requirement:** "size limits", "file checksum" [§22].
- **Contradiction:** none.
- **Options:** server-side (unchanged) · direct-to-bucket presigned upload.
- **Recommended option:** server-side, plus an `x-amz-checksum-sha256` header on put.
- **Consequences:** no workflow change.
- **Must NOT be implemented:** direct client uploads that skip validation or scanning.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / No / No

### D8 — Versioning and object immutability
- **Current repository behaviour:** application-level immutability (new version = new key; append-only versions); no deletion code.
- **Specification requirement:** "versioning" [§22].
- **Contradiction:** none.
- **Options:**
  - bucket versioning + application credentials without delete permission;
  - plus Object Lock (governance / compliance) with a retention period ⟨TO SELECT⟩.
- **Recommended option:** versioning + no-delete credentials now. Object Lock only once retention periods exist (D48).
- **Consequences:** storage grows (no lifecycle rules until D48).
- **Must NOT be implemented:** lifecycle expiry rules; Object Lock periods without a decision.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / No

### D9 — Migration of existing local files
- **Current repository behaviour:** dev / test have local files. No production environment exists.
- **Specification requirement:** none.
- **Contradiction:** none.
- **Options:** a one-off copy tool (same keys, SHA-256 verified, report) · start empty.
- **Recommended option:** a copy-and-verify tool (`manage.py`), idempotent, never deleting the source.
- **Consequences:** needed only where local files exist.
- **Must NOT be implemented:** deletion of local originals by the tool.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / No / No

### D10 — Orphan file deletion
- **Current repository behaviour:** 12A detects and reports only (the storage abstraction has no delete).
- **Specification requirement:** none.
- **Contradiction:** none.
- **Options:**
  - keep detection only;
  - two-stage: tag / move to a quarantine prefix, then delete after a grace period ⟨TO SELECT⟩ under a separate operational identity.
- **Recommended option:** keep detection only in 12B. Deletion only with sign-off.
- **Consequences:** orphan files accumulate (small).
- **Must NOT be implemented:** deletion with the application's credentials; deletion of any referenced key.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / Yes / No

### D11 — File written before the DB commit
- **Current repository behaviour:** `put` happens before the commit, so an orphan is possible (documented and detected).
- **Specification requirement:** none.
- **Contradiction:** none.
- **Options:** keep · a pending-upload record + two-phase completion.
- **Recommended option:** keep (an orphan is harmless and detected; no extra state).
- **Consequences:** none new.
- **Must NOT be implemented:** writing the DB row before the file exists.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / No / No

### D12 — Malware scanning architecture
- **Current repository behaviour:** synchronous signature scan in `_store` before `put`. INFECTED is refused + CRITICAL event.
  `scan_status` sits on the immutable version row. QUARANTINED exists but is unused.
- **Specification requirement:** "malware scanning adapter" [§22].
- **Contradiction:** asynchronous scanning (B / C) would change Phase 6–11 evidence flows (documents unusable until scanned).
- **Options:**
  - A — synchronous scan at acceptance;
  - B — QUARANTINED → background scan → ACTIVE;
  - C — storage event → scan worker.
- **Recommended option:** A at acceptance, plus background rescans recorded in a new append-only scan-history table. A later INFECTED
  result quarantines the document.
- **Consequences:** migration `0018` (scan history); upload latency includes the scan.
- **Must NOT be implemented:**
  - making a document available before its acceptance scan;
  - updating the immutable version row;
  - releasing an INFECTED document.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / Yes / **Yes**

### D13 — Antivirus engine
- **Current repository behaviour:** `SignatureScanner` (EICAR only).
- **Specification requirement:** "malware scanning adapter" (no engine named).
- **Contradiction:** none.
- **Options:**
  - ClamAV `clamd` (INSTREAM; GPL-2.0 service; large signature data);
  - a storage-native scanning service (depends on D2);
  - a commercial scanning API (sends documents to a third party: data-residency question).
- **Recommended option:** none proposed as a vendor. The adapter interface supports any of them.
- **Consequences:** infrastructure cost / hosting; KYC data exposure for third-party APIs.
- **Must NOT be implemented:** a fake "CLEAN" result; sending restricted documents to an unapproved third party.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / **Yes**

### D14 — Scanner unavailable / ERROR policy
- **Current repository behaviour:** not applicable (the signature scanner never fails).
- **Specification requirement:** none.
- **Contradiction:** none.
- **Options:**
  - fail closed — refuse uploads in LIVE while the scanner is down (`SCANNER_UNAVAILABLE`);
  - degraded — accept as ERROR + QUARANTINED, with a mandatory rescan before use;
  - different policies per environment.
- **Recommended option:** none (risk appetite). A suggested default for review: LIVE fail closed; DEMO / TEST signature scanner.
- **Consequences:** fail closed blocks all evidence uploads during an outage; degraded mode delays evidence use.
- **Must NOT be implemented:** accepting an unscanned LIVE file as ACTIVE.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / **Yes**

### D15 — Immutable scan history and rescans
- **Current repository behaviour:** a single `scan_status` per version; no rescans.
- **Specification requirement:** none.
- **Contradiction:** none.
- **Options:** none · an append-only `document_scans` table + a scheduled rescan job (12A framework) on signature change / degraded uploads.
- **Recommended option:** the append-only table + rescan job (allow-listed registry entry).
- **Consequences:** migration `0018`; new audit actions (`DOCUMENT_SCANNED`, `DOCUMENT_QUARANTINED`, `DOCUMENT_RESCAN_INFECTED`).
- **Must NOT be implemented:** overwriting earlier scan results.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / No / No (depends on D12)

### D16 — Quarantine visibility and release
- **Current repository behaviour:** a QUARANTINED document cannot be downloaded or referenced; nothing sets or releases it.
- **Specification requirement:** none.
- **Contradiction:** none.
- **Options:**
  - nobody can release;
  - a security role can release only ERROR / false-positive cases, with a reason;
  - INFECTED is never released.
- **Recommended option:** the security role views; release only for ERROR cases after a clean rescan; never for INFECTED.
- **Consequences:** a security-admin workflow and UI.
- **Must NOT be implemented:** release of INFECTED; silent release.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / No

### D17 — Scanning per environment
- **Current repository behaviour:** `MALWARE_SCANNER=signature` everywhere.
- **Specification requirement:** honest DEMO; TEST may use test infrastructure.
- **Contradiction:** none.
- **Options:** as discovery §17.
- **Recommended option:**
  - TEST: EICAR signature + a stub engine server;
  - DEMO: signature scanner labelled NOT_SCANNED (or the real engine if hosted);
  - LIVE: a real engine required (production start-up guard).
- **Consequences:** none for DEMO / TEST.
- **Must NOT be implemented:** a runtime mock engine reporting CLEAN.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / No / No

### D18 — Distributed rate limiting
- **Current repository behaviour:** in-memory per process (the code states Redis is required before multi-process).
- **Specification requirement:** "rate limiting" [§22].
- **Contradiction:** none.
- **Options:** in-memory · SQL-backed · Redis-backed (`INCR` + `EXPIRE`) · gateway only.
- **Recommended option:** a Redis backend behind the existing Protocol (no new package), enabled when Redis is configured; gateway limits
  in addition (D21).
- **Consequences:** limiter keys in Redis (counters only).
- **Must NOT be implemented:** business state or raw emails in Redis keys (hash them).
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / No / No (behaviour on outage per D20)

### D19 — New rate-limit values
- **Current repository behaviour:** login 10 / min (per IP and IP+email), global 600 / min per IP, lockout 5 failures / 15 min —
  configuration defaults.
- **Specification requirement:** "rate limiting", "API abuse" tests; no numbers.
- **Contradiction:** none.
- **Options:** values ⟨TO SELECT⟩ for refresh, uploads, per user / organization, job trigger, burst.
- **Recommended option:** none (no invented numbers). Existing values stay.
- **Consequences:** without values, only the existing limits apply.
- **Must NOT be implemented:** invented limits.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / No

### D20 — Rate-limit failure policy (Redis outage)
- **Current repository behaviour:** not applicable.
- **Specification requirement:** none.
- **Contradiction:** none.
- **Options:**
  - fail open (no limiting);
  - degrade to the per-process limiter;
  - fail closed for login only.
- **Recommended option:** degrade to per-process; the DB lockout still applies; never fully open.
- **Consequences:** limits are weaker during an outage.
- **Must NOT be implemented:** silent fail-open.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / **Yes**

### D21 — Trusted proxy and client IP
- **Current repository behaviour:** deployment.md: uvicorn `--proxy-headers`; IP from `request.client`.
- **Specification requirement:** none.
- **Contradiction:** none.
- **Options:** proxy headers with `--forwarded-allow-ips` restricted · edge rate limiting · both.
- **Recommended option:** document and validate the forwarded-IP configuration, plus proxy body-size and connection limits (F6).
- **Consequences:** correct IPs for limits and audit.
- **Must NOT be implemented:** trusting `X-Forwarded-For` from any source.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / No / No — **safe to implement**

### D22 — Production Redis hosting
- **Current repository behaviour:** no production Redis; compose binds Redis to localhost.
- **Specification requirement:** Redis in the architecture [§2 / §3].
- **Contradiction:** none.
- **Options:** managed · self-hosted single · Sentinel. Redis Cluster is excluded (not supported by the Celery Redis broker).
- **Recommended option:** none (hosting / cost — D50).
- **Consequences:** availability of dispatch and limits (correctness does not depend on Redis).
- **Must NOT be implemented:** a Redis Cluster broker; a public Redis.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / No (production blocker)

### D23 — Redis production configuration and guard
- **Current repository behaviour:** any `REDIS_URL` accepted (F8).
- **Specification requirement:** "secret management", "secure" configuration [§22].
- **Contradiction:** none.
- **Options:** documentation only · a start-up guard.
- **Recommended option:**
  - production start-up guard: refuse a non-local `redis://` without TLS / authentication;
  - document ACL users (broker / limiter), noeviction, maxmemory, AOF, monitoring.
- **Consequences:** misconfiguration fails fast.
- **Must NOT be implemented:** storing business data in Redis.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / No / No — **safe to implement**

### D24 — Redis failure behaviour for jobs
- **Current repository behaviour:** 12A: jobs stay QUEUED in SQL Server, are republished on recovery, lazy expiry stays correct.
- **Specification requirement:** 12A lock record D3.
- **Contradiction:** none.
- **Options:** —
- **Recommended option:** keep.
- **Consequences:** none.
- **Must NOT be implemented:** a Redis-dependent correctness path.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / EXISTING REQUIREMENT / No / No

### D25 — RPO / RTO
- **Current repository behaviour:** undefined.
- **Specification requirement:** "backup strategy" [§22]; no values.
- **Contradiction:** none.
- **Options:** RPO ⟨TO SELECT⟩, RTO ⟨TO SELECT⟩.
- **Recommended option:** none (not invented).
- **Consequences:** they determine the log-backup frequency, standby needs and cost.
- **Must NOT be implemented:** a schedule presented as meeting an undefined target.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / **Yes**

### D26 — Backup method, encryption, storage and retention
- **Current repository behaviour:** deployment.md "full + log"; dev DB FULL, test DB SIMPLE.
- **Specification requirement:** "backup strategy", "restore test" [§22].
- **Contradiction:** none.
- **Options:**
  - full + differential + log backups `WITH CHECKSUM`, encrypted, off-host / immutable storage, retention ⟨TO SELECT⟩;
  - managed-database automated backups (if hosted).
- **Recommended option:** the method above. Frequencies and retention per D25 / business.
- **Consequences:** storage cost; restore-time drills.
- **Must NOT be implemented:** unencrypted off-host backups; backup retention without a decision.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / **Yes**

### D27 — Restore test and verification
- **Current repository behaviour:** none.
- **Specification requirement:** "restore test" [§22] — EXISTING requirement.
- **Contradiction:** none.
- **Options:** a manual runbook · a runbook plus an automated verification command.
- **Recommended option:** a runbook plus `manage.py verify-restore`:
  - migration head; trigger presence;
  - ledger conservation;
  - calculation / settlement / report hash checks;
  - a sample of document SHA-256 values against storage;
  - results recorded.
- **Consequences:** a repeatable drill.
- **Must NOT be implemented:** restoring over a live database in a drill.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / EXISTING REQUIREMENT / No / No — **safe to implement**

### D28 — Object storage backup and consistency with DB restores
- **Current repository behaviour:** local files; no backup.
- **Specification requirement:** "versioning" [§22].
- **Contradiction:** none.
- **Options:** bucket versioning · plus replication / a separate backup.
- **Recommended option:** versioning + replication or backup per provider (D2). DB point-in-time restores stay consistent because the
  application never deletes objects.
- **Consequences:** depends on D2.
- **Must NOT be implemented:** application-level deletion that would break restore consistency.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / No / No (needs D2)

### D29 — Development database recovery model
- **Current repository behaviour:** dev DB FULL without log backups (log 136 MB on a nearly full disk); test DB SIMPLE.
- **Specification requirement:** none.
- **Contradiction:** none.
- **Options:** SIMPLE for development · periodic log backups · leave as is.
- **Recommended option:** SIMPLE for the development database only (your machine; your call).
- **Consequences:** no point-in-time restore in development (not needed).
- **Must NOT be implemented:** any change to a production database's recovery model.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / Yes / No

### D30 — Secret management and key rotation
- **Current repository behaviour:** `.env`; one Fernet `DATA_ENCRYPTION_KEY` (no rotation); HS256 `JWT_SECRET` (no key id).
- **Specification requirement:** "secret management", "encryption where appropriate" [§22].
- **Contradiction:** none.
- **Options:**
  - secret store ⟨TO SELECT⟩;
  - Fernet rotation (MultiFernet: decrypt with old + new, re-encrypt job);
  - JWT key id + rotation window.
- **Recommended option:** rotation support (code) once a secret store is chosen.
- **Consequences:** re-encryption job (12A framework); token invalidation window.
- **Must NOT be implemented:** keys in the repository, Redis or logs.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / No (production blocker)

### D31 — Performance targets and data volumes
- **Current repository behaviour:** guards only (20,000-row calculation / report limits).
- **Specification requirement:** §40 lists scenarios (paginated lists, large farm datasets, spatial queries, large lab datasets,
  calculation background job, concurrent reservation / transfer) without numbers.
- **Contradiction:** none.
- **Options:** volumes and SLOs ⟨TO SELECT⟩.
- **Recommended option:** none (not invented). Fix the verified hot spots regardless (D32).
- **Consequences:** without targets, performance work stops at removing obvious defects.
- **Must NOT be implemented:** invented SLOs.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / No

### D32 — Fix verified listing hot spots; pagination contract
- **Current repository behaviour:**
  - whole-table scans + Python filtering (orders, listings, refunds, finance projects);
  - lazy-expiry writes inside GET loops;
  - N+1 mappers;
  - 93 unpaginated list endpoints.
- **Specification requirement:** "pagination", "query optimization" [§22].
- **Contradiction:** changing `list` responses to `Page` responses breaks API contracts (Phase 1–11 "do not change response contracts
  unnecessarily").
- **Options:**
  - SQL-side scoping + eager loading with the response shape unchanged;
  - plus optional `limit` / `offset` keeping the list shape;
  - plus `Page` responses (breaking).
- **Recommended option:** SQL-side scoping + eager loading, plus optional limit / offset that keeps the list shape, for the hot
  listings. Remove read-path expiry writes only if covered by the 12A sweeps — that is a behaviour change, so sign-off.
- **Consequences:** frontend unchanged unless it opts into paging.
- **Must NOT be implemented:** breaking response shapes; removing lazy expiry without sign-off.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / Yes / No

### D33 — Performance test harness
- **Current repository behaviour:** none.
- **Specification requirement:** §40 performance acceptance.
- **Contradiction:** none.
- **Options:** pytest timing + a TEST-only synthetic data generator + Query Store / plans · a load tool (Locust / k6 — new dependency).
- **Recommended option:** pytest-based harness on synthetic TEST data; no new dependency.
- **Consequences:** reproducible baselines.
- **Must NOT be implemented:** performance runs on LIVE data; synthetic data in DEMO.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / No / No — **safe to implement**

### D34 — Calculation execution in workers
- **Current repository behaviour:** synchronous, guarded; **no calculation module registered**.
- **Specification requirement:** §12 "Use Celery for long calculations"; §40 "calculation background job".
- **Contradiction:** the spec wants a background calculation, but no real calculation exists to run.
- **Options:** implement now (new run states) · defer until a production module and volumes exist.
- **Recommended option:** DEFERRED. The 12A framework is ready; the design is in discovery §9.
- **Consequences:** §40 "calculation background job" is not demonstrable until then.
- **Must NOT be implemented:**
  - a DEMO / fake calculation module;
  - client-supplied carbon quantities;
  - Phase 7 semantic changes.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / DEFERRED / Yes / No

### D35 — Report generation in workers
- **Current repository behaviour:** synchronous, deterministic, guarded (20,000 rows), versioned, hashed.
- **Specification requirement:** §22 "background workers" (general).
- **Contradiction:** none.
- **Options:** implement now · defer.
- **Recommended option:** DEFERRED (no evidence of need; the design is in discovery §10).
- **Consequences:** `REPORT_TOO_LARGE` remains for very large runs.
- **Must NOT be implemented:** non-deterministic reports.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / DEFERRED / Yes / No

### D36 — External provider polling
- **Current repository behaviour:** all runtime adapters are MANUAL / none; status queries are on request only (TEST adapters in tests).
- **Specification requirement:** "async integrations" [§22]; Phase 10 D35 and Phase 12A D12 (no polling).
- **Contradiction:** none.
- **Options:** —
- **Recommended option:** DEFERRED until a provider is contracted.
- **Consequences:** none.
- **Must NOT be implemented:** polling of mock / manual providers; fake success.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / DEFERRED / No / No

### D37 — Webhooks
- **Current repository behaviour:** no webhook route (Phase 10 D17); `payment_events` + `ingest_event` exist for TEST.
- **Specification requirement:** none beyond provider interfaces.
- **Contradiction:** none.
- **Options:** —
- **Recommended option:** DEFERRED. The pattern for a future provider: signature → persist → 2xx → job → domain service (discovery §12).
- **Consequences:** none.
- **Must NOT be implemented:** a public webhook endpoint without a provider; business mutation inside the HTTP request.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / DEFERRED / No / No

### D38 — "Mock + Real implementation for every provider" vs honest runtime
- **Current repository behaviour:** no runtime mock provider; TEST adapters exist only in tests (Phases 9A–12A).
- **Specification requirement:** §42 "Every provider must have Mock implementation, Real implementation".
- **Contradiction:** yes — a runtime mock conflicts with the no-fake-provider / honest-DEMO rule locked in Phase 10 (D15 / D33) and
  Phase 12A.
- **Options:** —
- **Recommended option:** keep the existing rule: test doubles in tests only; MANUAL adapters at runtime.
- **Consequences:** none.
- **Must NOT be implemented:** runtime mock providers.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / EXISTING REQUIREMENT / No / No

### D39 — Notification provider (email / SMS / WhatsApp)
- **Current repository behaviour:** channels declared, none implemented.
- **Specification requirement:** §23 `NotificationProvider`, channels IN_APP / EMAIL / SMS / WHATSAPP_ADAPTER; "notification provider"
  is listed as an open decision.
- **Contradiction:** none.
- **Options:** provider(s) ⟨TO SELECT⟩.
- **Recommended option:** none. External delivery is deferred until selected.
- **Consequences:** in-app only.
- **Must NOT be implemented:** fake deliveries; a provider without a contract.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / No

### D40 — In-app notification events and recipients
- **Current repository behaviour:** 14 in-app call sites (Phases 2–5). §23 events after Phase 5 are not wired.
- **Specification requirement:** the §23 event list (farm verified, sample assigned / received, lab result available, retest required,
  calculation complete, QA issue, VVB finding, verification complete, registry status, credit issued, order paid, transfer,
  retirement, payout).
- **Contradiction:** recipients are not specified.
- **Options:** recipients per event ⟨TO SELECT⟩ (role / organization / farmer).
- **Recommended option:** wire the in-app notifications in the business transaction (internal row, no external side effect) once
  recipients are decided.
- **Consequences:** UI bell gets more events.
- **Must NOT be implemented:** notifications revealing data the recipient may not see (respect organization / allow-list rules).
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / No

### D41 — External notification delivery architecture
- **Current repository behaviour:** PENDING / FAILED / `retry_count` columns exist, unused.
- **Specification requirement:** §23.
- **Contradiction:** none.
- **Options:** —
- **Recommended option:** DEFERRED until D39. Pattern: PENDING row in the business transaction → delivery job → SENT / FAILED + retries;
  idempotent per notification.
- **Consequences:** none now.
- **Must NOT be implemented:** external calls inside financial or ledger transactions.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / DEFERRED / No / No

### D42 — Consent, opt-out, quiet hours and language for external channels
- **Current repository behaviour:** consent definitions (Phase 2) and `preferred_language` exist.
- **Specification requirement:** none explicit.
- **Contradiction:** none.
- **Options:** ⟨TO SELECT⟩.
- **Recommended option:** none. Required before SMS / WhatsApp to farmers.
- **Consequences:** legal exposure without it.
- **Must NOT be implemented:** messaging farmers without consent.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / No (deferred with D39)

### D43 — Monitoring platform
- **Current repository behaviour:** none (logs, DB tables, `/jobs/status`).
- **Specification requirement:** "observability: structured logs, request_id, track API / job / DB / lab / registry / payment failures,
  security events" [§22].
- **Contradiction:** none.
- **Options:** Prometheus + Grafana + Alertmanager · a cloud provider's monitoring · SaaS APM / logging · an OpenTelemetry collector.
- **Recommended option:** none (hosting / cost — D50).
- **Consequences:** determines the metrics exposure format (D44).
- **Must NOT be implemented:** shipping logs containing personal data to an unapproved third party.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / No

### D44 — Minimum observability in code
- **Current repository behaviour:** plain-text logs except the JSON `app.jobs` logs; `api_access_logs`; `security_events`.
- **Specification requirement:** structured logs with `request_id` [§22].
- **Contradiction:** none.
- **Options:**
  - stdlib JSON log formatter for all loggers + request / job correlation;
  - plus a metrics surface (Prometheus client or OTel, per D43).
- **Recommended option:** JSON logging now (no dependency); a metrics surface once D43 is chosen.
- **Consequences:** log format change (documented).
- **Must NOT be implemented:** logging secrets / PII / payloads.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / No / No — **safe to implement** (JSON logging part)

### D45 — Alert routing and on-call
- **Current repository behaviour:** none.
- **Specification requirement:** none (Phase 12 D15 left it open).
- **Contradiction:** none.
- **Options:** recipients / channel ⟨TO SELECT⟩.
- **Recommended option:** none.
- **Consequences:** alerts without an owner are ineffective.
- **Must NOT be implemented:** —
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / No

### D46 — Health endpoints
- **Current repository behaviour:** public `/health` (with environment); authenticated `/jobs/status`.
- **Specification requirement:** none specific.
- **Contradiction:** none.
- **Options:** keep · `/health/live` + `/health/ready` without internal detail.
- **Recommended option:** add live / ready (keep `/health` for compatibility, but drop the environment field in production — F9).
- **Consequences:** load-balancer probes.
- **Must NOT be implemented:** topology details on public endpoints.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / No / No — **safe to implement**

### D47 — Security fixes F1, F5 (mechanism only), F6, F8, F9
- **Current repository behaviour:** see discovery §15 (evidence).
- **Specification requirement:** §22 security list.
- **Contradiction:** none.
- **Options:** fix in 12B-II · leave.
- **Recommended option:**
  - fix: Swagger / OpenAPI off in production (F1);
  - a refresh-limit hook using the existing settings pattern, value per D19 (F5);
  - proxy body-limit documentation (F6);
  - Redis production guard (F8, with D23);
  - health detail (F9).
- **Consequences:** `/docs` unavailable in production.
- **Must NOT be implemented:** invented limit values.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / No / No — **safe to implement**

### D48 — Retention periods (all record classes)
- **Current repository behaviour:** immutability / append-only defined. **No period defined anywhere.** The 12A purge job purges nothing.
- **Specification requirement:** none. deployment.md asks for an `api_access_logs` policy.
- **Contradiction:** a privacy expectation for `api_access_logs` (IP, user agent) conflicts with the current "keep forever" behaviour
  (F10).
- **Options:** periods ⟨TO SELECT⟩ for:
  - audit / workflow / security / login / access logs;
  - documents and evidence; calculation records; ledger / money / registry / verification records;
  - job history; notifications; backups; monitoring data.
- **Recommended option:** none (legal / registry-driven). Likely "never" for ledger / financial / registry / verification / audit.
- **Consequences:** storage growth until decided.
- **Must NOT be implemented:** any purge without an approved period.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / No

### D49 — DEMO / TEST / LIVE behaviour of Phase 12B components
- **Current repository behaviour:** an environment on every record; honest DEMO; TEST-only adapters.
- **Specification requirement:** honest DEMO; TEST adapters allowed; LIVE real or manual.
- **Contradiction:** none.
- **Options:** —
- **Recommended option:** the matrix in discovery §17 (separate buckets, scanner per environment, environment key prefixes, no
  performance runs on LIVE / DEMO, no fake provider success).
- **Consequences:** none.
- **Must NOT be implemented:** fake payments / registry / credits / payouts / verification / provider success.
- **Type / Status / Sign-off / Blocker:** TECHNICAL / RECOMMENDATION / No / No — **safe to implement**

### D50 — Production hosting and data residency
- **Current repository behaviour:** undefined; compose is not exercised; the dev machine is Windows.
- **Specification requirement:** "production hosting", "data residency" listed as open decisions.
- **Contradiction:** none.
- **Options:** cloud provider / region / on-premises ⟨TO SELECT⟩.
- **Recommended option:** none. Workers on Linux (12A).
- **Consequences:** drives D2, D13, D22, D26, D43.
- **Must NOT be implemented:** provider-specific infrastructure code before the choice.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / No (production blocker)

### D51 — Development / test infrastructure for 12B
- **Current repository behaviour:** about 185 MB free; no Docker / WSL / Redis; MinIO and ClamAV cannot run locally.
- **Specification requirement:** "MinIO for local development"; tests at every phase.
- **Contradiction:** the spec wants local MinIO, but the machine cannot run it.
- **Options:**
  - free disk / install WSL2 or Docker on this machine (your decision);
  - a separate test host / CI runner with MinIO + ClamAV + Redis;
  - stub-only testing (S3 HTTP stub, INSTREAM stub) with real-service integration tests reported as not run.
- **Recommended option:** none (your environment). Stub-only is possible but weaker.
- **Consequences:** determines what can be verified before release.
- **Must NOT be implemented:** obsolete Windows Redis; deleting unrelated files to make space.
- **Type / Status / Sign-off / Blocker:** BUSINESS / OPEN DECISION / Yes / **Yes**

---

## Contradictions C1–C6

| C | Contradiction | Source A | Source B | Resolution proposed |
|---|---|---|---|---|
| C1 | "Signed access" vs audited, integrity-checked downloads | §22 | `document_service.download` (audit + re-hash every read) | D6: keep API streaming; "signed access" = authenticated, audited access |
| C2 | Mock + Real provider for every provider | §42 | honest runtime (Phase 10 D15 / D33, 12A) | D38: test doubles only in tests |
| C3 | "Use Celery for long calculations" / "calculation background job" | §12, §40 | no registered module; synchronous guarded execution | D34: deferred until a module exists |
| C4 | Notification events listed | §23 | recipients undefined; provider open | D39 / D40 |
| C5 | MinIO for local development | §2 | machine cannot run MinIO / Docker | D51 |
| C6 | Access-log privacy vs keep-forever | deployment.md (policy needed) | 12A: no retention invented | D48 |

---

## DECISION SUMMARY

| ID | Topic | Type | Status | Sign-off | Blocker | Safe now |
|----|-------|------|--------|----------|---------|----------|
| D1 | 12B scope / sub-phases | TECHNICAL | RECOMMENDATION | Yes | **Yes** | |
| D2 | S3 provider | BUSINESS | OPEN DECISION | Yes | prod | |
| D3 | S3 client library | TECHNICAL | RECOMMENDATION | Yes | **Yes** | |
| D4 | Bucket layout / keys | TECHNICAL | RECOMMENDATION | No | | |
| D5 | File encryption at rest | BUSINESS | OPEN DECISION | Yes | **Yes** | |
| D6 | Download path (presigned?) | TECHNICAL | RECOMMENDATION | Yes | | |
| D7 | Upload path | TECHNICAL | RECOMMENDATION | No | | |
| D8 | Versioning / Object Lock | BUSINESS | OPEN DECISION | Yes | | |
| D9 | Local → S3 migration tool | TECHNICAL | RECOMMENDATION | No | | |
| D10 | Orphan deletion | TECHNICAL | RECOMMENDATION | Yes | | |
| D11 | Write-before-commit kept | TECHNICAL | RECOMMENDATION | No | | |
| D12 | Scan architecture | TECHNICAL | RECOMMENDATION | Yes | **Yes** | |
| D13 | AV engine | BUSINESS | OPEN DECISION | Yes | **Yes** | |
| D14 | Scanner outage policy | BUSINESS | OPEN DECISION | Yes | **Yes** | |
| D15 | Scan history + rescans | TECHNICAL | RECOMMENDATION | No | | |
| D16 | Quarantine release | BUSINESS | OPEN DECISION | Yes | | |
| D17 | Scanning per environment | TECHNICAL | RECOMMENDATION | No | | |
| D18 | Redis rate limiter | TECHNICAL | RECOMMENDATION | No | | |
| D19 | New limit values | BUSINESS | OPEN DECISION | Yes | | |
| D20 | Limiter outage policy | BUSINESS | OPEN DECISION | Yes | **Yes** | |
| D21 | Trusted proxy / IP | TECHNICAL | RECOMMENDATION | No | | **Yes** |
| D22 | Production Redis hosting | BUSINESS | OPEN DECISION | Yes | prod | |
| D23 | Redis config + guard | TECHNICAL | RECOMMENDATION | No | | **Yes** |
| D24 | Redis failure (jobs) | TECHNICAL | EXISTING REQUIREMENT | No | | |
| D25 | RPO / RTO | BUSINESS | OPEN DECISION | Yes | **Yes** | |
| D26 | Backup method / retention | BUSINESS | OPEN DECISION | Yes | **Yes** | |
| D27 | Restore test + verification | TECHNICAL | EXISTING REQUIREMENT | No | | **Yes** |
| D28 | Object storage backup | TECHNICAL | RECOMMENDATION | No | | |
| D29 | Dev DB recovery model | TECHNICAL | RECOMMENDATION | Yes | | |
| D30 | Secrets / key rotation | BUSINESS | OPEN DECISION | Yes | prod | |
| D31 | Performance targets | BUSINESS | OPEN DECISION | Yes | | |
| D32 | Listing hot spots / paging | TECHNICAL | RECOMMENDATION | Yes | | |
| D33 | Performance harness | TECHNICAL | RECOMMENDATION | No | | **Yes** |
| D34 | Calculation workers | TECHNICAL | DEFERRED | Yes | | |
| D35 | Report workers | TECHNICAL | DEFERRED | Yes | | |
| D36 | Provider polling | TECHNICAL | DEFERRED | No | | |
| D37 | Webhooks | TECHNICAL | DEFERRED | No | | |
| D38 | Mock + Real providers (spec) | TECHNICAL | EXISTING REQUIREMENT | No | | |
| D39 | Notification provider | BUSINESS | OPEN DECISION | Yes | | |
| D40 | In-app events / recipients | BUSINESS | OPEN DECISION | Yes | | |
| D41 | External delivery architecture | TECHNICAL | DEFERRED | No | | |
| D42 | Consent / language | BUSINESS | OPEN DECISION | Yes | | |
| D43 | Monitoring platform | BUSINESS | OPEN DECISION | Yes | | |
| D44 | Minimum observability (JSON logs) | TECHNICAL | RECOMMENDATION | No | | **Yes** |
| D45 | Alert routing / on-call | BUSINESS | OPEN DECISION | Yes | | |
| D46 | Health live / ready | TECHNICAL | RECOMMENDATION | No | | **Yes** |
| D47 | Security fixes F1 / F5 / F6 / F8 / F9 | TECHNICAL | RECOMMENDATION | No | | **Yes** |
| D48 | Retention periods | BUSINESS | OPEN DECISION | Yes | | |
| D49 | DEMO / TEST / LIVE matrix | TECHNICAL | RECOMMENDATION | No | | **Yes** |
| D50 | Hosting / data residency | BUSINESS | OPEN DECISION | Yes | prod | |
| D51 | Dev / test infrastructure | BUSINESS | OPEN DECISION | Yes | **Yes** | |

**Statuses:** 21 OPEN DECISION · 22 RECOMMENDATION · 3 EXISTING REQUIREMENT · 5 DEFERRED.

---

## COUNTS

- **TOTAL DECISIONS:** 51
- **BUSINESS DECISIONS:** 21 (D2, D5, D8, D13, D14, D16, D19, D20, D22, D25, D26, D30, D31, D39, D40, D42, D43, D45, D48, D50, D51)
- **TECHNICAL DECISIONS:** 30
- **RECOMMENDATIONS REQUIRING YOUR SIGN-OFF:** 9 technical (D1, D3, D6, D10, D12, D29, D32, plus deferrals D34, D35 because they defer
  explicit spec text). In addition, all 21 business decisions require sign-off — 30 in total.
- **BLOCKERS BEFORE IMPLEMENTATION:** 10 (D1, D3, D5, D12, D13, D14, D20, D25, D26, D51)
- **SAFE TO IMPLEMENT WITHOUT FURTHER DECISION:** 8 (D21, D23, D27, D33, D44, D46, D47, D49), once the 12B scope (D1) is approved
- **Production (go-live) blockers in addition:** D2, D22, D30, D50

## WHAT IS NOT IMPLEMENTED BY THIS DOCUMENT

Nothing. No code, migration, dependency, configuration or database change was made.
