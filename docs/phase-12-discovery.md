# Phase 12 — Background jobs, Celery and Redis: discovery and design

> **Discovery only.** No application code, migration, schema, dependency, configuration or database was created or changed. Two
> documents were added: this report and [phase-12-decision-lock.md](phase-12-decision-lock.md).
> Baseline: commit `6312792` (`phase-11-revenue-payouts`). The working tree was clean and both databases are at migration `0016`.

Tags used throughout:

- **[REPO]**: verified in the repository (file and line references given).
- **[SPEC]**: stated in the master specification (`§n`).
- **[ASSUMPTION]**: inferred as technically necessary. It can be challenged but needs no business rule.
- **[OPEN DECISION]**: not defined anywhere; locked in the decision lock (`Dn`).

---

## 1. Executive summary

1. **Scope differs between the spec and the request.**
   - The specification's Phase 12 is *production hardening* (§22). It covers security review, object storage (MinIO / S3), a malware
     scanning adapter, structured logs, deadlock handling, backup / restore tests, performance, and background workers.
   - The request narrows Phase 12 to Celery / Redis / background jobs.
   - I recommend splitting it the way Phases 8 and 9 were split:
     - **12A**: job infrastructure and the workloads below;
     - **12B**: the rest of §22 hardening.

   This needs sign-off (D1).

2. **The repository is fully synchronous, by explicit and repeated decisions.** [REPO] These choices were made deliberately, with
   correctness safeguards:
   - lazy expiry, with no worker: Phase 9B D4 and Phase 10 D5;
   - provider status "queried once on request — no job, no automatic retry": Phase 9A and Phase 10 D35;
   - synchronous calculation with an input-size guard: Phase 7 A18;
   - synchronous report generation with a size guard: Phase 8A B11;
   - "no workers or schedulers": Phase 11 D42.

   Phase 12 should **add promptness, not change correctness**. Every lazy check stays in place, and jobs only run the same idempotent
   service functions earlier.

3. **The project is already worker-ready in several ways.** [REPO]
   - Services take an explicit `RequestContext` and own their commits.
   - `ledger_service.run()` gives one transaction per attempt with deadlock retry.
   - Row locks use `UPDLOCK, HOLDLOCK, ROWLOCK`, and Read Committed Snapshot Isolation (RCSI) is on.
   - State machines with transition audit are already in place (47 machines).
   - Idempotency-Key replay is everywhere.
   - Provider calls already use the outbox pattern: the row and its key are committed before the external call.
   - `RequestContext.system()` exists.
   - `app/workers/` exists but is empty. `REDIS_URL` is configured but unused. `docker-compose.yml` has a `redis` service but no worker
     or beat service.

4. **Few workloads truly need background execution today.**
   - The real candidates are:
     - expiry sweeps (reservations, orders, listings);
     - the document-orphan sweep;
     - retention purges, once retention periods are decided;
     - optionally, calculation execution and calculation report generation above the size guards.
   - Two items look like job workloads but should not be built yet:
     - **Provider polling and webhooks:** no LIVE payment, payout or registry provider is contracted, so the only "jobs" there would
       exercise the TEST adapters.
     - **Long calculations:** no production calculation module is registered (Phase 7), so no real long calculation exists yet.

5. **Financial safety.**
   - No approval, separation-of-duties step, payout execution, payment confirmation, refund, reconciliation or revenue recognition is
     moved to a worker.
   - Revenue recognition must stay **inside** the delivery transaction. Making it asynchronous would create an unrecognized-revenue
     window and a second recognition path.
   - Jobs may only perform *system-owned* transitions, such as a deadline passing.

6. **Three findings need decisions before coding.**
   - **System actor.** `credit_ledger_entries.actor_id` is NOT NULL, and expiry today falls back to `ctx.user_id or r.created_by`
     (`order_service.py:214`, `ledger_service.py:331`). A scheduled sweep would therefore record the reservation's creator as the
     actor. Today, lazy expiry records whoever triggered the read, which can be a user of another organization. A system actor is
     needed (D4).
   - **Reservation-expiry policy.** A buyer who reported a payment (PENDING_CONFIRMATION) keeps the order, but the order's 9B
     reservations still expire (`order_service.py:202-203`). A sweep makes this happen without anyone visiting, which raises a
     business question (D6).
   - **Local environment.** The development machine has no Docker. The only Redis on disk is your own archived Windows port 3.0.504
     (2016, unmaintained), which is not running. Celery no longer supports Windows workers officially, and about 300 MB of disk is free.
     A local Redis and worker strategy must be chosen (D18).

7. **Counts:** 36 decisions (D1–D36), 9 contradictions (C1–C9). Proposed migration: **`0017_phase12_jobs`**.

---

## 2. Repository inspection (the 12 areas)

