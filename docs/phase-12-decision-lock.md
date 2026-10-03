# Phase 12 — Decision lock (for human review)

> **No implementation.** This document prepares the Phase 12 decisions for sign-off. No application code, migration, schema,
> dependency, configuration or database was changed. Source: [phase-12-discovery.md](phase-12-discovery.md) (sections A–AL, C1–C9) and
> the master specification. Baseline commit `6312792`; latest migration `0016`.

## How to read this document

Every decision carries **exactly one** classification:

| Classification | Meaning | Count |
|---|---|---|
| **BUSINESS DECISION REQUIRED** | The specification and the repository do not define the answer (policy, operations, hosting, money-adjacent timing). Only the business / operations owner can lock it. | 11 |
| **RECOMMENDATION — REQUIRES SIGN-OFF** | Discovery recommends an answer that changes behaviour visible to users, auditors or operators; a human must accept or replace it. | 10 |
| **TECHNICAL DECISION** | An engineering choice that follows from the existing architecture (Phases 1–11) and the specification (§2, §3, §22). Recorded for review; no business rule is involved. | 15 |

Rules applied:

- No interval, retention period, retry count, time limit, threshold or provider is presented as a requirement.
  - Business values use `⟨BUSINESS TO SELECT …⟩` placeholders.
  - Engineering defaults are marked as such and are configurable.
- No financial transition is proposed for background execution.
- Every lazy / synchronous correctness check from Phases 7–11 is kept.

---

## Index of the most important decisions

| # | Topic | Decision | Classification |
|---|---|---|---|
| 1 | Phase 12 scope (jobs vs full §22 hardening) | D1 | RECOMMENDATION — REQUIRES SIGN-OFF |
| 2 | Job framework | D2 | TECHNICAL DECISION |
| 3 | Where job state lives (DB vs Redis) | D3 | TECHNICAL DECISION |
| 4 | Who is the actor of system actions | D4 | RECOMMENDATION — REQUIRES SIGN-OFF |
| 5 | Reservation expiry when a payment was reported | D6 | BUSINESS DECISION REQUIRED |
| 6 | Sweep intervals | D7 | BUSINESS DECISION REQUIRED |
| 7 | No financial transition in a worker | D13 | RECOMMENDATION — REQUIRES SIGN-OFF |
| 8 | Scheduled settlement runs | D11 | BUSINESS DECISION REQUIRED |
| 9 | Retention periods | D10 | BUSINESS DECISION REQUIRED |
| 10 | Local development environment | D18 | BUSINESS DECISION REQUIRED |
| 11 | Redis hosting / HA | D17 | BUSINESS DECISION REQUIRED |
| 12 | Dead-job alerting / on-call | D15 | BUSINESS DECISION REQUIRED |

---

## D1–D36

### D1

Title: Phase 12 scope

Current requirement:
- §22 Phase 12 "Production hardening":
  - security review;
  - malware scanning adapter;
  - MinIO / S3 storage;
  - structured logs;
  - deadlock handling;
  - backup / restore test;
  - performance;
  - background workers;
  - Redis caching;
  - async integrations.
- The current request: Celery / Redis / background jobs / retries / idempotency / monitoring / audit.

Problem:
- The specification's Phase 12 is much broader than the requested direction. Doing everything at once is large and risky.

Options:
- Option A — Phase 12 = jobs only; the remaining §22 items are unplanned.
- Option B — Phase 12 = all of §22 in one phase.
- Option C — Split, as Phases 8 and 9 were:
  - **12A**: job infrastructure (Celery, Redis, job table, workers, beat, sweeps, monitoring of jobs);
  - **12B**: the remaining hardening (Redis rate limiter if not in 12A, S3 adapter, antivirus adapter, structured logs, security
    review, backup / restore, performance).

Discovery recommendation:
- Option C.

Impact:
- Scope, sequencing and the exit report of each sub-phase.

Decision classification:
- RECOMMENDATION — REQUIRES SIGN-OFF

Proposed locked wording:
- "Phase 12 is split into 12A (background jobs: Celery, Redis, job records, workers, scheduler, job monitoring) and 12B (remaining §22
  hardening). This decision lock covers 12A; 12B items listed here are only boundaries."

---

### D2

Title: Job framework

Current requirement:
- §2 "Background jobs: Celery, Redis"; §3 architecture (FastAPI + SQL Server + Redis + Celery); §12 "Use Celery for long calculations".
- Repo: no task library is installed. `app/workers/` exists, empty. `REDIS_URL` is configured but unused.

Problem:
- A framework must be chosen and pinned. Alternatives (RQ, Dramatiq, DB polling with APScheduler) would deviate from the
  specification.

Options:
- Option A — Celery 5.x with a Redis broker.
- Option B — An alternative queue library.
- Option C — DB-polling only (no Redis).

Discovery recommendation:
- Option A. The latest stable Celery 5.x supporting Python 3.10 is verified and pinned at implementation.

Impact:
- Dependencies (`celery[redis]`), deployment processes and tests.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "Background jobs use Celery 5.x with a Redis broker, as specified in §2 / §3; versions are pinned in `requirements/base.txt` after
  verification."

---

### D3

Title: System of record for job state; transactional outbox

Current requirement:
- Repo: the DB is the record for every business state. Audit is atomic with the change. External calls use the outbox pattern
  (Phases 9A, 10, 11).

Problem:
- The Celery result backend and Redis are not durable or auditable enough for job history. Publishing a task inside a business
  transaction can create phantom tasks (if the transaction rolls back) or lose tasks (if the publish fails).

Options:
- Option A — A `background_jobs` table (+ `background_job_attempts`) as the record:
  - the job row is inserted in the same transaction as the business change;
  - it is published after commit;
  - a periodic dispatcher re-publishes QUEUED rows;
  - the Celery result backend is disabled.
- Option B — Celery result backend (Redis) as the record.
- Option C — Fire-and-forget tasks with no record.

Discovery recommendation:
- Option A.

