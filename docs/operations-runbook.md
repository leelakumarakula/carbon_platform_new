# Operations runbook (Phase 12B-III)

Audience: the **Platform / DevOps team**, which owns production alerts and first response (D45). No individuals, phone numbers or paging
contracts are named here; the team configures its own routing in the self-hosted monitoring platform (D43, no vendor selected).
Related: [runtime-hardening.md](runtime-hardening.md) (rate limits, Redis, secrets, health, logs, metrics),
[storage-and-scanning.md](storage-and-scanning.md), [object-storage-recovery.md](object-storage-recovery.md),
[background-jobs.md](background-jobs.md), [production-readiness.md](production-readiness.md).

All commands run from `backend/` with the production configuration (secrets from `SECRETS_DIR`). Commands that change data say so.

## 1. Recovery objectives (D25)

| | Target | Locally tested capability (development machine) | Deployment-dependent |
|---|---|---|---|
| **RPO** | **15 minutes** | Backup / `RESTORE VERIFYONLY` / restore mechanics work on SQL Server 2022 (COPY_ONLY drills). | Log backups every 5 min to an off-host, object-locked store; the gauge `db_last_log_backup_age_seconds` proves it continuously. |
| **RTO** | **1 hour** | A full drill of the test database (≈ 21 MB compressed) — backup + verify + restore + verify-restore — completed in ≈ 2–3 s. That is **not** a production RTO measurement. | Restore of the production full + latest diff + log chain from the backup store, measured by quarterly drills on production-sized data. |

The targets are **designed** for; they are achieved only when the deployment provides the infrastructure below and drills confirm the times.

## 2. SQL Server backup (D26)

- **Method:** native SQL Server backups `WITH CHECKSUM, COMPRESSION, ENCRYPTION (AES_256, server certificate)` written directly
  **off-host** with `BACKUP TO URL` (SQL Server 2022 S3 connector) into an S3-compatible bucket with **object lock (COMPLIANCE, 60 days)**
  — immutable: not even an administrator can delete or alter a backup before it expires — replicated to a second site
  (`ops/minio/backup-and-replication.sh`).
- **Schedule** (`ops/sqlserver/backup-jobs.sql`, SQL Server Agent): LOG every 5 min · DIFF every 6 h · FULL weekly; FULL / DIFF are
  followed by `RESTORE VERIFYONLY`; msdb history older than 60 days is cleaned daily. Job failures notify the Platform/DevOps operator.
- **Retention:** 60 days (D26 / D48), enforced by the bucket lock + lifecycle expiry. Backup deletion is entirely separate from
  application-data retention: the application never deletes backups.
- **Keys:** the backup certificate **and its private key** are exported to the secret store; without them no backup can be restored.
  Test the certificate restore on the restore host.
- **Ad-hoc backup** (e.g. before a risky migration): `python manage.py backup --database <db> --type full`
  (production refuses unless `BACKUP_ENCRYPTION_CERT` and `BACKUP_URL` are set; non-production writes to the instance backup directory
  after a disk-headroom check and runs `RESTORE VERIFYONLY`). `--copy-only` leaves the backup chain untouched.
- **Development:** the development database uses the SIMPLE recovery model (D29; never applied to production). Local drills are
  **unencrypted** COPY_ONLY backups and say so in their output.

## 3. SQL Server restore (point in time)

Never restore over the live database in a drill (D27). For a real recovery, restore into a new database name first when possible.
1. Freeze writes: stop the API / workers (`/health/ready` will fail database checks during the restore).
2. On the restore host: import the backup certificate from the secret store; create the `s3://` credential for the backup bucket.
3. Restore the chain `WITH NORECOVERY`: latest FULL → latest DIFF before the target time → every LOG after it, the last one
   `WITH STOPAT = '<UTC time>', RECOVERY`. Use `RESTORE FILELISTONLY` and `MOVE` for new file locations.
4. Run `python manage.py verify-restore --database <restored_db> --objects 50 --checkdb --report restore-<date>.json`
   (exit code 0 required; keep the report with the incident record).
5. Point the application at the restored database (secret store `DATABASE_URL`), start the API, check `/api/v1/health/ready`, then
   workers (`python manage.py jobs-recover` republishes queued jobs).
6. Documents: object storage is restored separately and needs no rollback — see [object-storage-recovery.md](object-storage-recovery.md).

## 4. Restore verification (D27)

`python manage.py verify-restore --database <name> [--compare-with <source>] [--objects N] [--checkdb] [--report file.json]` — read-only
(one rolled-back probe), exit code 1 on any failure. Checks: connectivity on exactly that database; migration head; every table, column,
index, constraint and trigger of the committed schema manifest (`app/ops/schema_manifest.json`); no disabled trigger; append-only
trigger behaviour; credit-ledger conservation (OPEN positions = batch quantity, no unposted entry); settlement reproducibility (hash,
figures, entitlements, inputs); calculation-report hashes; organization-scoping predicates; optionally document objects (size +
SHA-256) and DBCC CHECKDB; per-table row counts (compared with a source when given).