| # | Area | Findings [REPO] |
|---|---|---|
| 1 | FastAPI architecture | Modular monolith (`app/main.py`, `create_app()`). Sync route handlers run in Starlette's threadpool. Routers under `/api/v1` (`api/v1/router.py`, 31 modules). Middleware: request id (`X-Request-ID`), secure headers, body-size limit, global per-IP rate limit, API access log (`core/middleware.py`). Error envelope `{success, error_code, message, details, request_id}`. Plain-text `logging.basicConfig` (not structured). |
| 2 | Service patterns | Thin routers → services that take `(db, ctx, principal, …)` and own `commit()`. Mappers are explicit allow-lists. Composable `*_in_tx` functions for cross-module transactions (9B → 10 → 11). Adapters are injected only by tests. |
| 3 | Transactions | `get_db` is request-scoped and always rolls back at the end; services commit. `ledger_service.run(db, ctx, op)` runs one transaction per attempt and retries deadlock victims 3 times. Sessions use `autoflush=False, expire_on_commit=False` (`core/database.py`). RCSI is on. Engine `pool_size=10, max_overflow=20, pool_pre_ping=True`. |
| 4 | Audit | `audit.service.record()` adds the `audit_logs` row to the caller's session, so it commits atomically with the change. `ls.audit()` writes the two-organization pattern. `workflow_events`, `security_events`, `login_audit`, and `api_access_logs` (its own short transaction, via the threadpool, after every API request). Audit tables are append-only (triggers). `AuditLog.user_id` and `request_id` are nullable. |
| 5 | State machines | `core/state_machine.py` + `services/workflows.py`: 47 `StateMachine.build(...)` machines. Transitions are audited as workflow events. Final states are additionally frozen by DB triggers (Phases 6–11). |
| 6 | Concurrency / locking | Pessimistic row locks (`WITH (UPDLOCK, HOLDLOCK, ROWLOCK)`, `ms.lock`, `ls.lock_*`). Fixed lock order: order → payment → reservation / transfer → positions (Phase 10 D26). Filtered unique indexes as the last line of defence (one recognition per item, one ACTIVE settlement claim, one open payout per run and farmer). Real cross-connection race tests on SQL Server database snapshots (9B, 10, 11). |
| 7 | Database / Alembic | SQL Server 2022, `mssql+pyodbc`, migrations `0001`–`0016`. Every migration hand-adds sequences, triggers and a downgrade guard. `alembic check` is part of the exit gate. Test DB `carbon_platform_test`. |
| 8 | Phase 11 synchronous financials | Revenue recognition / reversal inside the Phase 10 delivery / refund transactions. Settlement calculation locks the project and claims inputs. Payout lifecycle: approve, initiate (bank re-check under lock), confirm-paid, reconcile — each a single user-driven transaction. `query_status` / `_provider_outcome` exist only for non-MANUAL adapters (TEST). No scheduler. |
| 9 | Adapter patterns | Protocol + `MANUAL` implementation that raises `ManualActionRequired` (payment, payout, registry); `NoLimsAdapter`; `SignatureScanner` (EICAR only, `NOT_SCANNED` otherwise); `LocalFileStorage` (S3 "planned for Phase 12"). Outbox: the row and key are committed before the external call; a timeout gives UNCONFIRMED, never an automatic retry (`payment_service.py:134-170`, `registry_service.py:9`). |
| 10 | Authentication / RBAC | JWT access token (15 min) + hashed refresh tokens + `sessions` table. Lockout. **In-memory** login and global rate limiter (`core/rate_limit.py`: "Redis backend required before running multiple API workers"). `Principal` grants per organization (`can_in_org`). 404 outside scope / 403 when visible. Separation of duties enforced in services and DB checks. |
| 11 | Frontend / API behaviour | Angular 21 (zoneless, signals). Every mutation is a synchronous HTTP call with an `Idempotency-Key`. The only polling is the notification unread count every 60 s (`layout/shell.ts:53`). No job / progress UI exists. |
| 12 | Configuration | `pydantic-settings` (`core/config.py`), `backend/.env` (never committed), production guards (secure cookie, distinct secrets, no local storage in production). `REDIS_URL`, `OBJECT_STORAGE_*` are defined but unused. `.env.example` mirrors them. `docker-compose.yml`: sqlserver, redis (7-alpine, no auth / persistence settings), minio, backend, frontend — "not exercised on the dev machine". |

Other relevant facts [REPO]:
- `requirements/base.txt` has no Celery, redis or kombu.
- Python 3.10.0 in `.venv`.
- `notifications` rows have `channel IN (IN_APP, EMAIL, SMS, WHATSAPP)`, `status IN (PENDING, SENT, FAILED)` and `retry_count`, but
  only IN_APP is written, synchronously, as SENT.
- `document_service.py:8` says "an orphan-sweep job is planned with the Celery workers (Phase 12)".
- `POST /credits/reservations/expire-due` is a manual sweep endpoint.

---

## A. Why Phase 12 is needed

- **[SPEC]** The specification requires it:
  - §2 / §3 put "Background jobs: Celery, Redis" in the target architecture;
  - §12 says "Use Celery for long calculations";
  - §22 lists "background workers", "async integrations" and tracking of "background jobs";
  - §40 tests a "calculation background job".
- **Deadlines without traffic.** [REPO] Reservations, unpaid orders and listings expire only when someone reads or writes near them.
  Expired state is enforced correctly, but it is *reported* late (inventory looks reserved, an order looks open), and the expiry is
  attributed to whoever happened to trigger it.
- **Size guards.** [REPO] Calculations above `CALCULATION_MAX_INPUT_ROWS` are BLOCKED, and reports above `CALCULATION_REPORT_MAX_ROWS`
  are refused. Without background execution these workloads cannot complete at all.
- **Housekeeping debt.** [REPO] There is no sweep of orphaned stored files, expired sessions / refresh tokens, or old `api_access_logs`
  (deployment.md item 8 asks for a retention policy).
- **Scale-out.** [REPO] The rate limiter and lockout counters are per-process. Running more than one API process (deployment.md item 6)
  needs a shared store, which is Redis per §2.
- **Future integrations.** A contracted payment, payout, registry or LIMS provider needs status polling and inbound event processing.
  Phase 12 should provide the mechanism; it should not invent a provider.

## B. Workloads that should become background jobs

| # | Workload | Today [REPO] | Proposed job | Why safe | Decision |
|---|---|---|---|---|---|
| B1 | Reservation expiry (9B) | lazy + `POST /credits/reservations/expire-due` | periodic `maintenance.expire_reservations`: calls `ledger_service.expire_due` per batch, chunked | each item re-checked under `UPDLOCK`, one `run()` per reservation, idempotent | D4, D6, D7 |
| B2 | Unpaid order expiry (10) | lazy (`order_service.expire_if_due`) | periodic `maintenance.expire_orders`: iterates PLACED orders past `expires_at`, calls `expire_if_due` | locks order → reservations (D26 order); re-checks `_holds` | D4, D7 |
| B3 | Listing expiry (10) | lazy (`expire_listing_if_due`) | periodic `maintenance.expire_listings` | locked re-check | D4, D7 |
| B4 | Document orphan sweep | none (comment in `document_service.py:8`) | periodic `maintenance.sweep_orphan_files`: storage keys older than a grace period with no `document_versions` row → quarantine / delete | never touches referenced files; grace period protects in-flight uploads | D10, D32 |
| B5 | Retention purges | none | periodic `maintenance.purge_*` for `api_access_logs`, expired `sessions` / `refresh_tokens`, read notifications, finished job rows | append-only audit tables are **never** purged | D10 |
| B6 | Calculation execution above the input guard (7) | sync; BLOCKED `INPUT_TOO_LARGE` | `calculation.execute_run` (user-requested, re-authorized at execution) | run state machine + frozen inputs; execution re-checks state under lock | D8 |
| B7 | Calculation report generation above the row guard (8A) | sync; refused `REPORT_TOO_LARGE` | `reports.generate_calculation_report` | report content hash; current report replaced only by the defined workflow | D9 |
| B8 | Provider status polling (payments UNCONFIRMED / PENDING, payouts UNCONFIRMED / PAYMENT_PENDING, registry SUBMISSION_UNCONFIRMED) | manual "query once" endpoints; TEST adapters only | `integration.poll_*` **only for non-MANUAL adapters** | a MANUAL adapter is never polled; the result only moves states the provider owns | D12 |
| B9 | Notification delivery for non-IN_APP channels | not implemented | `notifications.deliver` (outbox on `notifications` PENDING / FAILED + `retry_count`) | no provider → out of scope | D31 |
| B10 | Asynchronous malware scan (real AV) | sync signature hook | `documents.scan_version` with a quarantine state | changes document availability | D32 |
| B11 | Job housekeeping | — | `jobs.recover_stuck` (expired leases), `jobs.dispatch_pending` (outbox re-publish) | DB-driven, idempotent | D3, D20 |