Impact:
- Migration `0017` (D25), exactly-once *effect* with at-least-once delivery, and auditability.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "SQL Server is the system of record for every background job and attempt. Jobs are created in the same transaction as the change
  that requires them (outbox) and published to Redis only after commit; Redis is transport only and holds no business data."

---

### D4

Title: System actor for scheduled / system actions

Current requirement:
- Repo:
  - `credit_ledger_entries.actor_id` is NOT NULL.
  - Expiry uses `ctx.user_id or r.created_by` (`order_service.py:214`, `ledger_service.py:331`).
  - `RequestContext.system()` exists with `user_id = None`.
  - `audit_logs.user_id` is nullable.

Problem:
- A scheduled sweep has no user, so expiry ledger entries would name the reservation's creator as the actor.
- Today, lazy expiry names whoever triggered the read, which can be a user of another organization.
- Both are misleading in an audit trail.

Options:
- Option A — One **non-login system actor** per environment:
  - a `users` row with a dedicated status / flag;
  - no password, no roles, no permissions;
  - used as `actor_id` and `audit_logs.user_id` for system-owned transitions;
  - may also be used by lazy expiry going forward.
- Option B — Keep the current fallback (creator / triggering reader).
- Option C — Make `actor_id` nullable for system entries. This changes the 9B schema and triggers, which is not recommended.

Discovery recommendation:
- Option A.
- Whether lazy expiry also switches to the system actor needs sign-off, because it changes how existing audit entries are attributed
  from now on.

Impact:
- Seed data, possibly a user-status CHECK change, audit and ledger attribution, and the security review ("must hold no permission").

Decision classification:
- RECOMMENDATION — REQUIRES SIGN-OFF

Proposed locked wording:
- "System-owned transitions (deadline expiry, housekeeping, recording provider-reported outcomes) are attributed to a per-environment,
  non-login SYSTEM actor that holds no role or permission. Lazy expiry ⟨BUSINESS TO SELECT: also uses the SYSTEM actor / keeps the
  current attribution⟩."

---

### D5

Title: Initial background workloads and the existing "no worker" decisions

Current requirement:
- Phase 9B D4 and Phase 10 D5: lazy expiry, "no background worker". `document_service.py:8` plans an orphan sweep.
- Phase 7 A18 / 8A B11: synchronous calculation and report generation with size guards.

Problem:
- Adding sweeps changes the wording (not the correctness) of locked decisions. The initial job list must be agreed.

Options:
- Option A — 12A jobs:
  - order / listing / reservation expiry sweeps;
  - the outbox dispatcher;
  - stuck-lease recovery;
  - the orphan-file sweep;
  - retention purges (only with D10 values);
  - calculation and report jobs (per D8 / D9);
  - provider polling (per D12; disabled in LIVE).
- Option B — Infrastructure only, with no workloads.
- Option C — More workloads (notifications, AV), blocked by D31 / D32.

Discovery recommendation:
- Option A. Lazy expiry and the manual `expire-due` endpoint remain as correctness guarantees.

Impact:
- Amends the wording of Phase 9B D4 and Phase 10 D5 ("No worker" → "lazy expiry plus scheduled sweeps").

Decision classification:
- RECOMMENDATION — REQUIRES SIGN-OFF

Proposed locked wording:
- "Phase 12A adds scheduled sweeps that call the existing idempotent expiry functions; lazy expiry on reads and writes remains and stays
  the correctness guarantee. Phase 9B D4 and Phase 10 D5 are amended accordingly."

---

### D6

Title: Reservation expiry for an order whose buyer reported a payment

Current requirement:
- Phase 10 D18 / D23 (`order_service.py:202-203`): a PENDING_CONFIRMATION payment holds the order, "its 9B reservations still expire on
  their own". At confirmation, a lost reservation leads to ATTENTION_REQUIRED (re-reserve or refund).

Problem:
- Today this happens only when someone touches the batch. A scheduled sweep makes it happen reliably at the deadline: a buyer who paid
  on time but whose payment was not confirmed before `expires_at` loses the reservation.

Options:
- Option A — Keep the rule: the sweep expires these reservations, as lazy expiry already would.
- Option B — The sweep (and lazy expiry) skips reservations of orders with a PENDING_CONFIRMATION payment until the finance decision.
  This changes Phase 10 behaviour.
- Option C — Option B, but with an upper bound ⟨BUSINESS TO SELECT⟩.

Discovery recommendation:
- None. This is a commercial / customer-protection choice. Option A keeps Phase 10 unchanged.

Impact:
- Buyer experience, inventory availability and the Phase 10 rule. B / C require changes to 9B / 10 service code.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Reservations of an order whose payment is PENDING_CONFIRMATION ⟨BUSINESS TO SELECT: expire at the order deadline as today (A) / are
  held until the finance decision (B) / are held for at most ___ (C)⟩."

---

### D7

Title: Sweep intervals and ordering

Current requirement:
- None. Deadlines are exact timestamps; lazy expiry enforces them on access.

Problem:
- The interval decides how quickly expired inventory, orders and listings appear as expired, which affects users and reports.

Options:
- Option A — An interval per sweep ⟨BUSINESS TO SELECT⟩, configurable by environment variable.
- Option B — One interval for all sweeps.

Discovery recommendation:
- Option A, with a fixed order within a cycle: orders → listings → remaining reservations (Phase 10 D26 lock order).
- No value is proposed.

Impact:
- DB load, user-visible promptness and audit timing.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Expiry sweeps run every ⟨BUSINESS TO SELECT: orders ___, listings ___, reservations ___⟩ in the order orders → listings →
  reservations; values are configuration, not code."

---

### D8

Title: Asynchronous calculation execution

Current requirement:
- §12 "Use Celery for long calculations".
- Phase 7 A18: synchronous; runs over `CALCULATION_MAX_INPUT_ROWS` are BLOCKED (`INPUT_TOO_LARGE`).
- No production calculation module is registered.

Problem:
- Large runs cannot complete today. Async execution changes the user experience: a run is "queued" and its result arrives later.

