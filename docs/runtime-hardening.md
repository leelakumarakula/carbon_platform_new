# Runtime hardening (Phase 12B-II)

Audience: the Platform / DevOps team deploying and operating the API, and security reviewers. Decisions are D18–D24, D30–D33, D38–D47 of
`docs/phase-12b-decision-lock.md`. "Implemented" below means built and tested in this repository; items marked **deployment** need real
infrastructure that does not exist on the development machine (no Redis server, secret store, SMTP or monitoring platform was used —
tests use fakeredis and closed ports).

## 1. Rate limiting (D18–D20, F5)

| Limit | Key | Default | Setting |
|---|---|---|---|
| Sign-in (unchanged) | IP, and IP + email | 10 / min | `LOGIN_RATE_LIMIT_PER_MINUTE` |
| Global (unchanged) | IP | 600 / min | `GLOBAL_RATE_LIMIT_PER_MINUTE` |
| Account lockout (unchanged, database) | user | 5 failures → 15 min | `MAX_FAILED_LOGINS`, `LOCKOUT_MINUTES` |
| Refresh (F5) | IP | **100 / min** | `REFRESH_RATE_LIMIT_PER_MINUTE` |
| Uploads (multipart) | user | **100 / min** | `UPLOAD_RATE_LIMIT_PER_MINUTE` |
| Per user | user | **1,000 / min** | `USER_RATE_LIMIT_PER_MINUTE` |
| Per organization | each organization of the caller | **5,000 / min** | `ORGANIZATION_RATE_LIMIT_PER_MINUTE` |
| Job / API burst | whole deployment, every API request | **10,000 / min** | `API_BURST_RATE_LIMIT_PER_MINUTE` |

Values are the locked D19 values. *Interpretation (documented):* "job / API burst" is one deployment-wide ceiling over all API requests;
the per-organization limit counts every organization the caller belongs to. Load-balancer probes (`/health/live`, `/health/ready`) are
exempt. A refused request gets HTTP 429 with `Retry-After: 60` and `RATE_LIMITED` / `ORGANIZATION_RATE_LIMITED` / `UPLOAD_RATE_LIMITED`.

**Backend.** `RATE_LIMIT_BACKEND=redis` (required in production) stores fixed-window counters in Redis (`INCR` + `EXPIRE`) under
`<RATE_LIMIT_KEY_PREFIX>:<env>:<sha256(key)>:<window>` — keys are hashed, so no email address or identifier is stored; counters are the only
data. `memory` (one process) is for development and tests. Use a dedicated ACL user, e.g. `RATE_LIMIT_REDIS_URL=rediss://limiter:…@redis:6380/1`.

**Redis outage → FAIL OPEN (locked D20).** Requests are not rate limited by Redis while it is unavailable. Never silent:
- a WARNING log line (`app.ratelimit`, at most every 30 s) — "rate limiter DEGRADED (fail-open, D20)";
- metrics `rate_limiter_degraded_total`, `redis_errors_total{component="rate_limiter"}`, gauge `rate_limiter_degraded`;
- `/health/ready` reports `rate_limiter: degraded` (HTTP 200: the API stays in rotation).
Still enforced during the outage: database account lockout, refresh-token rotation and reuse detection, sessions, RBAC. After a failure Redis
is not retried for `RATE_LIMIT_REDIS_RETRY_SECONDS` (5 s), and calls time out after `RATE_LIMIT_REDIS_TIMEOUT_SECONDS` (0.5 s), so an outage
adds no latency. The edge proxy should keep its own connection / request limits.

## 2. Client IP and trusted proxies (D21)