Not proposed as jobs (sections C, S): settlement calculation, payout lifecycle steps, reconciliation, revenue recognition / reversal,
refunds, ledger movements, approvals, document upload validation, PDF generation within the size guards, sampling-point generation,
GIS area computation.

## C. Operations that must remain synchronous

| Operation | Why it stays synchronous |
|---|---|
| Authentication, token refresh, lockout, permission checks | user-facing security decisions |
| Every approval / second-person step (configuration, costs, settlement approve, payout approve, listing approve, KYC, calculation QA / approve, VVB decision recording, issuance confirmation) | separation of duties is evaluated on the acting **person**; a worker is not a person |
| Ledger movements: open, reserve, transfer request / complete / close, retirement, reversal | lock order + conservation inside one transaction; the user needs the result (`INSUFFICIENT_AVAILABLE`) immediately |
| Order placement (T1), payment recording (T2), payment confirmation (T3), order-linked delivery (T4) | all-or-nothing with 9B reservations; immediate outcome |
| **Revenue recognition / reversal** | must stay inside the T4 / refund transaction (Phase 11 D8 / D10); async would open a window with delivered-but-unrecognized revenue and a second code path |
| Settlement calculate / submit / approve / reject / cancel; payout calculate / submit / approve / initiate / confirm-paid / fail / reissue / release-hold; reconciliation; recovery-case closing | human-driven financial controls; bank re-check under lock at initiate; SoD per person |
| Refund request / approve / complete | dual control; reversal written in the same transaction |
| Document upload validation (type sniffing, size, PDF-only, EICAR) and storage | the user must know the upload was rejected |
| Audit / workflow writes | atomic with the business change |
| Idempotent replays, lineage, verify (`/settlements/{id}/verify`) | read paths |
| Calculation execution and report generation **below** the guards | already bounded; keep the immediate result (D8, D9) |

## D. Celery architecture

**[ASSUMPTION]**, pending D2 / D3.

- **One Celery application** in `app/workers/celery_app.py`, with tasks in `app/workers/tasks/*.py`. Tasks are thin. Each task:
  1. loads its job row;
  2. claims it (section I);
  3. builds a `RequestContext`;
  4. calls the **existing service function**;
  5. finalizes the job row.

  No business logic lives in tasks (the modular monolith stays, per §2).
- **The database is the system of record** for job state (`background_jobs`); Redis is transport only.
  - Results backend: disabled (`task_ignore_result=True`). Outcomes are written to the DB job row.
  - Serializer: `json` only. `accept_content=["json"]`; never pickle.
  - `task_acks_late=True` and `task_reject_on_worker_lost=True`: a crash re-delivers, and the DB claim makes re-delivery harmless.
  - `worker_prefetch_multiplier=1` for long queues.
  - `broker_transport_options.visibility_timeout` must exceed the longest task time limit. Otherwise Redis re-delivers a running
    task, which the DB lease also guards against.
  - `task_time_limit` / `task_soft_time_limit` per queue.
- **Transactional outbox for enqueueing.** A business transaction that needs a job inserts the `background_jobs` row in the **same**
  transaction. After commit it publishes to Celery. If publishing fails (Redis down), the row stays QUEUED and `jobs.dispatch_pending`
  (beat) re-publishes it. Without this, a rolled-back transaction could publish a phantom task, or a committed transaction could lose
  its task.
- **Beat** (`celery beat`) runs the periodic schedule: exactly one beat process (section L).

## E. Redis architecture

**[ASSUMPTION]**, pending D17 / D22.

- **Redis ≥ 7** (compose already pins `redis:7-alpine`). The Windows 3.0.504 port is not suitable.
- **Logical separation:**
  - DB 0: Celery broker;
  - DB 1: rate limiter and lockout counters (12B / D22);
  - DB 2: short-lived locks (beat singleton only).

  Keys are prefixed with the environment (`live:`, `demo:`, `test:`).
- **Broker durability:** AOF `appendfsync everysec`, `maxmemory-policy noeviction`. Eviction would silently drop queued tasks; the DB
  outbox would recover them, but noeviction keeps Redis honest.
- **Security:** a password / ACL user per client role, TLS (`rediss://`) outside localhost, no public port (compose currently publishes
  `6379:6379`), `protected-mode` on, dangerous commands disabled (`FLUSHALL`, `CONFIG`) for application users.
- **No business data in Redis.** Messages carry job ids only (section Q). Losing Redis loses no financial state.

## F. Worker architecture

- **Worker pools by queue** (section G). Prefork pool on Linux. On Windows development, `--pool=solo` or `threads` (Celery does not
  support Windows prefork officially; D18).
- **One engine per worker process.** Call `get_engine().dispose()` on `worker_process_init`; SQLAlchemy pools are not fork-safe. Use
  the same `get_session_factory()` and a new `Session` per task. Never use the request-scoped `get_db`.
- **Settings:** the same `Settings` class (worker and API share `.env`), plus worker-only settings (section AG).
- **Graceful shutdown:** `SIGTERM` → warm shutdown, finishing the current task within the soft limit; `acks_late` re-delivers anything
  cut off.