Options:
- Option A — Everything async.
- Option B — Sync below the guard; async above it (replaces BLOCKED `INPUT_TOO_LARGE` with a queued execution).
- Option C — Keep synchronous only.

Discovery recommendation:
- Option B. The worker re-checks the run state and the frozen snapshot under lock and re-authorizes the requester.

Impact:
- A calculation run status / queued indicator, the Phase 7 A18 amendment, the `calculation` queue and time limits.

Decision classification:
- RECOMMENDATION — REQUIRES SIGN-OFF

Proposed locked wording:
- "Calculation runs at or below CALCULATION_MAX_INPUT_ROWS execute synchronously as today; larger runs are queued as a background job
  that re-checks the run state and the requester's permission at execution. Phase 7 A18 is amended accordingly."

---

### D9

Title: Asynchronous calculation report generation

Current requirement:
- Phase 8A B11: synchronous; larger reports are refused (`REPORT_TOO_LARGE`, "background generation is not available yet").

Problem:
- Large reports cannot be produced.

Options:
- Option A — Async above the guard, sync below it.
- Option B — Always async.
- Option C — Keep synchronous.

Discovery recommendation:
- Option A. Determinism and the content hash are unchanged.

Impact:
- Report status UX, the `reports` queue, and the Phase 8A B11 amendment.

Decision classification:
- RECOMMENDATION — REQUIRES SIGN-OFF

Proposed locked wording:
- "Calculation reports within CALCULATION_REPORT_MAX_ROWS are generated synchronously; larger ones are generated by a background job
  with the same deterministic content and hash."

---

### D10

Title: Retention periods and the orphan-file grace period

Current requirement:
- deployment.md item 8: "set a retention policy for `api_access_logs`".
- Audit / workflow / security / ledger / financial tables are append-only.
- No retention period is defined anywhere.

Problem:
- Purge jobs need periods, and legal and regulatory retention is a business matter.

Options:
- Option A — Per-category retention ⟨BUSINESS TO SELECT⟩ for `api_access_logs`, expired `sessions` / `refresh_tokens`, read
  notifications, finished job rows, and an orphan-file grace period. Append-only audit and business tables are never purged.
- Option B — No purge in 12A.

Discovery recommendation:
- Option A, with each category disabled (never purge) until a value is set.

Impact:
- Storage growth, privacy (IP addresses and user agents in access logs), and legal holds.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Retention: api_access_logs ⟨___⟩, expired sessions / refresh tokens ⟨___⟩, read notifications ⟨___⟩, finished job records ⟨___⟩,
  orphaned files after ⟨___⟩. Audit, workflow, security, ledger, document and financial records are never purged by a job."

---

### D11

Title: Scheduled settlement runs

Current requirement:
- The Phase 11 decision lock: "Settlement cycle: ⟨BUSINESS TO SELECT: none (manual runs) / ___⟩. Scheduled runs are Phase 12".
- Phase 11 implemented manual runs only.

Problem:
- Automating settlement creation or calculation is a financial-process change.

Options:
- Option A — None: settlement stays manual.
- Option B — A scheduled job may **create and calculate** DRAFT runs on a cycle ⟨BUSINESS TO SELECT⟩. Submission and approval stay
  human. The system actor (D4) would become the calculator, which affects SoD.
- Option C — Reminders only (in-app notification that unsettled revenue exists).

Discovery recommendation:
- Option A for 12A. The cycle was never selected by the business.

Impact:
- Financial controls and SoD attribution.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Settlement runs ⟨BUSINESS TO SELECT: remain manual (A) / are created and calculated on a ___ cycle, never submitted or approved
  automatically (B) / trigger reminders only (C)⟩."

---

### D12

Title: Provider status polling

Current requirement:
- Phase 9A / 10 D35: a status is "queried once on request — no job, no automatic retry". Phase 11: `query_status` (non-MANUAL only).
- LIVE adapters are MANUAL only.

Problem:
- §22 "async integrations" vs no contracted provider. Polling could only exercise TEST adapters.

Options:
- Option A — Build a generic polling task for non-MANUAL adapters, disabled unless a non-MANUAL adapter is configured; it records only
  provider-owned outcomes.
- Option B — No polling until a provider is contracted.

Discovery recommendation:
- Option B for LIVE behaviour. Option A only as a disabled, tested mechanism if desired. MANUAL is never polled. Polling never
  confirms, approves or reconciles.

Impact:
- Phase 9A / 10 D35 wording.

Decision classification:
- RECOMMENDATION — REQUIRES SIGN-OFF

Proposed locked wording:
- "Provider status polling exists only for non-MANUAL adapters and is disabled until a provider is contracted; it records
  provider-reported outcomes under the entity lock and never confirms a payment, approves, pays, reconciles or retries a non-idempotent
  call."

---

### D13

Title: No financial transition executed by a worker

Current requirement:
- Phase 10 / 11 financial safety rules; separation of duties per person; revenue recognition inside the delivery transaction.

Problem:
- Background execution could bypass approval, SoD or reconciliation, or duplicate revenue or payouts.

Options:
- Option A — Explicit allow-list: workers may only perform system-owned transitions (deadline expiry, housekeeping,
  provider-reported outcomes per D12). Every other transition stays user-initiated and synchronous.
- Option B — Case by case.

Discovery recommendation:
- Option A, enforced by a test that introspects registered tasks (like the Phase 11 OpenAPI amount check).

Impact:
- Defines the 12A boundary for every financial module.

Decision classification:
- RECOMMENDATION — REQUIRES SIGN-OFF

Proposed locked wording:
- "No background job recognizes or reverses revenue, creates / calculates / approves settlements, creates / approves / executes /
  confirms / reconciles payouts, confirms payments, completes refunds, moves credits on a user's behalf or closes recovery cases.
  Revenue recognition and reversal stay inside their Phase 10 transactions."

---

### D14

Title: Retry policy

Current requirement:
- `ledger_service.run()` retries deadlock victims 3 times. External non-idempotent calls are never retried automatically
  (UNCONFIRMED).

