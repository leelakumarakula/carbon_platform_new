"""Disk-space safety (Phase 12B-III). The development machine once reached 4 MB free and a source file was truncated mid-write; these
checks make the platform refuse disk-consuming work before the disk is exhausted, and report the condition to readiness and metrics.

Thresholds (DISK_WARN_FREE_MB / DISK_CRITICAL_FREE_MB) are operational defaults, not business SLAs.
"""
import shutil
import tempfile
from pathlib import Path

from app.core.config import get_settings


class DiskSpaceLow(RuntimeError):
    def __init__(self, path: str, free_mb: int, needed_mb: int, reserve_mb: int) -> None:
        super().__init__(f"Refused: {free_mb} MB free at {path}; this operation needs about {needed_mb} MB and {reserve_mb} MB must stay "
                         "free (DISK_CRITICAL_FREE_MB). Free disk space first (docs/operations-runbook.md, disk-space incident).")
        self.path, self.free_mb, self.needed_mb, self.reserve_mb = path, free_mb, needed_mb, reserve_mb


def free_mb(path: str | Path) -> int:
    p = Path(path)
    while not p.exists() and p.parent != p:
        p = p.parent
    return int(shutil.disk_usage(p).free // (1024 * 1024))


def watched_paths() -> dict[str, str]:
    """The volumes this process writes to: application directory, temporary files and (local backend) document storage."""
    from app.integrations.storage import local_root
    paths = {"app": str(Path(__file__).resolve().parents[2]), "temp": tempfile.gettempdir()}
    if get_settings().STORAGE_BACKEND == "local":
        paths["storage"] = str(local_root())
    return paths


def status() -> tuple[str, dict[str, int]]:
    """("ok" | "warn" | "critical", free MB per watched path)."""
    s = get_settings()
    free = {name: free_mb(p) for name, p in watched_paths().items()}
    low = min(free.values())
    state = "critical" if low < s.DISK_CRITICAL_FREE_MB else "warn" if low < s.DISK_WARN_FREE_MB else "ok"
    return state, free


def ensure_headroom(path: str | Path, needed_mb: int = 0, *, free: int | None = None) -> int:
    """Raise DiskSpaceLow unless `needed_mb` can be written at `path` while DISK_CRITICAL_FREE_MB stays free. Returns free MB.
    `free` lets a caller supply the free space as measured elsewhere (e.g. by SQL Server for its own volume)."""
    reserve = get_settings().DISK_CRITICAL_FREE_MB
    free = free_mb(path) if free is None else free
    if free - needed_mb < reserve:
        raise DiskSpaceLow(str(path), free, needed_mb, reserve)
    return free