- **No worker calls the HTTP API.** Workers call services directly with an explicit context (as the tests do).

## G. Queue design

| Queue | Tasks | Concurrency guidance | Time limit |
|---|---|---|---|
| `maintenance` | B1–B5, B11 | low (1–2); must not starve the database | short (minutes) |
| `calculation` | B6 | 1 per worker host (CPU and memory heavy) | long; set from D8 |
| `reports` | B7 | 1–2 | medium |
| `integration` | B8 (only once a provider exists) | low; per-provider rate limits | short; provider timeout + margin |
| `notifications` | B9 (only once a channel provider exists) | low | short |

- Routing: `task_routes` by task-name prefix.
- **No `finance` queue.** No financial transition is executed by a worker (section S). Provider polling for payouts, if ever enabled,
  goes through `integration` and can only record provider-owned outcomes.

## H. Retry strategy

- **Retry only transient failures:**
  - DB connection loss;
  - deadlock victims that remain after `ls.run`'s own 3 attempts;
  - lock timeouts;
  - Redis / broker errors on publish;
  - provider timeouts **only** for read-only status queries.
- **Never retry business outcomes.** `AppError` subclasses (`Conflict`, `ValidationFailed`, `PermissionDenied`, `NotFound`,
  `InvalidTransition`) finish the job as FAILED (non-retryable), or SKIPPED when the precondition simply no longer holds (for example,
  the order was paid).
- **Never automatically retry a non-idempotent external call.** This keeps the Phase 9A / 10 / 11 rule: a timeout on create-payment,
  create-payout or registry-submit leaves UNCONFIRMED and is resolved by a status query.
- **Backoff:** exponential with full jitter, capped. `max_attempts` per job type comes from configuration. The values are engineering
  defaults, not business rules (D14).
- **Each attempt is recorded** in `background_job_attempts` (append-only) with a sanitized error class / code. No stack traces with
  data go to users.

## I. Idempotency strategy

Three layers:

1. **Enqueue idempotency.** `background_jobs.idempotency_key` has a filtered unique index.
   - User-requested jobs reuse the request's `Idempotency-Key`.
   - Periodic jobs use `"<job_type>:<schedule-slot>"`, for example `expire_reservations:2026-10-03T10:05Z`, so a duplicate beat or a
     re-publish cannot create a second job.
2. **Execution claim.** A worker claims a job with one `UPDATE background_jobs SET status='RUNNING', lease_owner=…, lease_until=…,
   attempt=attempt+1 WHERE id=… AND status IN ('QUEUED','RETRY_SCHEDULED') [OR lease expired]`. Zero rows updated means another worker
   owns it, so the task exits.
3. **Business idempotency.** This already exists:
   - every target service re-checks state under a row lock (`expire_due`, `expire_if_due`, `expire_listing_if_due`, calculation
     `execute`, `_provider_outcome`);
   - the unique indexes are the last line of defence.

   A task that runs twice therefore produces at most one state change.

## J. Dead-letter / permanently failed jobs

- After `max_attempts`, or on a non-retryable error, the job becomes **DEAD** (retries exhausted) or **FAILED** (business refusal).
- No Redis dead-letter queue is needed: the DB row *is* the dead-letter record, together with its attempt history.
- **Alerting (D15):** a `security_events`-style operational event or an in-app notification to the platform role selected in D15.
- **Manual retry:** a person with the D16 permission creates a **new attempt** on the same job row.
  - The retry is audited.
  - All preconditions are re-checked.
  - It is never automatic.
- **Cancel:** a QUEUED or RETRY_SCHEDULED job can be CANCELLED, with a reason and audit.
- Dead jobs are never auto-deleted before the D10 retention period.

## K. Job state machine

```
QUEUED ──dispatch──▶ DISPATCHED ──claim──▶ RUNNING ──▶ SUCCEEDED
   ▲                                          │ ├──▶ SKIPPED   (precondition no longer holds; nothing to do)
   │                                          │ ├──▶ FAILED    (non-retryable business / authorization outcome)
   │                                          │ └──▶ RETRY_SCHEDULED ──(next_attempt_at)──▶ DISPATCHED
   │                                          └──(lease expired: worker lost)──▶ RETRY_SCHEDULED | DEAD
   └── QUEUED / RETRY_SCHEDULED ──▶ CANCELLED          RETRY_SCHEDULED ──(max attempts)──▶ DEAD
                                                      DEAD ──(manual retry, audited)──▶ QUEUED
```

- Final states: SUCCEEDED, SKIPPED, FAILED, CANCELLED. DEAD is final unless manually retried.
- Implemented as a `StateMachine.build("background_job", …)` like the other 47 machines.
- A DB trigger freezes final rows and keeps attempts append-only.

## L. Scheduled jobs / periodic tasks

| Schedule | Task | Interval | Notes |
|---|---|---|---|
| reservation / order / listing expiry | B1–B3 | ⟨D7⟩ | orders first (D26 lock order: order → reservation), then listings, then remaining non-order reservations |
| outbox re-dispatch | B11 `jobs.dispatch_pending` | ⟨D14 technical⟩ | republishes QUEUED rows older than a grace period |
| stuck-lease recovery | B11 `jobs.recover_stuck` | ⟨D14⟩ | RUNNING with `lease_until < now` → RETRY_SCHEDULED / DEAD |
| orphan file sweep | B4 | ⟨D10⟩ | grace period ⟨D10⟩ |
| retention purges | B5 | ⟨D10⟩ | only categories with a decided retention period |
| provider polling | B8 | ⟨D12⟩ | disabled unless a non-MANUAL adapter is configured |

- **Beat singleton:** exactly one beat process per environment (deployment), plus slot-keyed idempotency (section I), so an
  accidental second beat creates no duplicate work.
- **Schedule storage:** static configuration in code and environment, not editable from the UI (D20).
- **No scheduled settlement, payout or reconciliation** unless D11 selects it.

## M. Concurrency and distributed locking

- **Correctness locks stay in SQL Server.** The existing row locks, lock order and unique indexes remain authoritative. A Redis lock is
  *never* used for financial or ledger correctness: it can be lost (failover, expiry) while the holder keeps working.