Problem:
- Retries must not repeat business refusals or non-idempotent calls.

Options:
- Option A — Retry only transient infrastructure errors, with exponential backoff and full jitter, capped. `max_attempts`, base and
  cap delays per job type are configurable (engineering defaults set at implementation, not business values). `AppError` refusals →
  FAILED / SKIPPED, no retry.
- Option B — Celery autoretry on all exceptions.

Discovery recommendation:
- Option A.

Impact:
- Reliability and the DEAD volume.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "Jobs retry only transient infrastructure failures with capped exponential backoff and jitter (configurable per job type); business
  refusals end the job without retry; non-idempotent external calls are never retried."

---

### D15

Title: Dead jobs: alerting, ownership and manual retry

Current requirement:
- None. `security_events` exists; in-app notifications exist.

Problem:
- Someone must be told and must act on DEAD jobs, and must be authorized to retry or cancel them.

Options:
- Option A — Alert ⟨BUSINESS TO SELECT: role(s) / channel⟩. Manual retry / cancel by the D16 permission, audited, re-validated.
- Option B — Logging only.

Discovery recommendation:
- Option A. The on-call role or channel is a business / operations choice.

Impact:
- Operational process.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "A DEAD job raises ⟨BUSINESS TO SELECT: alert channel / recipients⟩; only holders of the job-management permission may retry or cancel
  it, with a reason, audited; a retry re-validates every precondition."

---

### D16

Title: Job permissions and administration UI

Current requirement:
- RBAC with organization scoping (404 / 403). No job permission exists.

Problem:
- Who may see and manage jobs.

Options:
- Option A — `jobs.read` and `jobs.manage` (retry / cancel / run maintenance now), granted to PLATFORM_ADMIN only. Organization users
  see their own user-requested jobs through the owning entity (for example the calculation run status).
- Option B — Organization-level job managers as well.

Discovery recommendation:
- Option A. No new role.

Impact:
- Permission seed and role counts (`test_admin_orgs_roles_api.py` / `test_unit_core.py` only if a role is added), plus the admin page.

Decision classification:
- RECOMMENDATION — REQUIRES SIGN-OFF

Proposed locked wording:
- "New permissions `jobs.read` and `jobs.manage` are granted to the Platform Administrator only; organization users see the status of
  jobs they requested through the owning record; no new role."

---

### D17

Title: Redis hosting, durability and high availability

Current requirement:
- §2 Redis. compose: `redis:7-alpine`, no auth, no persistence settings, port published.

Problem:
- Production Redis hosting is an infrastructure / cost decision.

Options:
- Option A — Managed Redis (cloud service).
- Option B — Self-hosted single instance with AOF.
- Option C — Self-hosted with Sentinel / replica.

In every case: auth + TLS, `noeviction` for the broker, environment key prefixes, and a separate instance or DB per environment.

Discovery recommendation:
- None for the hosting choice (no production platform is defined; D34). The security settings are recommended in all options.

Impact:
- Availability of job dispatch (correctness does not depend on Redis).

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Production Redis is ⟨BUSINESS TO SELECT: managed / self-hosted single / self-hosted HA⟩, version 7.x, with authentication, TLS,
  noeviction and per-environment separation."

---

### D18

Title: Local development and test environment for Redis / Celery

Current requirement:
- Repo / machine:
  - Windows 11;
  - no Docker;
  - compose "not exercised";
  - your archived Redis 3.0.504 Windows port (unsuitable, not running);
  - `wsl.exe` present;
  - about 300 MB free on C:.
- Celery does not support Windows prefork workers officially.

Problem:
- A real broker and worker are needed for integration tests and E2E. Installing software on your machine is your decision.

Options:
- Option A — Redis in WSL2 (requires a distribution and disk space).
- Option B — Docker Desktop (large disk footprint).
- Option C — Memurai (Windows-native, licence terms apply).
- Option D — A remote development Redis.
- Option E — No local Redis: eager task execution for development and tests; real-worker tests only where Redis is available.

Worker on Windows: `-P solo` / `threads`.

Discovery recommendation:
- None. It depends on your machine, disk space and policy. Option E is possible without installing anything, but leaves real
  re-delivery untested locally.

Impact:
- Feasibility of integration tests and E2E, and the disk-space risk.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Local Redis / Celery runs via ⟨BUSINESS TO SELECT: WSL2 / Docker / Memurai / remote / eager-only⟩; Windows workers use the solo pool;
  production workers run on ⟨D34⟩."

---

### D19

Title: Test strategy for jobs

Current requirement:
- Rolled-back test DB; snapshot-based real concurrency tests (9B / 10 / 11); E2E against DEMO.

Problem:
- Celery adds broker-dependent behaviour.

Options:
- Option A — Three tiers:
  - direct task-function and service tests on the rolled-back DB;
  - eager-mode tests for routing / serialization;
  - snapshot concurrency tests (claim exclusivity, sweep vs T3 / cancel / lazy expiry, duplicate slot).

  Plus broker integration tests (re-delivery after a killed worker, Redis restart) when Redis is available (D18), skipped otherwise
  with an explicit report.
- Option B — Eager mode only.

Discovery recommendation:
- Option A.

Impact:
- Test duration and CI requirements.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "Jobs are tested directly, in eager mode and under real cross-connection concurrency; broker integration tests run where Redis is
  available and their skip is reported explicitly."

---

### D20

Title: Beat schedule storage and singleton

Current requirement:
- None.

Problem:
- Duplicate beats duplicate work, and editable schedules are an attack / config-drift surface.

Options:
- Option A — Static schedule in code + environment variables. Exactly one beat process per environment. Slot-keyed idempotency
  (`<type>:<slot>`) absorbs an accidental second beat.
- Option B — DB-editable schedules (django-celery-beat style) with an admin UI.

Discovery recommendation:
- Option A.

Impact:
- Operations and the migration (no schedule table).

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "Periodic schedules are static configuration; one beat per environment; every periodic job carries a slot idempotency key so
  duplicates are impossible."

---

### D21

Title: Locking — SQL Server authoritative

