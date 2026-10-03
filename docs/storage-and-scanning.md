# Document storage and antivirus scanning (Phase 12B-I)

Audience: Platform / DevOps team and security administrators. Decisions D2–D17 of `docs/phase-12b-decision-lock.md`.

## 1. Object storage (MinIO via S3 APIs)

| Item | Implementation |
|---|---|
| Backend | `STORAGE_BACKEND=s3` → `S3ObjectStorage` (`app/integrations/storage.py`). `local` is development / test only; production refuses to start with it. |
| Client | Python standard library only (`app/integrations/s3.py`): AWS Signature V4, path-style requests, `http.client`, TLS with optional private CA (`OBJECT_STORAGE_CA_CERT`). No boto3 / MinIO SDK (D3). Verified against the AWS-documented example signatures (`tests/test_storage_av.py`). |
| Buckets | One private bucket per data environment: `<OBJECT_STORAGE_BUCKET_PREFIX>-live`, `<prefix>-demo`. A key's environment prefix selects the bucket, so a LIVE key can never be written to or read from the DEMO bucket (D4 / D49). |
| Keys | Server-generated only: `<live\|demo>/<YYYY>/<MM>/<32 hex>`. Anything else is refused before a request is sent (no traversal, no client-chosen names). Existing keys are unchanged by the migration. |
| Encryption | Every PUT requests SSE-S3 (`x-amz-server-side-encryption: AES256`); a response without the SSE confirmation is refused (`STORAGE_NOT_ENCRYPTED`), and verification re-checks it (D5). |
| Integrity | The SHA-256 of the bytes is the signed payload hash (MinIO rejects a body that does not match) and is stored as `x-amz-meta-sha256`. Order: **write object → verify (HEAD: size, SHA-256, SSE) → database rows → commit** (D7 / D11). A storage failure leaves the database untouched (HTTP 503 `STORAGE_UNAVAILABLE`). Every download re-hashes the bytes against the database checksum. |
| Downloads | Streamed through the API only: authorization by the owning entity, audited `DOCUMENT_DOWNLOADED`, `Content-Disposition: attachment`, `nosniff`, sandbox CSP, `no-store` (D6). No presigned URLs. |
| Deletion | The application identity has **no delete permission** (D8). Only the orphan-cleanup job deletes, with the separate `OBJECT_STORAGE_DELETE_*` identity; without it, deletion is disabled and candidates are only reported. Versioning keeps every deleted / overwritten object recoverable (delete markers). |
| Health | `S3ObjectStorage.health()` reports a bucket without versioning or with a public bucket policy (used by the Phase 12B-II readiness probe). |

### Provisioning (per environment)

`docker/minio-init.sh` is the reference (used by `docker-compose.yml`, development): buckets, `mc version enable`, `mc anonymous set none`,
`mc encrypt set sse-s3`, an application policy (GetObject, PutObject, ListBucket, GetBucketVersioning, GetBucketPolicy) and a deletion
policy (GetObject, DeleteObject, ListBucket). Neither identity has `s3:DeleteObjectVersion` or bucket-configuration rights.
Production SSE-S3 needs MinIO KMS / KES with a managed key (the compose file uses the single-key development mode).

### Local → MinIO migration (D9)

```
STORAGE_BACKEND=s3 OBJECT_STORAGE_...=... python manage.py storage-migrate --dry-run
STORAGE_BACKEND=s3 OBJECT_STORAGE_...=... python manage.py storage-migrate
```
For every document version: the local bytes are checked against the database SHA-256 / size, written under the same key, then verified
in MinIO. The local original is never deleted or modified. Re-runnable (already-present verified objects are skipped). Exit code 1 lists
missing sources, checksum mismatches (never copied) or target failures. Run it before switching `STORAGE_BACKEND` on a server that has
local documents; keep the local directory until the backup policy (12B-III) covers MinIO.

## 2. Orphan cleanup (D10)