- **Redis locks** (`SET NX PX` with a fencing token) only for non-correctness singletons: beat leadership (if HA beat is ever needed)
  and cosmetic de-duplication.
- **Job exclusivity:** the DB claim (section I). For singleton periodic job types, a filtered unique index on `(job_type)` WHERE status
  IN ('DISPATCHED','RUNNING') prevents two concurrent sweeps of the same kind.
- **New races introduced by asynchronous execution** (and the mitigations):

| Race | Risk | Mitigation |
|---|---|---|
| sweep expires an order's reservation while finance confirms payment (T3) | the order goes ATTENTION_REQUIRED instead of TRANSFER_PENDING — today's behaviour, but it now happens without any user action | business decision D6; order sweep uses order-first lock order; T3 already handles a lost reservation |
| sweep vs lazy expiry on a read | double expiry | both re-check under `UPDLOCK`; `run()` returns False for the loser |
| sweep vs user cancel / delivery | deadlock | identical lock order; `run()` deadlock retry |
| duplicate task delivery (acks_late, visibility timeout, two beats) | double effect | DB claim + slot idempotency + locked re-checks |
| job enqueued in a transaction that rolls back | phantom work | outbox: job row in the same transaction; publish after commit |
| commit succeeds, publish fails | lost job | `dispatch_pending` re-publishes QUEUED rows |
| user's permission revoked between enqueue and execution | action without authority | re-authorize at execution (D27) |
| worker clock vs DB clock on different hosts | early / late expiry | due checks use DB time `SYSUTCDATETIME()` or NTP-synchronized hosts (D28) |
| long calculation job vs recalculation request | stale run executed | run state machine + frozen snapshot; execution re-checks the run state under lock |
| provider poll vs manual confirm-paid | double outcome | `_provider_outcome` runs under the payout lock; PAID → RECONCILED only; the trigger freezes PAID evidence |

## N. Transaction boundaries

Each job uses separate short transactions:

1. **Claim** (UPDATE + commit).
2. **Business work**, one `ls.run()` per entity (as `expire_due` already does). A sweep over 10,000 reservations is 10,000 short
   transactions, never one long one. It is chunked, with a per-chunk checkpoint on the job row.
3. **Finalize** (status, counts, error) + commit.

Rules:
- No transaction is held open across an external call; the outbox pattern stays.
- No DB transaction spans the Celery publish (publish only after commit).
- Audit rows stay in the business transaction, as today.

## O. Database interaction from workers

- Same engine factory; `dispose()` after fork; pool sized per worker concurrency (`pool_size ≥ concurrency`, small overflow).
- `pool_pre_ping=True` (already set) covers DB restarts.
- A query timeout should be set for maintenance queries, through the connection or statement options.
- RCSI means sweeps read committed versions without blocking writers. Writes still take row locks.
- Batching: select candidate ids with `TOP (n)` ordered by due time, then process each id in its own `run()`.
- Least privilege: a separate SQL login for workers with the same DML rights as the API, no DDL (D29).

## P. Audit requirements

- Every state change made by a job is audited exactly as the synchronous path does it (same service function). Rows are written with:
  - `request_id = "job:<job_code>:<attempt>"`, the correlation id carried through logs;
  - `user_id` = the **system actor** (D4) for scheduled jobs, or the requesting user for user-requested jobs, with the system actor
    recorded as executor in the job row;
  - organization ids as the service already decides (two-organization pattern).
- **Job lifecycle audit:** created, dispatched, attempt started, succeeded / skipped / failed / dead, manually retried, cancelled. These
  go in `background_job_attempts` plus `audit_logs` for manual actions (retry, cancel).
- Never put payload secrets in audit: job payloads hold ids only (section Q).

## Q. Security / authorization for background jobs

- **Payloads carry ids only.** No PII, bank data, tokens, file contents or amounts entered by users. Redis is not a secure store.
- **JSON serializer only.** Optional Celery message signing (`auth` serializer) is a D26 sub-decision.
- **Scheduled system jobs** run with the system context (D4) and may perform only **system-owned transitions**: deadline expiry,
  housekeeping, recording provider-reported outcomes (D13). They can never approve, confirm, execute, reconcile or close.
- **User-requested jobs** store `requested_by` and the organization. At execution the worker reloads the principal
  (`load_principal`) and re-checks the same permission and organization scope as the endpoint. A revoked user → FAILED
  (`PERMISSION_REVOKED`), audited.
- **Job administration API** (`/api/v1/jobs`): permission-gated (D16), organization-scoped for organization users (their own requested
  jobs), platform-wide only for platform roles.
- **No public Flower.** Flower shows task arguments and allows revoking tasks. If used at all: internal network only, with
  authentication (D23).

## R. Multi-organization isolation

- Job rows carry `organization_id` (nullable for platform-wide maintenance) and `environment`.
- Organization users can list only jobs they requested or that target their organization (same 404 / 403 rules as entities).
- Platform-wide sweeps operate across organizations, but every state change is audited to the affected organizations (the services
  already do this).
- A worker never mixes organizations in one transaction beyond what the synchronous service already does.

## S. Financial safety

| Rule | How Phase 12 guarantees it |
|---|---|
| Never duplicate revenue | recognition stays in the T4 transaction (synchronous); unique index on RECOGNITION per order item; no job creates revenue |
| Never duplicate payout | payouts are created only by `POST /payouts/from-settlement` (user); unique open payout per (run, farmer); no job calls `create_for_run` |
| Never execute a payout twice | `initiate` / `confirm-paid` stay user actions; no job performs them. Provider polling (D12) can only record a provider-reported outcome under the payout lock; `uq_payouts_external`; PAID is frozen by trigger |
| Never bypass approval | jobs can't approve (no SoD actor); D13 locks this; every approval checks `principal.user_id` against stored actors, and a system actor holds no finance permission |
| Never bypass reconciliation | no automatic MATCHED; reconciliation stays a user action with statement evidence; provider PAID ≠ RECONCILED (trigger: PAID → RECONCILED only) |
| Never mutate immutable financial records | the existing triggers apply to workers identically; workers use the same service functions; no raw-SQL tasks |

Phase 11 operations that need special idempotency / locking if they are **ever** made asynchronous (not proposed now):

