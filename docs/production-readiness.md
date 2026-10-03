# Production-readiness checklist (end of Phase 12B)

Audience: the Platform / DevOps team and the project owners deciding on go-live. Two columns of truth: what this repository implements
**and has tested locally**, and what **requires deployment infrastructure** that does not exist on the development machine (no Docker,
WSL, Redis, MinIO, antivirus engine, secret store, monitoring platform or SMTP). Nothing in the second list has been tested.

## A. Implemented and tested locally
| Area | Evidence |
|---|---|
| Phases 1–12A workflows, RBAC, organization / project scoping, SoD, append-only records, environment isolation | full backend suite, E2E |
| Object storage adapter (S3 API, SigV4, SSE-S3 required, SHA-256, per-environment buckets, no-delete app identity) | TEST-only S3 stub |
| Antivirus boundary, append-only scan history, quarantine / rescan / release | TEST antivirus double |
| Orphan cleanup with locked re-check; local → MinIO migration command | two-connection race test; stub |
| Redis rate limiter (fail-open D20), D19 limits, trusted proxies, body-size limit | fakeredis, closed ports, API tests |
| Health live / ready, OpenAPI off in production, production configuration guards | tests |
| MultiFernet data-key rotation, JWT `kid` rotation | tests |
| Structured JSON logs (redaction), `/metrics` | tests |
| Notification boundary (delivery deferred, consent gate) | tests |
| SQL-side scoping + paging of hot listings; performance harness | `tests/test_performance.py` (baselines, no SLA) |
| Backup command (CHECKSUM, COMPRESSION, VERIFYONLY), restore drill, verify-restore | real SQL Server 2022 drills on the TEST database (COPY_ONLY, unencrypted) |
| Retention (60-day operational policies; append-only records untouched) | tests |
| Disk-space safeguards (readiness, uploads, drills, test-suite guard) | tests |
| SQL Agent backup-job template | generated commands parse-checked (not executed) |

## B. Requires deployment infrastructure (real infrastructure integration pending deployment environment)
| Item | Decision | Status |
|---|---|---|
| India-based production hosting (D50) | location decided | **not provisioned** |
| SQL Server production instance, FULL recovery, Agent jobs (`ops/sqlserver/backup-jobs.sql`) | D25 / D26 | **pending** |
| Backup encryption certificate + key in the secret store | D26 | **pending** |
| Off-host, object-locked (60 days) S3-compatible backup store + replica (`ops/minio/backup-and-replication.sh`) | D26 | **pending** |
| RPO 15 min / RTO 1 h confirmed by a production-sized restore drill | D25 / D27 | **pending** |
| Real MinIO (both sites), SSE-S3 with KES / KMS, versioning, replication | D2 / D5 / D28 | **pending** |
| Commercial antivirus scanning API: vendor selection, adapter, credentials | D13 (no vendor selected) | **pending** — production refuses to start without it |
| Self-hosted Redis with TLS, ACL users, `noeviction`, AOF, monitoring | D22 / D23 | **pending** |
| Self-hosted secret store rendering files into `SECRETS_DIR` | D30 (no vendor selected) | **pending** |
| Self-hosted monitoring platform (not Prometheus / Grafana) scraping `/metrics`, collecting JSON logs, 60-day retention, alert routing to Platform / DevOps | D43 / D45 (no vendor selected) | **pending** |
| Reverse proxy: TLS, `TRUSTED_PROXIES`, body limit, timeouts | D21 | **pending** |
| SMTP, only once external notification delivery is approved | D39 / D41 / D42 | **deferred** |
| Licensed / self-hosted map tiles | Phase 2 D6 | **pending** |

## C. Go-live gates (all must be true)
1. Every item in B provisioned and its runbook step executed once ([operations-runbook.md](operations-runbook.md)).
2. `/api/v1/health/ready` returns `ready` on every node (no `degraded`, no `not_ready`).
3. A restore drill from a production backup on the restore host passes `verify-restore` and its measured time is within the RTO.
4. `db_last_log_backup_age_seconds` stays below 900 for a week.
5. Every alert in the runbook's catalogue has fired once in a test and reached the Platform / DevOps team.
6. A real antivirus adapter detects the EICAR test file end to end in production configuration.

## D. Intentionally deferred (decided, not part of Phase 12B)
Calculation and report workers (D34 / D35), provider polling and webhooks (D36 / D37), external notification delivery (D41), in-app
event wiring for the remaining §23 events (D40), new registry / credit-calculation behaviour.
