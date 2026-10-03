"""Phase 12B D9 — copy document objects from local file storage into object storage (MinIO).

For every document version (both environments): read the local bytes, check them against the SHA-256 and size recorded in the
database, write them to the target under the SAME key (keys are unchanged, D4), then verify the target object (size, SHA-256,
server-side encryption). The local original is NEVER deleted or modified. Idempotent: an object already present and verified in the
target is skipped, so the command can be re-run after an interruption. Nothing in the database changes.
"""
import hashlib
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.storage import LocalFileStorage, ObjectStorage, StorageError
from app.models import DocumentVersion


@dataclass
class MigrationReport:
    versions: int = 0
    copied: int = 0
    already_present: int = 0
    missing_source: list[str] = field(default_factory=list)
    source_checksum_mismatch: list[str] = field(default_factory=list)
    target_failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.missing_source or self.source_checksum_mismatch or self.target_failures)

    def as_dict(self) -> dict[str, object]:
        return {"versions": self.versions, "copied": self.copied, "already_present": self.already_present,
                "missing_source": self.missing_source, "source_checksum_mismatch": self.source_checksum_mismatch,
                "target_failures": self.target_failures, "ok": self.ok}


def migrate_local_to(db: Session, source: LocalFileStorage, target: ObjectStorage, *, dry_run: bool = False,
                     batch_size: int = 500) -> MigrationReport:
    if target.name == source.name:
        raise StorageError("STORAGE_MIGRATION_SAME_BACKEND", "The migration target must be the object store, not local storage.")
    rep = MigrationReport()
    last = ""
    while True:
        rows = db.execute(select(DocumentVersion.storage_key, DocumentVersion.checksum_sha256, DocumentVersion.size_bytes,
                                 DocumentVersion.mime_type)
                          .where(DocumentVersion.storage_key > last).order_by(DocumentVersion.storage_key).limit(batch_size)).all()
        db.commit()
        if not rows:
            return rep
        for key, sha, size, mime in rows:
            rep.versions += 1
            try:
                target.verify(key, sha, size)
                rep.already_present += 1
                continue
            except StorageError:
                pass                                            # absent (or not yet verified): copy it
            try:
                data = source.get(key)
            except (OSError, StorageError):
                rep.missing_source.append(key)
                continue
            if len(data) != size or hashlib.sha256(data).hexdigest() != sha:
                rep.source_checksum_mismatch.append(key)        # never copy bytes that do not match the record
                continue
            if dry_run:
                rep.copied += 1
                continue
            try:
                target.put(key, data, mime)
                target.verify(key, sha, size)
                rep.copied += 1
            except (OSError, StorageError) as e:
                rep.target_failures.append(f"{key}: {getattr(e, 'code', type(e).__name__)}")
        last = rows[-1][0]