- `settlement_service.calculate`: project lock + claim indexes; a job must claim by run id and re-check DRAFT.
- `payout_service.initiate`: bank re-check under lock; must never run from a job.
- `payout_service.query_status` / `_provider_outcome`: TEST only. A poll job must use the payout lock and treat UNCONFIRMED → PAID as
  provider-owned only.
- `finance_service.reverse_for_refund_in_tx`: must stay inside the refund transaction.
- `payout_service.reconcile`: user-only (SoD vs executor).

## T. Monitoring and observability

- **Source of truth:** the `background_jobs` table. Queue depth (QUEUED / RETRY_SCHEDULED counts), oldest QUEUED age, RUNNING with
  expired lease, DEAD in the last 24 h, per-type success rate and duration.
- **Admin page** (frontend, D16): "Background jobs" (list, filter, attempt history, retry / cancel).
- **Worker heartbeat:** each worker updates a `worker_heartbeats` row (or a Redis key with TTL) every N seconds. Beat records its last
  tick.
- **External stack** (Prometheus / Grafana / Azure Monitor / …): none exists in the repository (D23).

## U. Logging

- §22 requires structured logs with `request_id`. The current logging is plain text (`main.py`).
- Proposal (12A or 12B per D1): JSON log lines with `request_id` / `job_id` / `attempt` / `task` / `queue` / `org_id` / `environment`.
- Task logs must never contain payload PII or secrets; error messages are sanitized (no SQL parameters).
- Correlation: the `X-Request-ID` of the enqueuing request is stored on the job row and logged by the task.

## V. Metrics

Proposed metrics (exposure decided by D23):
- `jobs_queued{type,queue}`, `jobs_running`, `jobs_dead_total`, `job_duration_seconds{type,result}`, `job_attempts_total{type,result}`;
- `oldest_queued_age_seconds{queue}`, `worker_up{worker}`, `beat_last_tick_age_seconds`;
- `redis_up`, broker queue length;
- business counters: `reservations_expired_total`, `orders_expired_total`, `listings_expired_total`, `orphans_swept_total`.

## W. Health checks

- Today `GET /api/v1/health` is unauthenticated and returns status, database and **environment** [REPO].
- Proposal (D24):
  - `/health/live`: process only, no dependencies.
  - `/health/ready`: database + Redis, used by the load balancer.
  - An authenticated detailed status for administrators: workers, beat, queue depth, DEAD count.
- No internal topology is exposed publicly.
- Worker liveness: the Celery `inspect ping` or heartbeat row; beat liveness: last-tick age.

## X. Worker failure / restart behaviour

- **Crash mid-task:** `acks_late` + `reject_on_worker_lost` → re-delivery. The DB lease expires, so `recover_stuck` moves the job to
  RETRY_SCHEDULED.
- **Partial work:** each entity was processed in its own transaction, so committed items stay done and the re-run skips them (locked
  re-checks).
- **Restart:** stateless. Leases owned by a dead `worker_id` are recovered after `lease_until`.
- **Poison task:** `max_attempts` → DEAD + alert. Never an infinite loop.

## Y. Redis failure behaviour

- **API keeps working.** No synchronous user flow depends on Redis (section C). Enqueueing writes the DB row; publish failure is logged
  and the row stays QUEUED.
- **Rate limiter (12B):** policy needed when Redis is down. Fail open, to the in-memory per-process limiter, or fail closed for login
  only (D22).
- **Lazy expiry still guarantees correctness** while workers cannot receive tasks.
- **On recovery:** `dispatch_pending` re-publishes. Duplicates are harmless (section I).
- **Data loss in Redis:** none of consequence; the DB is the record.

## Z. Database failure behaviour

- **Workers:** `pool_pre_ping` + retry with backoff on connection errors. The claim fails, so the task retries later. Celery tasks
  awaiting the DB are not acknowledged as successful.
- **Mid-transaction failure:** rollback (`run()` handles it). The job row keeps its last committed state, and the lease expires.
- **Long outages:** jobs go to RETRY_SCHEDULED → DEAD after `max_attempts`. Alert. Manual retry after recovery.
- **Failover:** reconnect; `HOLDLOCK` semantics are unchanged.

## AA. Deployment model

- **Processes:** `api` (uvicorn, N replicas, once Redis rate limiting is in place), `worker-maintenance`, `worker-calculation`,
  `worker-reports`, (later) `worker-integration` and `worker-notifications`, `beat` (exactly 1), `redis`, `sqlserver`, object storage.
- Same image for API and workers (`docker/backend.Dockerfile`), different commands. Compose additions: `worker`, `beat` services with
  `depends_on` redis / sqlserver health.
- Migrations stay a separate deploy step (deployment.md item 3). Workers must start **after** the migration that adds the job tables.
- The production platform is not defined anywhere (D34).

## AB. Local development model

- **Constraints found** [REPO / machine]: no Docker on the development machine; compose "not exercised"; Windows 11; Python 3.10.0;
  about 300 MB free on C:; `wsl.exe` present (no distribution inspected); your archived Redis 3.0.504 Windows port is unsuitable.
- **Options (D18):**
  - Redis in WSL2 or Docker Desktop (disk space needed);
  - Memurai (a Windows-native Redis-compatible server, licensing);
  - a remote development Redis;
  - **no Redis locally**, running tasks eagerly (`task_always_eager`) in development and tests, with real-worker integration tests only
    where Redis exists.
- The worker on Windows uses `celery -A app.workers.celery_app worker -P solo` (or threads); beat runs separately.

## AC. Test strategy

- **Unit:** every task function is called directly against the rolled-back test database (as services are tested today), plus Celery
  `task_always_eager` for routing and serialization.
- **Job framework:** claim exclusivity, state machine, slot idempotency, outbox (rollback = no job; commit + publish failure = QUEUED →
  dispatch), lease recovery, retry classification, DEAD after max attempts, manual retry / cancel permissions and audit, payload
  contains ids only.
- **Concurrency (snapshot harness, like 9B / 10 / 11):**
  - two workers claiming the same job;
  - sweep vs T3 confirmation;
  - sweep vs user cancel;
  - sweep vs lazy expiry;
  - order sweep vs reservation sweep (lock order);
  - duplicate beat slot.
