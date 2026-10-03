# Background jobs (Phase 12A)

Celery workers run **safe scheduled operational work**: proactive expiry sweeps, an orphan-file scan and retention-purge infrastructure.
They do **not** take over any business decision.
- Design: [phase-12-discovery.md](phase-12-discovery.md).
- Locked decisions: the Phase 12A implementation prompt, summarized in [phase-12-decision-lock.md](phase-12-decision-lock.md).

## 1. Architecture

```
Celery beat (exactly one) ──jobs.schedule / jobs.recover──▶ Redis (broker: job ids only) ──▶ Celery worker(s)
                                                                                                   │
API / services ── business transaction + background_jobs row ── COMMIT ── publish job id ─────────┘
                                                                                                   ▼
                         SQL Server: background_jobs · background_job_attempts · audit_logs · workflow_events
                                     (the system of record)        │
                                                                    ▼
                                    existing domain services (9B ledger, Phase 10 orders / listings)
```

- **SQL Server is the system of record** for every job, attempt, result and audit row.
- **Redis is disposable transport.**
  - The Celery result backend is disabled.
  - Messages carry only a job id (JSON; pickle is refused).
  - If Redis is cleared, the SQL rows are republished by the recovery tick.
- **Delivery is at-least-once; the business effect is effectively-once.**
  - The worker claims the SQL row under `UPDLOCK, HOLDLOCK, ROWLOCK`.
  - The domain service locks and re-checks the object it changes.
  - SQL Server and Redis are **not** transactional together. The outbox below and recovery make the pair reliable.
- **Tasks are thin adapters:** Celery task → `job_service.execute(job_id)` → allow-listed handler → existing domain service → SQL
  transaction. No business rule lives in a task, and no worker goes through HTTP.

## 2. Transactional enqueue (outbox)

1. Inside the business transaction, `job_service.enqueue(...)` adds the `background_jobs` row (status QUEUED) and its `JOB_CREATED`
   audit row.
2. The caller commits.
3. Only then does `job_service.publish(job_id)` send the job id to Redis.
   - If publishing fails (Redis down or not configured), the row keeps status QUEUED with `last_publish_error`.
   - The API never reports the business operation as failed.
4. `jobs.recover` (beat, every `JOB_RECOVERY_INTERVAL`) or `python manage.py jobs-recover` republishes such rows.

A rolled-back transaction leaves no job. A committed job whose message was lost is republished.

## 3. Job lifecycle

```
QUEUED ──claim──▶ CLAIMED ──start (attempt row)──▶ RUNNING ──▶ SUCCEEDED
  │                  │                                │
  │                  └─(lease expired)──▶ QUEUED       ├──▶ RETRY_WAITING ──(due, recovery tick)──▶ QUEUED
  └──▶ CANCELLED (operator)                           └──▶ FAILED ──(operator requeue)──▶ QUEUED
```

- **Final states:** SUCCEEDED and CANCELLED. A FAILED job can only be requeued by a person with `jobs.manage` (audited, with a
  reason). A trigger enforces this.
- **Attempts** (`background_job_attempts`) are **append-only**.
  - A row is written when an execution starts (RUNNING) and completed exactly once: SUCCEEDED, RETRYABLE_ERROR, FAILED, or ABANDONED
    (worker lost).
  - A trigger forbids any later change or delete.
- **Audit actions:** `JOB_CREATED`, `JOB_CLAIMED`, `JOB_STARTED`, `JOB_RETRY_SCHEDULED`, `JOB_SUCCEEDED`, `JOB_FAILED`, `JOB_CANCELLED`,
  `JOB_REQUEUED`. Each also has a `workflow_events` row.
- **Duplicate delivery** of a job that is claimed, running, succeeded, failed or cancelled is a logged no-op (`NOT_ELIGIBLE` /
  `NOT_CLAIMED`).

## 4. Task registry (allow-list)