Current requirement:
- Repo: `UPDLOCK, HOLDLOCK, ROWLOCK`, fixed lock order, filtered unique indexes, `run()` deadlock retry.

Problem:
- Redis locks can be lost; financial and ledger correctness must not depend on them.

Options:
- Option A — DB row locks and unique indexes remain the only correctness mechanism. Job exclusivity comes from the DB claim / lease.
  Redis locks only for non-correctness singletons.
- Option B — Redis (Redlock) for job exclusivity.

Discovery recommendation:
- Option A.

Impact:
- None on existing code.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "Correctness locking stays in SQL Server (row locks, lock order, unique indexes, DB job claims); Redis locks are never relied on for
  ledger, financial or job-exclusivity correctness."

---

### D22

Title: Redis-backed rate limiter and its failure policy

Current requirement:
- `core/rate_limit.py`: in-memory; "Redis backend required before running multiple API workers"; deployment.md item 6.

Problem:
- Shared Redis makes this cheap to add, but behaviour when Redis is down is a security policy.

Options:
- Option A — In 12A, a Redis backend behind the existing `RateLimitBackend` Protocol. On Redis failure ⟨fail open to the per-process
  limiter / fail closed for login only⟩.
- Option B — Defer to 12B.

Discovery recommendation:
- Option A with fallback to the per-process limiter (login lockout remains DB-backed). Needs sign-off because it is security
  behaviour.

Impact:
- Multi-process API readiness.

Decision classification:
- RECOMMENDATION — REQUIRES SIGN-OFF

Proposed locked wording:
- "Rate limiting uses Redis when configured; if Redis is unavailable the API falls back to its per-process limiter and DB-backed
  lockout continues to apply."

---

### D23

Title: Observability platform (logs, metrics, dashboards, Flower)

Current requirement:
- §22: structured logs with request_id; track background jobs, DB / lab / registry / payment failures and security events.
- Repo: plain-text logging; no metrics stack.

Problem:
- Exporting metrics and logs requires a platform choice.

Options:
- Option A — DB-backed job monitoring (admin page) + structured JSON logs only.
- Option B — Option A + Prometheus / Grafana.
- Option C — Option A + a cloud monitoring service.
- Option D — Option A + Flower (internal network, authenticated).

Discovery recommendation:
- Option A as the baseline (works everywhere). The platform is a business / operations choice. Flower is never public.

Impact:
- Dependencies and deployment.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Job monitoring is DB-backed with structured JSON logs; metrics are exported to ⟨BUSINESS TO SELECT: none / Prometheus / ___⟩; Flower
  ⟨is not used / is internal and authenticated⟩."

---

### D24

Title: Health checks

Current requirement:
- `GET /api/v1/health`: unauthenticated; returns status, database and environment.

Problem:
- Adding Redis / worker detail publicly would leak topology.

Options:
- Option A — `/health/live` (process), `/health/ready` (DB + Redis, minimal body), and an authenticated admin status (workers, beat
  age, queue depth, DEAD count). The existing `/health` is kept for compatibility.
- Option B — Extend the existing public endpoint.

Discovery recommendation:
- Option A.

Impact:
- Load-balancer configuration; E2E.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "Liveness and readiness endpoints expose no internal detail; worker / queue status is available only to job administrators."

---

### D25

Title: Migration `0017_phase12_jobs`

Current requirement:
- Migrations `0001`–`0016`. Each one hand-adds sequences, triggers and a downgrade guard.

Problem:
- The job tables need the same discipline.

Options:
- Option A:
  - tables: `background_jobs` and `background_job_attempts` (append-only);
  - JOB- sequence;
  - filtered unique indexes (idempotency key; one active singleton per periodic type);
  - triggers (attempts append-only, final states frozen, no delete);
  - downgrade guard;
  - optional `worker_heartbeats`;
  - system-actor support per D4;
  - no Phase 1–11 table changes.
- Option B — No migration (Redis only), which conflicts with D3.

Discovery recommendation:
- Option A.

Impact:
- Schema.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "Migration 0017_phase12_jobs adds the job tables, sequence, indexes, triggers and downgrade guard, and changes no Phase 1–11 table
  (except a user-status CHECK if D4 requires it)."

---

### D26

Title: Task payloads and serialization

Current requirement:
- Repo: no bank numbers or tokens in audit; restricted documents.

Problem:
- Broker messages are readable by anyone with Redis access; pickle allows code execution.

Options:
- Option A — JSON only. Payloads carry ids and the job id only, no PII, amounts, secrets or file contents. Optional message signing.
- Option B — Pickle / rich payloads.

Discovery recommendation:
- Option A. Message signing is a sub-choice at implementation.

Impact:
- Security.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "Tasks accept JSON only and carry identifiers only; no personal, financial, secret or file data travels through Redis."

---

### D27

Title: Re-authorization at execution

Current requirement:
- Permissions are checked per request (`Principal`).

Problem:
- Permissions can change between enqueue and execution.

Options:
- Option A — User-requested jobs store `requested_by`. The worker reloads the principal and re-checks the same permission and
  organization scope as the endpoint. A revoked user → FAILED (`PERMISSION_REVOKED`).
- Option B — Trust the enqueue-time check.

Discovery recommendation:
- Option A.

Impact:
- Security.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "A user-requested job re-checks the requester's permission and organization scope when it executes."

---

### D28

Title: Clock source for due checks

Current requirement:
- Repo: `utcnow()` in Python on the API host.

Problem:
- Workers on other hosts may have a skewed clock.

Options:
- Option A — Sweeps select candidates with DB time (`SYSUTCDATETIME()`); hosts are NTP-synchronized; locked re-checks keep Python
  `utcnow()`.
- Option B — Python time everywhere, relying on NTP.

Discovery recommendation:
- Option A.

Impact:
- Small.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "Sweep candidate selection uses database time; all hosts are NTP-synchronized."

---

### D29

Title: Worker database login

Current requirement:
- deployment.md item 3: application login without DDL.

Problem:
- Workers need credentials.

