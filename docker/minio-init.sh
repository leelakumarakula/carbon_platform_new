#!/bin/sh
# Phase 12B (D4 / D5 / D8) — one-shot MinIO bootstrap for the docker-compose stack (development). Idempotent.
# Production buckets / identities are provisioned by the platform team with the same settings (docs/storage-and-scanning.md).
#   - one PRIVATE bucket per data environment: <prefix>-live, <prefix>-demo (anonymous access off)
#   - versioning enabled; SSE-S3 default encryption (the application also requests SSE-S3 on every write and refuses without it)
#   - application identity: get / put / list + read bucket versioning and policy. NO delete of any kind.
#   - deletion identity (orphan cleanup only): get / list / DeleteObject (a delete marker; earlier versions stay recoverable).
#     Neither identity may delete object versions (s3:DeleteObjectVersion) or change bucket configuration.
set -eu
PREFIX="${OBJECT_STORAGE_BUCKET_PREFIX:-carbon}"
: "${MINIO_ROOT_USER:?}" "${MINIO_ROOT_PASSWORD:?}" "${OBJECT_STORAGE_ACCESS_KEY:?}" "${OBJECT_STORAGE_SECRET_KEY:?}"

until mc alias set local "$MINIO_URL" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1; do sleep 2; done

RES_OBJ=""
RES_BKT=""
for ENV in live demo; do
  B="$PREFIX-$ENV"
  mc mb --ignore-existing "local/$B"
  mc version enable "local/$B"
  mc anonymous set none "local/$B"
  mc encrypt set sse-s3 "local/$B"
  RES_OBJ="$RES_OBJ\"arn:aws:s3:::$B/*\","
  RES_BKT="$RES_BKT\"arn:aws:s3:::$B\","
done
RES_OBJ="${RES_OBJ%,}"
RES_BKT="${RES_BKT%,}"

cat > /tmp/carbon-app.json <<EOF
{"Version": "2012-10-17", "Statement": [
  {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject"], "Resource": [$RES_OBJ]},
  {"Effect": "Allow", "Action": ["s3:ListBucket", "s3:GetBucketVersioning", "s3:GetBucketPolicy", "s3:GetBucketLocation"], "Resource": [$RES_BKT]}
]}
EOF
cat > /tmp/carbon-delete.json <<EOF
{"Version": "2012-10-17", "Statement": [
  {"Effect": "Allow", "Action": ["s3:GetObject", "s3:DeleteObject"], "Resource": [$RES_OBJ]},
  {"Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": [$RES_BKT]}
]}
EOF

mc admin policy create local carbon-app /tmp/carbon-app.json
mc admin user add local "$OBJECT_STORAGE_ACCESS_KEY" "$OBJECT_STORAGE_SECRET_KEY"
mc admin policy attach local carbon-app --user "$OBJECT_STORAGE_ACCESS_KEY" || true   # already attached on a re-run

if [ -n "${OBJECT_STORAGE_DELETE_ACCESS_KEY:-}" ] && [ -n "${OBJECT_STORAGE_DELETE_SECRET_KEY:-}" ]; then
  mc admin policy create local carbon-delete /tmp/carbon-delete.json
  mc admin user add local "$OBJECT_STORAGE_DELETE_ACCESS_KEY" "$OBJECT_STORAGE_DELETE_SECRET_KEY"
  mc admin policy attach local carbon-delete --user "$OBJECT_STORAGE_DELETE_ACCESS_KEY" || true
else
  echo "No deletion identity configured: orphan cleanup reports candidates and deletes nothing."
fi
echo "MinIO ready: buckets $PREFIX-live / $PREFIX-demo (private, versioned, SSE-S3)."
