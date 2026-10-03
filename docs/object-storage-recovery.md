# Object-storage recovery (Phase 12B-III, D28)

Audience: Platform / DevOps. Document objects live in MinIO (`<prefix>-live`, `<prefix>-demo`; [storage-and-scanning.md](storage-and-scanning.md)).
The database holds each object's key, size and SHA-256 (`document_versions`, append-only); the object holds the bytes.

## 1. Why database and object restores stay consistent
- The application never deletes or overwrites a referenced object: keys are unique per upload, document versions are never deleted,
  and the orphan-cleanup job deletes only objects no version references (and only with the separate deletion identity).
- So every object referenced by **any** database backup is still referenced today and still exists. Restoring the database to an
  earlier point never needs an object rollback; objects newer than the restored database become orphans and are cleaned up after the
  grace period.
- Versioning keeps every overwritten or deleted object recoverable; non-current versions are kept 60 days.

## 2. Protection (deployment — `docker/minio-init.sh`, `ops/minio/backup-and-replication.sh`)
- Versioning on both buckets; SSE-S3 encryption; no public access.
- Replication of every version and delete marker to an independent second MinIO site (`mc replicate add … --replicate
  "delete-marker,delete,existing-objects"`); replication status monitored (`mc replicate status`, alert on failed / growing pending).
- Lifecycle: non-current versions expire after 60 days (D48); current objects never expire.
- India-region hosting for both sites (D50).

## 3. Recovery procedures
**A single object deleted or damaged** (detected by a download `DOCUMENT_INTEGRITY_FAILURE`, verify-restore `document_objects`, or the
scan job): list versions `mc ls --versions <alias>/<bucket>/<key>`; restore the version whose SHA-256 equals the database value
(`mc cp --version-id <id> <alias>/<bucket>/<key> <alias>/<bucket>/<key>`), or remove a wrong delete marker (`mc rm --version-id
<marker-id>`). Verify with `python manage.py verify-restore --database <db> --objects <n>`.

**Primary site lost:** promote the replica (point `OBJECT_STORAGE_ENDPOINT` at it in the secret store), restart the API, run
`python manage.py verify-restore --database <db> --objects 200`, then re-establish replication in the other direction.

**Bucket-wide restore to a point in time:** use MinIO's versioned rewind (`mc cp --rewind <time> --recursive …` into a new bucket),
verify, then switch the bucket prefix.

**Moving from local storage:** `python manage.py storage-migrate [--dry-run]` (copy + verify; local originals are never deleted).

## 4. Verification
- Every download re-hashes the bytes against the database SHA-256 (tampering is refused and reported).
- `verify-restore --objects N` checks the newest N document versions (size + SHA-256 via the storage adapter).
- The S3 protocol behaviour (SigV4, SSE, versioning, delete identity, verification) is tested against the TEST-only S3 stub
  (`tests/s3_stub.py`); **real MinIO replication and versioned recovery have not been exercised** — the development machine has no MinIO.
  They are deployment verification items ([production-readiness.md](production-readiness.md)).
