"""Object storage adapter (spec section 32). Business code depends only on `ObjectStorage`.

- LocalFileStorage: development/test only; files under LOCAL_STORAGE_ROOT.
- S3-compatible (MinIO / AWS S3): planned adapter behind the same interface. It is not implemented yet,
  because no S3 client library is installed in this environment; selecting STORAGE_BACKEND=s3 fails loudly
  rather than silently storing files somewhere else.
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings


class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...


class LocalFileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:  # keys are generated server-side; this is defence in depth
            raise ValueError("storage key escapes the storage root")
        return p

    def put(self, key: str, data: bytes, content_type: str) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".part")
        tmp.write_bytes(data)
        os.replace(tmp, p)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


@lru_cache
def get_storage() -> ObjectStorage:
    s = get_settings()
    if s.STORAGE_BACKEND == "local":
        if s.is_production:
            raise RuntimeError("STORAGE_BACKEND=local is not allowed in production; configure S3-compatible storage.")
        root = Path(s.LOCAL_STORAGE_ROOT) if s.LOCAL_STORAGE_ROOT else Path(__file__).resolve().parents[3] / "storage" / "local-dev"
        return LocalFileStorage(root)
    raise RuntimeError(f"STORAGE_BACKEND={s.STORAGE_BACKEND!r} is not implemented yet (S3 adapter planned for Phase 12).")