Options:
- Option A — A separate worker login with the same DML rights as the API, no DDL.
- Option B — Share the API login.

Discovery recommendation:
- Option A.

Impact:
- Deployment.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "Workers connect with their own least-privilege SQL login (DML only)."

---

### D30

Title: DEMO / TEST / LIVE isolation for jobs

Current requirement:
- Honest DEMO (Phases 9A–11); TEST adapters never registered; environment on every record.

Problem:
- Jobs must not create DEMO data or use TEST adapters outside tests.

Options:
- Option A:
  - job rows carry `environment`; sweeps act only within their environment;
  - DEMO gets maintenance jobs only (no calculation, provider or financial jobs);
  - TEST adapters are never registered in workers;
  - Redis keys are prefixed per environment.
- Option B — No distinction.

Discovery recommendation:
- Option A.

Impact:
- E2E (DEMO shows an honest empty job list).

Decision classification:
- RECOMMENDATION — REQUIRES SIGN-OFF

Proposed locked wording:
- "Background jobs never create DEMO business data and never use TEST adapters outside the test suite; each environment's jobs act only
  on that environment's records."

---

### D31

Title: Notification delivery channels

Current requirement:
- `notifications.channel` allows EMAIL / SMS / WHATSAPP; only IN_APP is implemented (synchronous, SENT). No provider.

Problem:
- Delivery jobs need a provider, templates and consent rules.

Options:
- Option A — Out of scope until a provider ⟨BUSINESS TO SELECT⟩ is contracted.
- Option B — Build the outbox worker now with no provider (it would never send).

Discovery recommendation:
- Option A.

Impact:
- None in 12A.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Only in-app notifications exist in Phase 12A; email / SMS / WhatsApp delivery is added only with a contracted provider ⟨___⟩."

---

### D32

Title: Antivirus scanning and asynchronous scan

Current requirement:
- §22 "malware scanning adapter". Repo: `SignatureScanner` (EICAR only, `NOT_SCANNED`), synchronous at upload.

Problem:
- A real engine (for example ClamAV) is an infrastructure choice. An async scan needs a quarantine state that changes when documents
  become usable.

Options:
- Option A — 12B: real engine, synchronous scan.
- Option B — 12B: real engine, async scan with quarantine.
- Option C — Defer.

Discovery recommendation:
- Not in 12A. The engine choice is business / operations.

Impact:
- Document availability semantics.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Malware scanning remains synchronous signature-only in 12A; a real engine ⟨BUSINESS TO SELECT⟩ with ⟨sync / async-with-quarantine⟩
  scanning is part of 12B."

---

### D33

Title: Inbound provider events / webhooks

Current requirement:
- Phase 10 D17: no public webhook route; events are deduplicated through `ingest_event` (TEST only).

Problem:
- An event queue without a provider has nothing to process.

Options:
- Option A — No webhook endpoint or event queue in 12A.
- Option B — Build a generic queue now.

Discovery recommendation:
- Option A.

Impact:
- None.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "Phase 12A adds no public webhook endpoint and no inbound event queue; they are added with a contracted provider."

---

### D34

Title: Production deployment platform

Current requirement:
- compose (not exercised); deployment.md checklist; no production environment is defined.

Problem:
- Process supervision, scaling, secrets and log shipping depend on the platform.

Options:
- Option A — Linux containers (compose / orchestrator) ⟨BUSINESS TO SELECT⟩.
- Option B — VMs with systemd.
- Option C — Windows Server services. Celery workers are not supported on Windows for production.

Discovery recommendation:
- None. Workers should run on Linux.

Impact:
- Deployment documentation and the worker / beat process model.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Production runs on ⟨BUSINESS TO SELECT⟩; Celery workers and the single beat run on Linux."

---

### D35

Title: API access-log writes

Current requirement:
- Repo: each API request writes `api_access_logs` in its own transaction via the threadpool (`audit/access_log.py`).

Problem:
- Possible candidate for async buffering. But losing access-log rows (if Redis is down) weakens security forensics.

Options:
- Option A — Keep synchronous.
- Option B — Queue through Redis / Celery.

Discovery recommendation:
- Option A.

Impact:
- None.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "API access logs stay synchronous (own short transaction) in Phase 12A."

---

### D36

Title: Phase 12A boundary

Current requirement:
- This discovery, section AL.

Problem:
- Prevent scope creep into financial automation or 12B items.

Options:
- Option A — As listed in discovery section AL.

Discovery recommendation:
- Option A.

Impact:
- Scope only.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "Phase 12A does not implement:
  - automatic financial transitions;
  - scheduled settlement (unless D11);
  - provider integrations or webhooks;
  - email / SMS delivery;
  - a real antivirus engine;
  - an S3 adapter;
  - changes to Phase 1–11 business rules;
  - microservices;
  - cloud-specific deployment."

---

## Contradictions C1–C9

| C | Contradiction | Source A | Source B | Why it matters | Discovery recommendation | Approval? | Proposed resolution wording |
|---|---|---|---|---|---|---|---|
| C1 | Phase 12 scope | §22 production hardening (broad) | request: jobs | size / risk | split 12A / 12B (D1) | **Yes** | "Phase 12 = 12A jobs + 12B hardening." |
| C2 | "No worker" | Phase 9B D4, Phase 10 D5 | scheduled sweeps | wording of locked decisions | lazy stays; sweeps added (D5) | **Yes** | "Lazy expiry plus scheduled sweeps." |
| C3 | "Query once, no job" | Phase 9A, Phase 10 D35 | §22 async integrations | provider behaviour | polling only for non-MANUAL adapters, disabled in LIVE (D12) | **Yes** | "Polling per D12." |
| C4 | Synchronous with guards | Phase 7 A18, 8A B11 | §12 "Use Celery for long calculations" | UX and BLOCKED runs | async above the guards (D8, D9) | **Yes** | "Async above the guards." |
| C5 | Long calculations | §12 | no production module registered | no real workload | build the mechanism; no fake module | No (technical) | "The calculation job exists; no module is invented." |
| C6 | Compose vs machine | compose redis, no worker / beat, not exercised | no Docker locally | local feasibility | D18, D34 | **Yes** | "Per D18 / D34." |
| C7 | Ledger actor NOT NULL | 9B schema | system actions | audit attribution | system actor (D4) | **Yes** | "SYSTEM actor per D4." |
| C8 | Public health endpoint | returns environment | worker / Redis detail | information disclosure | split endpoints (D24) | No (technical) | "Per D24." |
| C9 | Settlement cycle | Phase 11 decision lock ("Scheduled runs are Phase 12") | financial controls | automation of money | manual unless D11 selects | **Yes** | "Per D11." |