`TRUSTED_PROXIES` lists the reverse proxies / load balancers (IPs or CIDRs) whose `X-Forwarded-For` is believed. The client IP is the TCP
peer, unless the peer is trusted — then the right-most address in `X-Forwarded-For` that is not itself a trusted proxy. A header sent by
anyone else is ignored. `0.0.0.0/0` / `::/0` are refused. Uvicorn runs with `--no-proxy-headers` (Dockerfile), so this is the only
interpretation. The proxy must **append** to (not pass through unchecked) `X-Forwarded-For`. The client IP feeds rate limits, audit and
login records.

## 3. Request size (F6)

`MAX_REQUEST_BYTES` (25 MiB) is enforced by an ASGI middleware on the streamed body: a declared `Content-Length` above it is refused before
reading, and an undeclared / chunked body is cut off once it exceeds the limit (HTTP 413 `PAYLOAD_TOO_LARGE`). File uploads keep their own
`MAX_UPLOAD_BYTES` (15 MiB). **Deployment:** set the same body limit and request timeouts at the proxy (e.g. `client_max_body_size 25m`).

## 4. Production Redis (D22 / D23, F8) — self-hosted

Start-up refuses, in production: `RATE_LIMIT_BACKEND=memory`; any `REDIS_URL` / `RATE_LIMIT_REDIS_URL` that is not `rediss://` (TLS); a
URL without an ACL user and password; the `default` user. `REDIS_CA_CERT` verifies a private-CA certificate (API limiter and Celery broker).
Readiness verifies, through `INFO`, `maxmemory-policy noeviction` and AOF persistence (`appendonly yes`) and reports `failed` (HTTP 503) if
either is wrong — grant the monitoring identity `+info`.

**Deployment checklist (self-hosted Redis 7, India region, D50):** TLS only (`port 0`, `tls-port 6380`); ACL users `carbon-broker`
(Celery: `~celery* ~_kombu* ~unacked* +@all -@dangerous` or tighter), `carbon-limiter` (`~rl:* +incr +expire +pexpire +ping +info`),
`default` disabled; `maxmemory-policy noeviction`; `appendonly yes`, `appendfsync everysec`; `protected-mode yes`; no public port;
`rename-command`/ACL-deny `FLUSHALL`, `CONFIG`, `KEYS` for application users; monitoring of memory, evictions (must stay 0), AOF status,
replication. No business data is ever stored in Redis (job state stays in SQL Server — D24).

**Jobs during a Redis outage (D24, unchanged from 12A):** SQL Server remains the record; enqueued jobs stay `QUEUED` with the publication
error recorded (`redis_errors_total{component="broker"}`), and the recovery tick republishes them when Redis is back. Lazy expiry keeps every
workflow correct without workers.

## 5. Secrets and key rotation (D30) — self-hosted secret store

No vendor is selected. The boundary is a mounted directory: the secret store's agent / sidecar renders one file per setting into
`SECRETS_DIR` (file name = setting name, e.g. `/run/secrets/carbon/JWT_SECRET`). In production:
- `SECRETS_DIR` is required; `.env` is never read;
- a secret setting supplied as a plain environment variable is refused at start-up (`SECRET_SETTINGS` in `app/core/config.py`: secret
  keys, JWT keys, data keys, database URL / password, Redis URLs, object-storage secrets, antivirus key, SMTP password, metrics token, seed
  passwords);
- secrets never appear in logs (redaction, §7), Redis or the repository.

**Data-encryption key (Fernet → MultiFernet).** `DATA_ENCRYPTION_KEY` encrypts; `DATA_ENCRYPTION_PREVIOUS_KEYS` still decrypt. Runbook:
1. generate a key (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) in the secret store;
2. set it as `DATA_ENCRYPTION_KEY`, move the old key to `DATA_ENCRYPTION_PREVIOUS_KEYS`; restart every API / worker process;
3. `python manage.py rotate-data-key --dry-run`, then `python manage.py rotate-data-key` (batched, idempotent, `updated_at` preserved,
   one `DATA_ENCRYPTION_KEY_ROTATED` security event; exit code 1 if any value cannot be decrypted — nothing is overwritten then);