- **Financial safety:** assertions that no task name / route can create or change revenue, settlements, payouts or reconciliations
  (registry introspection, similar to the Phase 11 OpenAPI check); a system actor holds no finance / approval permission.
- **Integration (requires Redis, D18 / D19):** a real worker + broker, task re-delivery after a killed worker, Redis restart recovery.
- **Regression:** the full Phase 1–11 suite stays green; lazy-expiry tests are unchanged.

## AD. E2E strategy

- DEMO: the "Background jobs" admin page is visible to the D16 role and shows the DEMO note / honest empty state. Sweeps run on DEMO
  data, which contains no reservations, orders or listings, so there is nothing to expire.
- **No E2E step should depend on wall-clock schedules.** The E2E calls an admin "run now" for maintenance jobs (if D16 allows it) or
  the existing `expire-due` endpoint, and asserts audit rows / job rows.
- The E2E environment needs Redis + one worker + beat (or eager mode); this depends on D18.

## AE. Migration requirements

Proposed `0017_phase12_jobs` (names illustrative; D25):

- **`background_jobs`:**
  - identity: `job_code` (JOB- sequence), `job_type`, `queue`, `status`;
  - scope and keys: `environment`, `organization_id` (nullable), `requested_by` (nullable), `idempotency_key` (filtered unique);
  - payload and outcome: `payload` (JSON, ids only, `ISJSON` check), `result` (JSON counts), `last_error_code`,
    `last_error_message` (sanitized);
  - retries and lease: `attempt`, `max_attempts`, `next_attempt_at`, `lease_owner`, `lease_until`;
  - timing and correlation: `dispatched_at`, `started_at`, `finished_at`, `celery_task_id`, `correlation_request_id`.
- **`background_job_attempts`:** append-only — attempt no, worker id, started / finished, outcome, error code.
- **Optionally `worker_heartbeats`**, if not kept in Redis (D23 / D24).
- **Filtered unique indexes:** the idempotency key; one active singleton per periodic job type.
- **Triggers:** attempts append-only; final job states frozen; no delete.
- **Downgrade guard:** refused while job rows exist.
- **System actor (D4):** a seeded non-login user per environment, via `manage.py seed-reference` (reference data, not migration data)
  or the migration. This depends on the user status values available (a new `SYSTEM` / `SERVICE` status may need a CHECK change).
- **No change** to Phase 1–11 tables, unless D4 option C (nullable actor) were chosen, which is not recommended.

## AF. Dependency / version recommendations

To be verified against current releases and pinned at implementation (D2):

| Package | Recommendation | Note |
|---|---|---|
| `celery[redis]` | latest stable 5.x supporting Python 3.10 | pulls `kombu`, `billiard`, `vine`, `redis` |
| `redis` (redis-py) | as required by kombu | also used by the 12B rate limiter |
| server | Redis 7.x (compose already `redis:7-alpine`) | not the Windows 3.0 port |
| optional | `flower` (internal only), a Prometheus client (only if D23 selects it), `fakeredis` (tests only, if D19 selects it) | no other new runtime dependency |

- About 10–20 MB of wheels: acceptable, but disk space must be checked first (about 300 MB free).
- Python 3.10.0 is old within 3.10; upgrading is a 12B item.

## AG. Configuration / environment variables

Proposed variables (all optional with safe defaults; none hold business values):

- **Broker:** `REDIS_URL` (exists), or a separate `CELERY_BROKER_URL`.
- **Execution:** `CELERY_TASK_ALWAYS_EAGER` (dev / test only; refused in production), `JOBS_ENABLED` (master switch),
  `WORKER_CONCURRENCY_<QUEUE>`.
- **Timing and retries:** `JOB_LEASE_SECONDS`, `JOB_DEFAULT_MAX_ATTEMPTS`, `JOB_BACKOFF_BASE_SECONDS`, `JOB_BACKOFF_MAX_SECONDS`.
- **Schedules and retention:** `SCHEDULE_EXPIRY_SECONDS` (D7), `SCHEDULE_ORPHAN_SWEEP` / `ORPHAN_GRACE_HOURS` (D10), `RETENTION_*_DAYS`
  (D10; unset = never purge).
- **Polling:** `PROVIDER_POLL_SECONDS` (D12; unset = disabled).
- **Redis key namespace:** `REDIS_KEY_PREFIX`.

Production guards: eager mode and an unauthenticated `redis://` to a non-local host are refused at start-up. `.env.example` is
updated; secrets are never committed.

## AH. Security risks

1. An unauthenticated or publicly exposed Redis (compose publishes `6379`) allows task injection. Mitigate with auth / TLS / network
   isolation and JSON-only tasks.
2. Pickle deserialization leads to remote code execution. Accept JSON only.
3. Flower exposure leaks arguments and allows revoking tasks. Keep it internal and authenticated, or don't use it.
4. Privilege drift: a job executes after its user lost permissions. Re-authorize at execution.
5. Over-privileged system actor: it must hold **no** role or permission. Its only power is the narrow set of system transitions coded
   into tasks.
6. Secrets or PII in payloads, logs or errors. Use ids only and sanitized errors.
7. A worker SQL login with DDL rights. Use least privilege.
8. Health endpoint information disclosure. Use the split endpoints (section W).

## AI. Operational risks

- A second beat instance: mitigated by slot idempotency, but it should still be prevented operationally.
- Visibility timeout shorter than a task → duplicate runs. Configure, and rely on the lease guard.
- Sweeps increasing DB load or lock contention at peak. Chunk, keep low concurrency, and schedule (D7).
- Queue backlog after an outage → expiry burst. Process due items oldest first; the work is idempotent.
- The DEAD queue grows silently without alerting (D15 / D23).
- Windows development parity: solo pool vs prefork in production.
- Disk space on the development machine for Redis / Docker (D18).
- Celery / kombu upgrades: pin versions and test re-delivery behaviour.

## AJ. Rollback strategy

- **Feature flag `JOBS_ENABLED=false`:** stop beat and workers. Lazy expiry and manual endpoints keep the platform correct, because
  all correctness checks remain synchronous.
- **Code rollback:** previous image. Job tables are additive, so Phase 1–11 code ignores them.
- **Migration rollback:** `alembic downgrade 0016` is refused while job rows exist. Archive and clear them first (documented
  procedure), then downgrade.