Defined in `backend/app/workers/registry.py`. Nothing else can be enqueued, triggered or executed, and task names never come from a
client or a stored payload.

| Job type | Celery task | Queue | Schedule | What it does | Idempotency |
|---|---|---|---|---|---|
| `EXPIRY_CREDIT_RESERVATIONS` | `maintenance.expire_credit_reservations` | maintenance | `JOB_EXPIRY_INTERVAL` (600 s) | expires ACTIVE 9B reservations past `expires_at` via `ledger_service.expire_reservation_in_tx` (same `RESERVATION_EXPIRE` entry as lazy expiry) | lock + re-check per reservation, one transaction each |
| `EXPIRY_MARKETPLACE_OBJECTS` | `maintenance.expire_marketplace_objects` | maintenance | `JOB_EXPIRY_INTERVAL` | expires unpaid PLACED orders past the payment deadline (`order_service.expire_if_due`: order → reservations), then listings past `valid_until` (`expire_listing_if_due`) | lock + re-check (state, deadline, held payment) |
| `ORPHAN_FILE_SCAN` | `maintenance.scan_orphan_files` | maintenance | `JOB_ORPHAN_SCAN_INTERVAL` (daily) | reports stored files that no document version references and that are older than `JOB_ORPHAN_GRACE_HOURS` | read-only; **deletes nothing** (deletion deferred) |
| `RETENTION_PURGE` | `maintenance.retention_purge` | maintenance | `JOB_RETENTION_INTERVAL` (daily) | infrastructure only: no retention policy exists, so it logs "not configured" and purges nothing | no-op |

- **Infrastructure ticks** (`default` queue, not job rows):
  - `jobs.schedule(job_type)` creates one job per environment in `JOB_ENVIRONMENTS`, keyed `schedule:<type>:<env>:<slot>`, so a
    duplicate beat or redelivery creates nothing.
  - `jobs.recover()` handles stale leases, due retries and unpublished jobs.
- **No financial queue or task exists.** No worker ever:
  - recognizes or reverses revenue;
  - calculates or approves settlements;
  - creates, approves, executes or reconciles payouts;
  - confirms payments or completes refunds;
  - approves, verifies or decides anything;
  - issues, transfers or retires credits.

  Tests check the registry and the worker modules' imports.

## 5. Expiry semantics (unchanged business rules)

- **Lazy expiry stays.** Reads and writes still expire due objects, so the platform is correct with the workers stopped. The sweeps
  only make expiry timely.
- **Bounded work.** Sweeps run in keyset batches of `JOB_BATCH_SIZE`, one short transaction per object, within a cooperative time
  budget below the task's soft time limit. A run that reaches its budget records `complete: false` and the next run continues.
- **System actor.** Expiries are attributed to the per-environment non-login **SYSTEM actor** (`users.status = SYSTEM`, seeded by
  migration 0017). It holds no role and no permission, cannot sign in, and is hidden from user administration.
- **Reported payments.** A buyer-reported payment (PENDING_CONFIRMATION) holds the *order* but not its *reservations* (Phase 10
  behaviour). A late confirmation goes to ATTENTION_REQUIRED through the existing human workflow. A worker never recreates a
  reservation or completes a transfer.
- **Item errors.** A per-object business refusal is recorded and the sweep continues. The job ends FAILED (`SWEEP_ITEM_ERRORS`) so it
  is visible.

## 6. Retries and failure handling