**Repeatable drill:** `python manage.py restore-drill --source <db> [--from-backup <file or s3 url>] [--objects N] --report drill.json`
backs up (COPY_ONLY) or takes the given backup, verifies it, restores into `<db>_restoretest`, runs verify-restore comparing row counts,
then drops the scratch database and deletes its own backup file. Refused in production and for any scratch name not ending in
`_restoretest`; refused without disk headroom. Run monthly on a non-production restore host against a production backup
(`--from-backup`), and record the timings as the RTO evidence. After every schema migration regenerate the manifest:
`python manage.py schema-manifest --database <db at head>` (the test suite fails if it is stale).

## 5. Monitoring and alerts (D43 / D44 / D45)

Signals: JSON logs (stdout), `GET /metrics` (OpenMetrics / JSON, bearer token), `GET /api/v1/health/ready`, `security_events`, SQL Agent job
history, MinIO replication status. Owner of every alert: **Platform / DevOps team**. Thresholds marked *(team)* are set by the team at
deployment from observed baselines — no SLA numbers were decided (D31).

| Alert | Signal | Warning | Critical | Runbook |
|---|---|---|---|---|
| Database unavailable | `database_up == 0`; readiness `database` failed | — | any occurrence | §6.13 |
| Database backup failure | Agent job failure; `db_last_log_backup_age_seconds` | log age > 10 min | log age > 15 min (RPO), full age > 8 days, any failed job | §6.2 |
| Restore verification failure | `verify-restore` / `restore-drill` exit code ≠ 0 | — | any failure | §6.4 |
| Redis unavailable | `rate_limiter_degraded == 1`, `redis_errors_total` rising, readiness `broker` / `rate_limiter` degraded | any occurrence (limits not enforced, D20) | > 15 min | §6.6 |
| Redis insecure configuration | readiness `failed` on broker / rate_limiter (no noeviction / AOF) | — | any | §6.6 |
| Background-job backlog | `jobs_oldest_queued_age_seconds`, `jobs_queued` | age > 2 × schedule interval *(team)* | no progress for 1 h | §6.9 |
| Repeated job failure | `job_failures_total{status="FAILED"}`, `jobs_failed` rising | any FAILED job | same task failing repeatedly | §6.9 |
| Storage unavailable | readiness `storage` degraded; `storage_failures_total` rising | any | > 15 min, or readiness `failed` (public bucket / versioning off) | §6.14 |
| Antivirus unavailable | readiness `antivirus` degraded; LIVE uploads answer 503 `SCANNER_UNAVAILABLE` | any | > 15 min | §6.8 |
| Antivirus scan failures | `av_scan_failures_total` rising; `documents_quarantined` rising | rate above baseline *(team)* | INFECTED detections (`security_events` CRITICAL) | §6.8 |
| Readiness failure | `/health/ready` 503; `readiness_failures_total{state="failed"}` | — | any node not ready | §6.12 |
| API error-rate anomaly | `api_errors_total` / `api_requests_total`; latency `api_request_duration_seconds` | above baseline *(team)* | sustained 5xx | §6.15 |
| Disk space | `disk_free_mb_*`; readiness `disk` | < `DISK_WARN_FREE_MB` (2048) → degraded | < `DISK_CRITICAL_FREE_MB` (1024) → node not ready | §6.10 |
| Backup retention failure | backup bucket lock / lifecycle missing; backups older than 61 days present, or none younger than 1 day | — | any | §6.2 |
| Object-storage replication failure | `mc replicate status` failed / pending counts | pending above baseline *(team)* | any failed replication | §6.5 |
| Security events | `security_events` CRITICAL (malware, integrity failure, environment mismatch, refresh-token reuse) | — | any | §6.16 |
| Monitoring outage | the platform's own scrape / heartbeat check | missed scrapes | no data for 15 min | §6.11 |

## 6. Runbooks

Every runbook starts with: confirm the alert, note the time, open an incident record, and keep the JSON log lines (`request_id`) and
command outputs with it. Escalate per §6.16.

1. **Deployment prerequisites** — [production-readiness.md](production-readiness.md); then `python manage.py migrate`,
   `python manage.py seed-reference`, `python manage.py schema-manifest` is **not** run in production (the manifest is committed).
2. **SQL Server backup** — check SQL Agent job history for the failed step; confirm the `s3://` credential is valid and the backup
   bucket reachable; confirm the certificate exists (`SELECT name FROM sys.certificates`). Re-run the job. While log backups fail, the
   transaction log grows (FULL recovery): watch the data volume. If the RPO is breached, record the window.
3. **SQL Server restore** — §3.
4. **Restore verification** — read the failing check in the JSON report: `migration_head` (restore of the wrong backup or a database
   needing `migrate`), `tables`/`triggers` (incomplete restore), `ledger_conservation` / `settlement_reproducibility` (data corruption —
   do not put the database into service; restore an earlier point), `document_objects` (object storage — §6.5).
