"""Restore drill (Phase 12B-III, D27): back up a source database (COPY_ONLY — the production backup chain is untouched), verify the backup,
restore it into a SCRATCH database (`*_restoretest`), run verify-restore against it (row counts compared with the source), then drop
the scratch database and delete the drill's own local backup file. Timings are recorded as locally measured evidence for the RTO
discussion — they are not a production RTO measurement (production data volume, off-host storage and hardware differ).

Refused: production (`APP_ENV=production`); a scratch name that is not `*_restoretest` or equals the application database; too little
disk space for the backup plus the restored files while DISK_CRITICAL_FREE_MB stays free.
"""
import time
from typing import Any

from app.ops import sqlserver as sq
from app.ops.verify_restore import verify_restore


def restore_drill(source: str, scratch: str | None = None, *, from_backup: str | None = None, keep_backup: bool = False,
                  objects: int = 0) -> dict[str, Any]:
    sq.check_name(source)
    scratch = sq.check_scratch(scratch or f"{source}{sq.SCRATCH_SUFFIX}")
    timings: dict[str, float] = {}
    out: dict[str, Any] = {"source": source, "scratch": scratch, "timings_seconds": timings}
    eng = sq.master_engine()
    created_backup = None
    try:
        if not sq.exists(eng, source):
            raise sq.UnsafeTarget(f"source database {source!r} does not exist")
        size = sq.used_mb(eng, source)
        data_dir = sq.default_backup_dir(eng)
        sq.ensure_server_headroom(eng, data_dir, size * 2)        # backup (<= used size) + restored files (= used size)
        t0 = time.monotonic()
        if from_backup:
            destination = from_backup
            sq.verify_backup(eng, destination)
            out["backup"] = {"destination": destination, "provided": True, "verified": True}
        else:
            b = sq.backup(source, "full", copy_only=True, verify=True)
            destination = created_backup = b.destination
            out["backup"] = b.as_dict()
        timings["backup_and_verify"] = round(time.monotonic() - t0, 2)
        t1 = time.monotonic()
        sq.restore_to_scratch(eng, destination, scratch)
        timings["restore"] = round(time.monotonic() - t1, 2)
        t2 = time.monotonic()
        report = verify_restore(scratch, compare_with=source, objects=objects)
        timings["verify"] = round(time.monotonic() - t2, 2)
        timings["total"] = round(time.monotonic() - t0, 2)
        out["verification"] = report.as_dict()
        out["ok"] = report.ok
        return out
    finally:
        try:
            sq.drop_scratch(eng, scratch)
            out["scratch_dropped"] = not sq.exists(eng, scratch)
        finally:
            if created_backup and not keep_backup:
                sq.delete_backup_file(eng, created_backup)
                out["backup_file_deleted"] = True
            eng.dispose()