---

## Proposed job model (candidate — not approved)

- `background_jobs`:
  - `job_code` (JOB-), `job_type`, `queue`, `status` (QUEUED / DISPATCHED / RUNNING / SUCCEEDED / SKIPPED / FAILED / RETRY_SCHEDULED /
    DEAD / CANCELLED);
  - `environment`, `organization_id?`, `requested_by?`, `idempotency_key` (filtered unique);
  - `payload` (JSON ids), `result` (JSON counts);
  - `attempt`, `max_attempts`, `next_attempt_at`, `lease_owner`, `lease_until`;
  - `celery_task_id`, `correlation_request_id`, `last_error_code`, `last_error_message`;
  - timestamps.
- `background_job_attempts` (append-only).
- State machine `background_job` (discovery §K). Final states frozen by trigger.

## Proposed queues (candidate)

`maintenance`, `calculation`, `reports`; later `integration`, `notifications`. No `finance` queue.

## Proposed permissions (candidate)

`jobs.read`, `jobs.manage` → Platform Administrator only (D16). The system actor holds no permission (D4).

---

## DECISION SUMMARY

| ID | Decision | Classification | Recommendation | Human sign-off required |
|----|----------|----------------|----------------|-------------------------|
| D1 | Phase 12 scope | RECOMMENDATION — REQUIRES SIGN-OFF | split 12A / 12B | Yes |
| D2 | Job framework | TECHNICAL DECISION | Celery 5.x + Redis (§2 / §3) | No (technical review) |
| D3 | Job system of record / outbox | TECHNICAL DECISION | SQL Server tables + outbox; Redis transport only | No (technical review) |
| D4 | System actor | RECOMMENDATION — REQUIRES SIGN-OFF | non-login SYSTEM user, no permissions | Yes |
| D5 | Initial workloads; amend "no worker" | RECOMMENDATION — REQUIRES SIGN-OFF | sweeps + housekeeping; lazy expiry stays | Yes |
| D6 | Reservations of orders with a reported payment | BUSINESS DECISION REQUIRED | none (A keeps Phase 10) | Yes |
| D7 | Sweep intervals | BUSINESS DECISION REQUIRED | configurable; order → listing → reservation | Yes |
| D8 | Async calculation | RECOMMENDATION — REQUIRES SIGN-OFF | async above the input guard | Yes |
| D9 | Async report | RECOMMENDATION — REQUIRES SIGN-OFF | async above the row guard | Yes |
| D10 | Retention / orphan grace | BUSINESS DECISION REQUIRED | per category; disabled until set | Yes |
| D11 | Scheduled settlement | BUSINESS DECISION REQUIRED | none in 12A | Yes |
| D12 | Provider polling | RECOMMENDATION — REQUIRES SIGN-OFF | non-MANUAL only; disabled in LIVE | Yes |
| D13 | No financial transitions in workers | RECOMMENDATION — REQUIRES SIGN-OFF | explicit allow-list + introspection test | Yes |
| D14 | Retry policy | TECHNICAL DECISION | transient only; backoff + jitter; configurable | No (technical review) |
| D15 | Dead jobs: alerting / ownership | BUSINESS DECISION REQUIRED | alert ⟨recipients⟩; manual audited retry | Yes |
| D16 | Job permissions / admin UI | RECOMMENDATION — REQUIRES SIGN-OFF | jobs.read / jobs.manage → Platform Admin | Yes |
| D17 | Redis hosting / HA | BUSINESS DECISION REQUIRED | auth + TLS + noeviction in every option | Yes |
| D18 | Local Redis / worker environment | BUSINESS DECISION REQUIRED | none (machine-dependent) | Yes |
| D19 | Test strategy | TECHNICAL DECISION | direct + eager + snapshot races + broker tests where available | No (technical review) |
| D20 | Beat schedule / singleton | TECHNICAL DECISION | static schedule; one beat; slot keys | No (technical review) |
| D21 | Locking | TECHNICAL DECISION | SQL Server authoritative | No (technical review) |
| D22 | Redis rate limiter + failure policy | RECOMMENDATION — REQUIRES SIGN-OFF | Redis with per-process fallback | Yes |
| D23 | Observability platform | BUSINESS DECISION REQUIRED | DB-backed + JSON logs baseline | Yes |
| D24 | Health checks | TECHNICAL DECISION | live / ready / admin split | No (technical review) |
| D25 | Migration 0017 | TECHNICAL DECISION | job tables + triggers + guard | No (technical review) |
| D26 | Payload / serializer | TECHNICAL DECISION | JSON, ids only | No (technical review) |
| D27 | Re-authorization at execution | TECHNICAL DECISION | reload principal, re-check scope | No (technical review) |
| D28 | Clock source | TECHNICAL DECISION | DB time for candidate selection; NTP | No (technical review) |
| D29 | Worker DB login | TECHNICAL DECISION | separate least-privilege login | No (technical review) |
| D30 | DEMO / TEST / LIVE | RECOMMENDATION — REQUIRES SIGN-OFF | maintenance only in DEMO; no TEST adapters | Yes |
| D31 | Notification channels | BUSINESS DECISION REQUIRED | out of scope until a provider | Yes |
| D32 | Antivirus / async scan | BUSINESS DECISION REQUIRED | 12B; engine to select | Yes |
| D33 | Webhooks / event queue | TECHNICAL DECISION | none in 12A | No (technical review) |
| D34 | Deployment platform | BUSINESS DECISION REQUIRED | Linux workers; platform to select | Yes |
| D35 | Access-log writes | TECHNICAL DECISION | stay synchronous | No (technical review) |
| D36 | Phase 12A boundary | TECHNICAL DECISION | discovery §AL | No (technical review) |