| Class | Examples | Behaviour |
|---|---|---|
| Retryable | DB connection lost / deadlock (after `ledger_service.run`'s own retries), broker / network errors, soft time limit | RETRY_WAITING with deterministic exponential backoff `JOB_RETRY_BACKOFF_SECONDS × 2^(n−1)` (capped at 1 h), at most `JOB_MAX_RETRIES` times, then FAILED |
| Non-retryable | any business / validation / permission / configuration error (`AppError`), environment mismatch, missing SYSTEM actor, unexpected exception | FAILED at once, with `error_code` and a sanitized message (no SQL text, no traceback; tracebacks go to the server log only) |

**Stale leases.**
- Claims and runs hold a lease of `JOB_STALE_AFTER_SECONDS` (longer than every task time limit).
- A **CLAIMED** job whose worker died is requeued; nothing ran.
- A **RUNNING** job's attempt becomes ABANDONED (`WORKER_LOST`), and the job is retried, or FAILED once retries are exhausted.
- Work already committed by the lost worker is not redone: the locked re-checks skip it.
- A late result from the lost worker is discarded (`LEASE_LOST`).

## 7. Environment isolation (DEMO / LIVE / TEST)

- **Every job has an environment.** Sweeps touch only rows of that environment, under that environment's SYSTEM actor.
- A worker refuses a job whose environment is not in `JOB_ENVIRONMENTS` or not supported by the task (`ENVIRONMENT_MISMATCH`).
- **Operators see only their own environment's jobs.** A DEMO platform admin sees DEMO jobs only; a LIVE job is "not found".
- **DEMO** has no registry-issued credits, orders or listings, so its sweeps find nothing to expire. The page shows the DEMO note.
- **TEST:** tests call task functions directly and use no Redis. The broker-integration test uses a real Redis (`REDIS_TEST_URL`) or
  the test-only `fakeredis` TCP server. No TEST adapter is ever registered.

## 8. Operations API and UI

- `/api/v1/jobs` provides:
  - list / get / attempts;
  - `registry` (read-only);
  - `status`: database, broker (NOT_CONFIGURED / REACHABLE / UNREACHABLE), worker heartbeats, counts, last schedule;
  - `POST /jobs/{id}/cancel` (QUEUED only) and `POST /jobs/{id}/retry` (FAILED only), each with a reason;
  - `POST /jobs/trigger` for an allow-listed, manually-triggerable job type (never an arbitrary task).
- Permissions: `jobs.read` / `jobs.manage`, granted to the Platform Administrator only.
- UI: **Administration → Background jobs**. It has no "run a task" control and shows no stack trace.
- A reachable broker is reported separately from worker liveness. Worker liveness means a heartbeat within
  3 × `JOB_HEARTBEAT_SECONDS`.

## 9. Configuration

| Variable | Default | Meaning |
|---|---|---|
| `REDIS_URL` | empty | Celery broker. Empty = no broker (jobs stay QUEUED; nothing breaks). Outside localhost use a password and TLS (`rediss://`). |
| `JOB_ENVIRONMENTS` | `LIVE,DEMO` | data environments scheduled jobs run for (production: `LIVE`) |
| `JOB_MAX_RETRIES` | 3 | bounded retries of transient failures |
| `JOB_RETRY_BACKOFF_SECONDS` | 60 | backoff base |
| `JOB_STALE_AFTER_SECONDS` | 1800 | lease (≥ 900, must exceed every task time limit) |
| `JOB_BATCH_SIZE` | 200 | rows per sweep batch |
| `JOB_EXPIRY_INTERVAL` | 600 | expiry sweeps (10 min) |
| `JOB_ORPHAN_SCAN_INTERVAL` / `JOB_ORPHAN_GRACE_HOURS` | 86400 / 24 | orphan scan (daily) / safety period before a file can be a candidate |
| `JOB_RETENTION_INTERVAL` | 86400 | retention infrastructure (purges nothing) |
| `JOB_RECOVERY_INTERVAL` | 60 | recovery tick |
| `JOB_HEARTBEAT_SECONDS` | 30 | worker heartbeat |

Intervals are operational defaults, not business rules. **No retention period is configured.** Job history is kept, and
audit / ledger / financial records are never purged by a job.

## 10. Running locally (Windows development machine)

The API, the tests and the E2E run **without Redis**. Jobs created then simply stay QUEUED. For a real worker:

**Redis (pick one; do not use the old Windows-native Redis 3.x ports, which are unmaintained):**
- **WSL2** (recommended). In an elevated PowerShell: `wsl --install -d Ubuntu`, reboot, then in Ubuntu:
  `sudo apt-get update && sudo apt-get install -y redis-server` and `sudo service redis-server start`. WSL2 forwards `localhost:6379`
  to Windows.
- **Docker Desktop:** `docker run -d --name carbon-redis -p 127.0.0.1:6379:6379 redis:7-alpine redis-server --appendonly yes`.
- Any reachable Redis ≥ 7.

Then set `REDIS_URL=redis://localhost:6379/0` in `backend/.env`.

**Worker and beat on Windows (development only; production workers run on Linux with the prefork pool).** From `backend/`:

```powershell
.venv\Scripts\celery -A app.workers.celery_app:celery_app worker -Q default,maintenance -l info -P solo
.venv\Scripts\celery -A app.workers.celery_app:celery_app beat -l info --schedule $env:TEMP\carbon-celerybeat-schedule
```

- Run exactly **one** beat.
- The Windows solo pool does not enforce Celery hard time limits. The handlers' cooperative time budget and the SQL lease still bound
  every job.
- The worker can also run inside WSL2. It then needs a SQL Server connection over TCP (`SQL_SERVER_HOST=<windows host IP>`,
  TCP enabled); the default local setup uses shared memory, so the Windows-native worker is simpler for development.

**Tests:**

```bash
pytest tests/test_jobs.py                 # unit: no Redis
pytest tests/test_jobs_concurrency.py     # races + a real Celery worker over the Redis protocol:
                                          #   REDIS_TEST_URL=redis://localhost:6379/15 for a real Redis, else test-only fakeredis
```

## 11. Operational runbook

| Symptom | Meaning | Action |
|---|---|---|
| Broker NOT_CONFIGURED | `REDIS_URL` empty | expected in development; jobs stay QUEUED; set `REDIS_URL` to run workers |
| Broker UNREACHABLE | Redis down | nothing is lost (SQL keeps the jobs); restore Redis, then wait for the recovery tick or run `python manage.py jobs-recover` |
| "No heartbeat" | no worker running | start a worker; queued jobs wait; lazy expiry keeps workflows correct |
| QUEUED jobs with `last_publish_error` | publication failed | `python manage.py jobs-recover` (or the next tick) republishes |
| Job stuck CLAIMED / RUNNING | worker died | recovered automatically after `JOB_STALE_AFTER_SECONDS` (CLAIMED → QUEUED; RUNNING → retry / FAILED) |
| FAILED `SWEEP_ITEM_ERRORS` | some objects refused | read the job result / server log; fix the cause; requeue (reason required) |
| FAILED `ENVIRONMENT_MISMATCH` | job environment not enabled here | check `JOB_ENVIRONMENTS` |
| FAILED `SYSTEM_ACTOR_MISSING` | migration 0017 not applied | `python manage.py migrate` |
| No scheduled jobs created | beat not running | start exactly one beat; lazy expiry still applies |

Structured worker logs are JSON lines on the `app.jobs` logger. Fields: `event`, `job_id`, `job_code`, `attempt_id`, `task_name`,
`queue`, `environment`, `entity_type`, `entity_id`, `status`, `duration_ms`, `request_id`, `error_code`. Payload values, secrets,
tokens, KYC, bank data and documents are never logged.

## 12. Not in Phase 12A

Phase 12A does not include:
- provider polling or webhooks (no contracted provider);
- email / SMS / WhatsApp delivery;
- deleting orphan files;
- any retention period;
- moving calculation / report execution to workers (the framework supports it; Phase 7 / 8A stay synchronous);
- the S3 / MinIO adapter, antivirus, a monitoring stack, backup / restore and performance work (Phase 12B).
