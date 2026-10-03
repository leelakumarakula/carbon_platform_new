#!/bin/sh
# Phase 12B-III (D26 / D28) — MinIO configuration for backups and document-object recovery. DEPLOYMENT TEMPLATE: not executed on the
# development machine (no MinIO cluster there). Requires the MinIO client `mc` with two aliases configured by the operator:
#   primary  — the production MinIO (India region, D50) holding <prefix>-live / <prefix>-demo (docker/minio-init.sh settings);
#   replica  — a second, independent MinIO deployment / site (off-host) that receives replicated objects.
# No hostnames or credentials are invented here: every value comes from the environment.
set -eu
: "${PREFIX:?bucket prefix, e.g. carbon}" "${PRIMARY:?mc alias of the primary MinIO}" "${REPLICA:?mc alias of the replica MinIO}"
: "${SQL_BACKUP_ACCESS_KEY:?access key SQL Server uses for BACKUP TO URL}" "${SQL_BACKUP_SECRET_KEY:?its secret (from the secret store)}"
RETENTION_DAYS="${RETENTION_DAYS:-60}"                     # D26 / D48: 60-day backup retention

# 1. SQL Server backup bucket: object lock (immutability) in COMPLIANCE mode for the retention period, then lifecycle expiry.
#    Nobody — including administrators — can delete or overwrite a backup before its lock expires.
B="$PREFIX-sql-backups"
mc mb --ignore-existing --with-lock "$PRIMARY/$B"
mc retention set --default COMPLIANCE "${RETENTION_DAYS}d" "$PRIMARY/$B"
mc anonymous set none "$PRIMARY/$B"
mc encrypt set sse-s3 "$PRIMARY/$B"
mc ilm rule add --expire-days "$((RETENTION_DAYS + 1))" "$PRIMARY/$B"
cat > /tmp/carbon-sql-backup.json <<EOF
{"Version": "2012-10-17", "Statement": [
  {"Effect": "Allow", "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation"],
   "Resource": ["arn:aws:s3:::$B", "arn:aws:s3:::$B/*"]}
]}
EOF
mc admin policy create "$PRIMARY" carbon-sql-backup /tmp/carbon-sql-backup.json
mc admin user add "$PRIMARY" "$SQL_BACKUP_ACCESS_KEY" "$SQL_BACKUP_SECRET_KEY"
mc admin policy attach "$PRIMARY" carbon-sql-backup --user "$SQL_BACKUP_ACCESS_KEY" || true

# 2. Off-host copy of the backups: replicate the backup bucket to the replica site (object lock must be enabled there too).
mc mb --ignore-existing --with-lock "$REPLICA/$B"
mc retention set --default COMPLIANCE "${RETENTION_DAYS}d" "$REPLICA/$B"
mc replicate add "$PRIMARY/$B" --remote-bucket "$REPLICA/$B" --priority 1

# 3. Document buckets (D28): versioning is already on (docker/minio-init.sh). Replicate every version and delete marker to the replica,
#    and keep non-current versions for the retention period. Safe for restores: a document version row is never deleted, so any object a
#    database backup references is still referenced today and is never an orphan; only never-committed uploads become non-current.
for ENV in live demo; do
  SRC="$PREFIX-$ENV"
  mc mb --ignore-existing "$REPLICA/$SRC"
  mc version enable "$REPLICA/$SRC"
  mc encrypt set sse-s3 "$REPLICA/$SRC"
  mc replicate add "$PRIMARY/$SRC" --remote-bucket "$REPLICA/$SRC" --replicate "delete-marker,delete,existing-objects" --priority 1
  mc ilm rule add --noncurrent-expire-days "$RETENTION_DAYS" "$PRIMARY/$SRC"
done

# 4. Report replication status (feed into monitoring: failed / pending replication counts per bucket).
for BK in "$B" "$PREFIX-live" "$PREFIX-demo"; do mc replicate status "$PRIMARY/$BK" || true; done
echo "Backup bucket $B (object lock ${RETENTION_DAYS}d COMPLIANCE) and document-bucket replication configured."