4. remove the old key; restart.
Encrypted today: `farmer_bank_accounts.account_number_enc`. *Not rotatable:* `SECRET_KEY` also keys the KYC / bank-number fingerprints
(HMAC; the raw identifiers are not stored), so rotating it would break duplicate detection — treat it as long-lived.

**JWT signing keys.** Tokens carry `kid` = `JWT_KEY_ID`. Runbook: put the new secret in `JWT_SECRET` with a new `JWT_KEY_ID`, keep the old
as `JWT_PREVIOUS_KEYS="<old kid>:<old secret>"`, restart; after `ACCESS_TOKEN_MINUTES` (15) remove it. Unknown `kid` → `TOKEN_INVALID`;
the algorithm is fixed (HS256). Refresh tokens are opaque and unaffected.

## 6. Health (D46, F9) and OpenAPI (F1)

| Endpoint | Purpose | Fails when |
|---|---|---|
| `GET /api/v1/health` | compatibility (status, database; environment only outside production) | never 5xx |
| `GET /api/v1/health/live` | liveness: the process answers; touches nothing | process hung |
| `GET /api/v1/health/ready` | load balancer readiness | **503**: database unreachable, schema not at migration head, public bucket / versioning off, Redis without noeviction / AOF, no real antivirus scanner configured |

Outages the platform degrades around (Redis, MinIO, the antivirus engine) are `degraded` with HTTP 200 — removing every node would turn a
partial outage into a full one (uploads / downloads answer 503 individually; LIVE uploads are never accepted unscanned). Production
responses contain check names and states only (`ok`, `degraded`, `failed`, `not_configured`); details are logged. `/docs` and
`/api/v1/openapi.json` are not served in production.

## 7. Structured logs (D44)

One JSON object per line on stdout: `ts`, `level`, `logger`, `message`, `request_id` (the `X-Request-ID`, also on audit rows and job
logs), plus structured fields — e.g. per request (`app.http`, message `request`): `method`, `route` (the template, e.g.
`/api/v1/farmers/{farmer_id}`), `status`, `duration_ms`, `user_id`; per job (`app.jobs`): `event`, `job_id`, `job_code`, `task_name`,
`environment`, `status`, `error_code`. Never logged: request bodies, query strings, headers, file contents. Redaction (defence in depth):
fields named like password / token / secret / authorization / cookie / api key / account / IFSC / routing / KYC / ID number / phone /
email / bank → `[REDACTED]`; bearer tokens, JWTs, Fernet tokens, `password=` pairs and credentials in Redis / database URLs are masked in
text. `LOG_FORMAT=text` is for local reading only (refused in production). Ship logs only to the approved, self-hosted platform (D43).

## 8. Metrics (D43) and alerts (D45)

`GET /metrics` (outside the API prefix) — OpenMetrics text by default, JSON with `?format=json`; bearer `METRICS_TOKEN` (≥ 32 chars, from
the secret store); without the token configured the endpoint does not exist. Values are per process (the monitoring platform aggregates).
No vendor is chosen; OpenMetrics is an open format most self-hosted platforms (or an OpenTelemetry collector) can scrape.

| Metric | Type | Meaning |
|---|---|---|
| `api_requests_total{method,route,status}` | counter | requests by route template and status class |
| `api_request_duration_seconds{method,route}` | summary | latency (`_count`, `_sum`) |
| `api_errors_total{method,route,status}` | counter | 5xx |
| `rate_limiter_degraded_total`, gauge `rate_limiter_degraded` | counter / gauge | fail-open events (D20) |
| `redis_errors_total{component=rate_limiter\|broker}` | counter | Redis failures |
| `job_failures_total{task,status}` | counter | attempts ending FAILED / RETRY_WAITING |
| gauges `jobs_queued`, `jobs_retry_waiting`, `jobs_claimed`, `jobs_running`, `jobs_failed`, `jobs_oldest_queued_age_seconds` | gauge | queue depth (SQL Server) |
| `av_scans_total`, `av_scan_failures_total`, `av_scan_duration_seconds` | counter / summary | antivirus |
| `storage_failures_total{operation}`, gauge `documents_quarantined` | counter / gauge | storage, quarantine |
| `readiness_failures_total{check,state}`, `db_failures_total`, gauge `database_up` | counter / gauge | dependencies |
| `orphan_objects_deleted_total` | counter | orphan cleanup |