5. **MinIO / object recovery** — [object-storage-recovery.md](object-storage-recovery.md).
6. **Redis recovery** — the platform stays correct without Redis: rate limiting fails open (logged, `rate_limiter_degraded`), jobs stay
   QUEUED in SQL Server. Restore Redis (TLS, ACL users, `noeviction`, AOF — runtime-hardening §4), then `python manage.py jobs-recover`.
   Redis holds no business data: an empty Redis after recovery is fine.
7. **Secret-store recovery** — the API reads secrets at start-up from `SECRETS_DIR`; running processes keep working. Restore the secret
   store from its own backup, re-render the files, restart processes. Lost `DATA_ENCRYPTION_KEY` = encrypted bank numbers unreadable;
   lost backup certificate = backups unrestorable: both must be in the secret store's backup. Key rotation: runtime-hardening §5.
8. **Antivirus outage** — LIVE uploads are refused (503) while the scanner is down; nothing unscanned is accepted (D14). When it returns,
   trigger rescans: `POST /api/v1/jobs/trigger {"job_type": "DOCUMENT_RESCAN"}` (Platform admin). Quarantined documents are released only
   by security users after a clean rescan (storage-and-scanning.md).
9. **Background-job outage** — `GET /api/v1/jobs/status` (database, broker, worker heartbeat). Workers down: restart them (Linux,
   `-Q default,maintenance`, exactly one beat). Broker down: §6.6. Then `python manage.py jobs-recover`. FAILED jobs: inspect the attempt
   error in Administration → Background jobs; retry only after fixing the cause. Lazy expiry keeps workflows correct meanwhile.
10. **Disk-space incident** — readiness `disk` degraded / failed, uploads answer 503 `DISK_SPACE_LOW`, drills and local backups refuse to
    start. Do not delete database, log or backup files by hand. Free space safely: expired temporary files, old log files of the host,
    package / build caches. On developer machines, editor caches are a known culprit (the VS Code extension-package cache
    `%APPDATA%\Code\CachedExtensionVSIXs` reached 4 GB here and exhausted the disk, truncating a file being written). The test suite
    refuses to start below 1 GB free. Never resume heavy work (tests, drills, backups) below `DISK_CRITICAL_FREE_MB`.
11. **Monitoring outage** — the platform keeps working; JSON logs remain on stdout / the log collector and `security_events` in SQL
    Server. Restore the monitoring platform, then review the gap using `api_access_logs` (60 days), `security_events` and job history.
12. **Readiness failure** — read `/api/v1/health/ready` (outside production the `details` field explains; in production check the node's
    logs for `readiness check <name> <state>`). `database` failed → §6.13; `storage` failed (public policy / versioning off) → fix the
    bucket; `antivirus` failed → scanner adapter not configured; `broker` / `rate_limiter` failed → Redis policy; `disk` failed → §6.10.
13. **Database connectivity failure** — check SQL Server service / failover, network, the login (secret store), connection pool
    exhaustion in logs. The API answers 5xx for data requests; `/health/live` stays up (no restart loop).
14. **Storage outage** — uploads / downloads answer 503 `STORAGE_UNAVAILABLE`; the rest of the platform works. Restore MinIO; nothing to
    replay (an upload is either fully stored and recorded or not recorded at all). Then `object-storage-recovery.md` verification.
15. **Rollback / recovery of a release** — application rollback = redeploy the previous image; database migrations are forward-only in
    production: restore the pre-deployment backup (§3, taken with `manage.py backup --type full --copy-only` before migrating) when a
    migration must be undone; `alembic downgrade` guards refuse to drop data and must not be used against production data.
16. **Escalation** — first response: Platform / DevOps (owner of all alerts). Security events (malware, integrity, environment mismatch,
    token reuse): Platform / DevOps involves the security administrators (role SECURITY_ADMIN). Data correctness (ledger, settlements):
    involve the finance / registry owners before any data change. Never "fix" append-only records in place.

## 7. Retention (D48)

| Category | Retention | How |
|---|---|---|
| `api_access_logs` (IP, user agent) | 60 days | `RETENTION_PURGE` job (daily), per environment |
| Read in-app notifications | 60 days after reading | `RETENTION_PURGE`; unread notifications are kept |
| Stopped / dead worker heartbeats | 60 days | `RETENTION_PURGE` (LIVE job) |
| Temporary upload files (`*.part`) | 24 h | `RETENTION_PURGE` (LIVE job, local storage only) |
| Application logs and metrics | 60 days | monitoring platform configuration (deployment) |
| SQL Server backups | 60 days | object lock + lifecycle on the backup bucket |
| Non-current object versions | 60 days | MinIO lifecycle (`ops/minio/backup-and-replication.sh`) |
| Audit, workflow, security, login records; job history and attempts; antivirus scan history; documents and versions; credit ledger, registry, verification, calculation, methodology, finance and payout records | **never purged** | append-only / immutable by design, legally and architecturally required (D48); not touched by any job |

Each purge is batched (bounded transactions), idempotent and audited (`RETENTION_PURGED`, entity `retention_policy`, with counts);
production refuses `OPERATIONAL_RETENTION_DAYS` below 60.