Job `ORPHAN_FILE_SCAN` (`maintenance.scan_orphan_files`, every `JOB_ORPHAN_SCAN_INTERVAL`). An object is deleted only if:
1. its key is server-generated (anything else is counted as `unrecognized_keys` and never touched);
2. no document version references it;
3. it is older than `JOB_ORPHAN_GRACE_HOURS` (uploads in flight are younger);
4. a re-check **inside the deletion transaction** under `UPDLOCK, HOLDLOCK` on the unique storage-key index still finds no reference. A
   concurrent upload transaction that inserted a version for that key makes the job wait; if it commits, nothing is deleted
   (`became_referenced`), proven with two real connections in `tests/test_storage_concurrency.py`.

Each deletion is audited (`STORAGE_ORPHAN_DELETED`, entity `storage_object`) and counted (`orphan_objects_deleted_total`).

## 3. Antivirus (D12–D17)

| Environment | Behaviour |
|---|---|
| TEST | EICAR signature + the test double in `tests/av_fixture.py` (registered by the test suite only; marked `is_test_double`). |
| Development / DEMO | `MALWARE_SCANNER=signature`: EICAR is blocked; everything else is recorded **NOT_SCANNED** (explicitly not a clean result). |
| LIVE (production) | A real commercial scanner adapter is mandatory. Startup refuses `signature`, a missing `ANTIVIRUS_ENDPOINT` / `ANTIVIRUS_API_KEY`, and any test double. A LIVE upload while the scanner is unavailable is refused (503 `SCANNER_UNAVAILABLE`); an outage is never treated as clean. |

**No vendor has been selected (D13).** The boundary is `AntivirusScanner` in `app/integrations/malware.py` (`scan(data, filename) ->
ScanResult`, `health()`); the vendor adapter is registered with `register_scanner("<name>", factory)` at deployment and configured with
`MALWARE_SCANNER`, `ANTIVIRUS_ENDPOINT`, `ANTIVIRUS_API_KEY`, `ANTIVIRUS_TIMEOUT_SECONDS`. Until it exists, production does not start:
*implementation complete; real infrastructure integration pending deployment environment.*

### Flow
- **Upload:** scanned synchronously before anything is written. INFECTED → refused (422 `MALWARE_DETECTED`, CRITICAL security event,
  nothing stored). ERROR (outside production LIVE) → stored, document **QUARANTINED**, `DOCUMENT_RESCAN` job queued.
- **History:** every scan (upload, background rescan, release rescan) is a new row in `document_scans` (append-only trigger; downgrade
  refused while rows exist), with SHA-256, result, provider, engine version, threat, trigger, job, actor and duration.
- **Background rescan:** job `DOCUMENT_RESCAN` (`maintenance.rescan_documents`) — one document on request, or every document of the
  environment whose current version has no CLEAN scan (skipped while only the signature scanner is configured). INFECTED quarantines
  (CRITICAL `DOCUMENT_RESCAN_INFECTED`). A rescan never releases.
- **Release (security.manage):** only a QUARANTINED document; every version is rescanned at that moment; released only if all results are
  CLEAN. INFECTED, ERROR and NOT_SCANNED keep it quarantined (`DOCUMENT_RELEASE_REFUSED` audit + 409). Reason mandatory; audited.

### API (`/api/v1/evidence/documents`)
| Endpoint | Permission |
|---|---|
| `GET /quarantined` | security.read (own environment) |
| `GET /{id}/scans` | security.read |
| `POST /{id}/quarantine` `{reason}` | security.manage |
| `POST /{id}/rescan` → 202 `{job_id}` | security.manage |
| `POST /{id}/release` `{reason}` | security.manage |

`DocumentOut.scan_state`: `PENDING_SCAN` (accepted before Phase 12B) · `CLEAN` · `NOT_SCANNED` · `SCANNER_UNAVAILABLE` · `INFECTED` ·
`QUARANTINED`. UI: Security → Document quarantine; document lists show the state and hide download for quarantined files.

## 4. Deployment prerequisites (not available in local development)
- MinIO cluster in the India region (D50) with TLS, KMS/KES for SSE-S3, versioning, the two identities above, and replication / backup
  (12B-III runbook).
- The commercial antivirus vendor selection, its adapter and credentials.
- Run `manage.py storage-migrate` for existing local documents.