The full alert catalogue (severities, signals, runbooks) is in [operations-runbook.md](operations-runbook.md) §5 (Phase 12B-III).

**Alert ownership: the Platform / DevOps team** (no named individuals; routing configured in the chosen platform). Alert categories —
thresholds are set by Platform / DevOps at deployment (no SLA numbers were decided, D31):
- **Page (critical):** readiness `not_ready` on any node; `database_up == 0`; sustained 5xx (`api_errors_total`); CRITICAL security events
  (malware detected, document integrity failure, environment mismatch — `security_events`); `jobs_failed` increasing.
- **Ticket (warning):** `rate_limiter_degraded == 1` or `redis_errors_total` increasing (limits not enforced — D20); broker publication
  failures; `jobs_oldest_queued_age_seconds` growing (no worker / broker); antivirus failures; storage failures; `documents_quarantined`
  increasing; latency regression against the team's baseline.

## 9. Notifications (D39 / D41 / D42)

In-app notifications are unchanged. **External delivery is deferred**: `NOTIFICATION_EXTERNAL_DELIVERY` accepts only `disabled`; SMTP is
the selected future channel and `SMTP_*` settings exist for configuration only (no credentials are invented); `SmtpChannel.send()` always
raises and nothing calls it. `app/integrations/notify.delivery_decision()` is the gate any future delivery must pass per message: explicit
opt-in (opt-out always wins), a preferred language, outside the recipient's quiet hours (deferred to their end), and delivery enabled.
Preference storage, consent wording and templates come with the delivery work (D41).

## 10. No simulated providers in production (D38)

Runtime adapters are MANUAL only (payment, payout, registry), `NoLimsAdapter` for laboratories, manual satellite evidence. Production
start-up refuses any `*_PROVIDER` named mock / fake / test / stub / dummy / simulated / demo. TEST doubles exist only in the test suite;
DEMO data uses the real services.

## 11. Query hardening (D32) and performance harness (D31 / D33)

The verified hot spots now filter in SQL with the same visibility rules (`app/security/scoping.org_predicate`): orders, marketplace
listings, refunds, finance projects. They accept optional `limit` (1–500) / `offset` while keeping their list response shape, and preload
related rows for their mappers. **Lazy expiry remains the correctness guarantee** (Phase 12A D5): the caller's due rows are found with one
query and expired (each re-checked under its lock) before the page is read. Behaviour note: a `status=` filter is applied after that expiry,
so `?status=PLACED` no longer lists an order that expired during the same request.

`tests/test_performance.py` (pytest, synthetic TEST data in the rolled-back test transaction, never DEMO / LIVE): rows loaded and SQL
statements do not grow with 1,500 other organizations' rows; results equal the previous Python rules for several principals; paging is
disjoint, ordered and complete; lazy expiry still runs. Timings are recorded as test properties for baselining — no SLA is asserted (D31).

## 12. Deployment prerequisites (real infrastructure integration pending deployment environment)
- Self-hosted Redis per §4, reachable over TLS; ACL users; monitoring.
- The self-hosted secret store and its agent rendering files into `SECRETS_DIR`.
- Reverse proxy: `TRUSTED_PROXIES`, appended `X-Forwarded-For`, body limit, timeouts.
- The self-hosted monitoring platform scraping `/metrics` and collecting JSON logs; alert routing to Platform / DevOps.
- SMTP only when D41 delivery is approved and built.