- **No data rollback** for completed business transitions: an expiry performed by a job is a normal audited business change, exactly
  as if lazy expiry had done it.

## AK. DEMO / TEST / LIVE isolation

- Every job row has an `environment`. Sweeps process only entities of their own environment.
- **DEMO:**
  - maintenance jobs only;
  - no calculation jobs (no DEMO calculation module, Phase 7);
  - no provider polling;
  - no financial jobs;
  - the admin page shows the honest DEMO note.
- **TEST:**
  - eager mode and snapshot concurrency tests;
  - the TEST payment / payout / registry adapters are never registered in the worker (as today with `ADAPTERS`).
- **LIVE:** only MANUAL adapters exist, so `integration` polling stays disabled.
- **Redis:** environment key prefixes, and a separate Redis DB or instance per environment if they share hardware (D17).

## AL. What Phase 12 (12A) explicitly does not implement

The items below are recommended exclusions, pending D1 / D36:

- No automatic payout execution, payout approval, settlement approval, reconciliation matching, refund, revenue recognition / reversal,
  or recovery-case resolution.
- No scheduled settlement runs, unless D11 selects them.
- No payment, payout, registry or LIMS provider integration, and no public webhook endpoint (no contract exists).
- No EMAIL / SMS / WhatsApp delivery (no provider; D31).
- No real antivirus engine or S3 adapter (12B / D32).
- No change to Phase 1–11 business rules: lazy expiry stays.
- No microservices: the modular monolith stays (§2).
- No Kubernetes / cloud-specific deployment (D34).

---

## 3. Special findings

### 3.1 Phase 1–11 operations that must NOT move to background execution

See section C. In short: everything that a person decides or approves; everything that must answer the user immediately (ledger
availability, order placement, uploads); revenue recognition / reversal; every Phase 11 settlement, payout and reconciliation step.

### 3.2 Phase 11 operations needing special idempotency / locking (if ever asynchronous)

See section S. `calculate` (project lock + claims), `initiate` (bank re-check under lock — never from a job), `query_status` /
`_provider_outcome` (payout lock; provider-owned transitions only), `reverse_for_refund_in_tx` (must stay in-transaction), `reconcile`
(SoD vs executor — user only).

### 3.3 Dangerous races introduced by asynchronous execution

See the table in section M. The two that change visible behaviour are:
- the reservation sweep vs payment confirmation (D6);
- the system actor on expiry (D4).

All others are neutralized by the existing locks plus the DB claim and outbox.

### 3.4 Contradictions / tensions found

| C | Tension | Source A | Source B | Proposed resolution |
|---|---|---|---|---|
| C1 | Phase 12 scope | §22 "production hardening" (broad) | request: Celery / Redis / jobs | split 12A / 12B (D1) |
| C2 | "No worker" decisions | Phase 9B D4, Phase 10 D5 ("No worker") | Phase 12 sweeps | lazy expiry stays; sweeps added for promptness; amend wording (D5) |
| C3 | Provider status "query once, no job" | Phase 9A, Phase 10 D35 | async integrations (§22) | polling only for non-MANUAL adapters; none exists in LIVE (D12) |
| C4 | Synchronous calculation / report with guards | Phase 7 A18, Phase 8A B11 | §12 "Use Celery for long calculations" | async only above the guard (D8, D9) |
| C5 | "Long calculations" | §12 | no production calculation module registered (Phase 7) | build the mechanism; no real workload yet |
| C6 | Compose stack | compose has `redis` but no worker / beat; "not exercised" | dev machine has no Docker | D18, D34 |
| C7 | Ledger actor NOT NULL | 9B schema (`actor_id` NOT NULL) | system actions without a user | system actor (D4) |
| C8 | Health endpoint | public, returns environment | adding Redis / worker details | split live / ready / admin (D24) |
| C9 | Phase 11 settlement cycle | Phase 11 decision lock: "none (manual runs) … Scheduled runs are Phase 12" | financial safety | no scheduled settlement unless D11 selects it |

### 3.5 Business decisions still required

- **BUSINESS DECISION REQUIRED (11):** D6 (reservation expiry for reported payments), D7 (sweep intervals), D10 (retention / orphan
  grace), D11 (scheduled settlement), D15 (dead-job alerting / on-call), D17 (Redis hosting), D18 (local environment), D23 (monitoring
  platform), D31 (notification channels), D32 (antivirus), D34 (deployment platform).
- **RECOMMENDATION — REQUIRES SIGN-OFF (10):** D1 (scope 12A / 12B), D4 (system actor), D5 (workloads; amend "no worker"), D8 / D9
  (async calculation / report above the guards), D12 (provider polling), D13 (no financial jobs), D16 (job permissions), D22 (Redis
  rate limiter and failure policy), D30 (environment isolation).

### 3.6 Technical decisions to lock before coding

D2 (Celery + Redis), D3 (DB system of record + outbox), D14 (retry policy), D19 (test strategy), D20 (static beat schedule), D21 (DB
locks authoritative), D24 (health), D25 (migration), D26 (payload / serializer), D27 (re-authorization), D28 (clock), D29 (worker
login), D33 (no webhooks), D35 (access log), D36 (boundary).

---

## 4. Proposed implementation order (sequence only — not started)

1. Lock the decisions (decision lock).
2. Dependencies (`celery[redis]`) + configuration + production guards.
3. Migration `0017_phase12_jobs` + system actor seed.
4. Job framework: model, state machine, outbox enqueue, claim / lease, retry classification, finalize, attempts.
5. Celery app, queues, routing, worker init (engine dispose), beat schedule with slot idempotency.
6. Tasks: dispatch_pending, recover_stuck, expire_orders → expire_listings → expire_reservations, orphan sweep; then calculation /
   report jobs (if D8 / D9), retention (if D10).
7. Job administration API + permissions + audit; health endpoints.
8. Frontend: Background jobs page; async status for calculation / report (if D8 / D9).
9. Tests: unit, framework, concurrency (snapshot), financial-safety introspection, integration with Redis (if available), full
   regression.
10. E2E, docs (`docs/background-jobs.md`, updates), compose worker / beat services.

None of these steps is implemented by this document.