Totals: 36 decisions — 11 BUSINESS DECISION REQUIRED, 10 RECOMMENDATION — REQUIRES SIGN-OFF, 15 TECHNICAL DECISION; 21 require human
sign-off; 9 contradictions (C1–C9; 7 require approval).

## IMPLEMENTATION BLOCKERS

These must be resolved before Phase 12A coding can begin safely:

- **D1:** scope (12A / 12B split).
- **D4:** system actor (schema / seed and audit attribution).
- **D6:** reservation expiry for reported payments (sweep behaviour).
- **D13:** the financial-safety allow-list.
- **D18:** a usable local Redis / worker setup (or an explicit eager-only decision). Disk space on the development machine must also be
  confirmed.
- **D7, D10:** needed before the corresponding sweeps or purges are *enabled*. The mechanisms can be built and left disabled.

## SAFE TO IMPLEMENT AFTER LOCK

- D2, D3, D14, D19, D20, D21, D24, D25, D26, D27, D28, D29, D33, D35, D36 (technical), once D1 is signed off.
- After sign-off: D5 workloads, D8 / D9 (if accepted), D12 (disabled mechanism), D16 permissions, D22 limiter, D30 isolation.

## PHASE 12A IMPLEMENTATION ORDER (proposed sequence only — not started)

1. Dependencies + configuration + production guards
2. Migration `0017_phase12_jobs` + system actor
3. Job framework (model, state machine, outbox, claim / lease, retry, attempts)
4. Celery app, queues, worker init, beat with slot idempotency
5. Housekeeping tasks (dispatch_pending, recover_stuck)
6. Expiry sweeps (orders → listings → reservations), orphan sweep
7. Calculation / report jobs (if D8 / D9); retention (if D10)
8. Job admin API, permissions, health endpoints
9. Frontend: Background jobs page; queued status for calculation / report
10. Tests (direct, eager, snapshot concurrency, financial-safety introspection, broker integration where available)
11. E2E, documentation, compose worker / beat services

None of these steps is implemented by this document.

---

## LOCK RECORD — Phase 12A implementation prompt (2026-10-03)

The Phase 12A implementation prompt locked the decisions below. Wording outside this section is the original discovery proposal and is
kept for traceability.

| ID | Locked outcome |
|---|---|
| D1 | Split. **12A** = background job infrastructure + safe scheduled operational work. **12B** = remaining hardening (not implemented). |
| D2 | Celery 5.x + Redis broker (pinned: `celery[redis]==5.6.3`, `redis==6.4.0`). |
| D3 | SQL Server is the system of record. Transactional enqueue; publication after commit; recovery republishes. Redis is transport only. |
| D4 | One non-login SYSTEM actor per environment (status `SYSTEM`, no role, no permission, hidden). It is used by background jobs; lazy expiry keeps its existing attribution. |
| D5 | Scheduled expiry sweeps (reservations; orders + listings), orphan-file scan (detection only), retention-purge infrastructure. Lazy expiry remains. |
| D6 | **Option A**: a reported payment does not stop reservation expiry (Phase 10 behaviour). A late confirmation goes to the existing ATTENTION_REQUIRED workflow. |
| D7 | Conservative operational defaults: expiry every 600 s, orphan scan and retention daily (configurable). |
| D8 / D9 | Not moved: calculation / report execution stays synchronous. The framework can host them later. |
| D10 | No retention period is invented. The purge infrastructure purges nothing; job history is kept. |
| D11 | No scheduled settlement (or any financial job). |
| D12 | No provider polling. |
| D13 | No financial or approval transition in any worker (enforced by the registry allow-list and tests). |
| D14 | Explicit classification. Bounded retries of transient failures with deterministic exponential backoff (no jitter); business errors fail at once. |
| D15 | DEAD / FAILED jobs are visible in Administration → Background jobs, with audited requeue / cancel. No alert channel was selected (12B). |
| D16 | `jobs.read` / `jobs.manage` granted to the Platform Administrator. No new role. |
| D17 | Production Redis hosting not selected (12B / operations). Local compose binds Redis to 127.0.0.1 with AOF + noeviction. |
| D18 | No Docker / WSL on the development machine. API, unit tests and E2E run without Redis. WSL2 / Docker setup is documented. The broker integration test uses a real Redis (`REDIS_TEST_URL`) or the test-only `fakeredis` TCP server. |
| D19 | Direct + snapshot-concurrency + real-worker (Redis protocol) tests. Eager mode is not used. |
| D20 | Static beat schedule; one beat; per-slot idempotency keys. |
| D21 | SQL Server locks are authoritative; no Redis lock is used. |
| D22 | Not in 12A: the rate limiter stays in-memory (12B). |
| D23 | No monitoring platform. Structured JSON job logs + DB-backed status only. |
| D24 | Authenticated `/jobs/status` (database, broker, worker heartbeat, counts). The public `/health` is unchanged. |
| D25 | Migration `0017_phase12_background_jobs`. |
| D26 | JSON only; payloads are identifiers only (allow-listed keys; none for 12A tasks). |
| D27 | Operator actions are checked at request time. 12A has no user-requested asynchronous business job. |
| D28 | Python `utcnow()` (as lazy expiry), so sweep and lazy semantics are identical. |
| D29 | Documented (12B / deployment). |
| D30 | Environment on every job; mismatch rejected; DEMO honest; TEST adapters never registered. |
| D31 / D32 / D33 | Not implemented (no notification provider, no antivirus, no webhooks). |
| D34 | Not selected (12B). Production workers run on Linux. |
| D35 | Access logs stay synchronous. |
| D36 | Boundary as in discovery §AL and the prompt's "DO NOT IMPLEMENT" list. |
