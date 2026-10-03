"""Object storage adapter (spec section 32; Phase 12B D2–D11). Business code depends only on `ObjectStorage`.

- LocalFileStorage: development / test only (refused in production); files under LOCAL_STORAGE_ROOT.
- S3ObjectStorage: MinIO through the S3 API (stdlib SigV4 client, `integrations/s3.py`). One private, versioned bucket per data
  environment (`<prefix>-live`, `<prefix>-demo`); every object is written with SSE-S3 and its SHA-256 in the signed payload hash and in
  `x-amz-meta-sha256`; a response without server-side encryption is refused. Keys are never chosen by a client: only server-generated
  keys of the form `<live|demo>/<YYYY>/<MM>/<32 hex>` are accepted, and a key's environment prefix selects its bucket, so a key can never
  reach another environment's bucket and no path can traverse.
- Deletion is NOT part of the application identity (D8): `get_deletion_storage()` returns an adapter built from the separate
  OBJECT_STORAGE_DELETE_* identity, used only by the orphan-deletion job; without it, deletion is disabled.
"""
import hashlib
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings
from app.integrations.s3 import S3Client, S3Error

KEY_PATTERN = re.compile(r"^(live|demo)/\d{4}/\d{2}/[0-9a-f]{32}$")
ENVIRONMENTS = ("live", "demo")


class StorageError(RuntimeError):
    """Storage refused or failed an operation (never silently ignored)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class StoredObject:
    key: str
    size_bytes: int
    modified_at: datetime          # naive UTC
    sha256: str | None = None      # recorded at upload (S3 metadata); None for local files


def validate_key(key: str) -> str:
    if not KEY_PATTERN.match(key or ""):
        raise StorageError("INVALID_STORAGE_KEY", "Storage keys are server-generated: <live|demo>/<YYYY>/<MM>/<32 hex>.")
    return key


class ObjectStorage(Protocol):
    name: str

    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def stat(self, key: str) -> StoredObject | None: ...
    def verify(self, key: str, sha256: str, size: int) -> None: ...
    def iter_objects(self, prefix: str) -> Iterator[StoredObject]: ...
    def health(self) -> list[str]: ...


class DeletionStorage(Protocol):
    def delete(self, key: str) -> None: ...


class LocalFileStorage:
    name = "local"

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:  # keys are generated server-side; this is defence in depth
            raise StorageError("INVALID_STORAGE_KEY", "storage key escapes the storage root")
        return p

    def put(self, key: str, data: bytes, content_type: str) -> None:
        p = self._path(validate_key(key))
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".part")
        tmp.write_bytes(data)
        os.replace(tmp, p)

    def get(self, key: str) -> bytes:
        return self._path(validate_key(key)).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(validate_key(key)).exists()

    def stat(self, key: str) -> StoredObject | None:
        p = self._path(validate_key(key))
        if not p.is_file():
            return None
        st = p.stat()
        return StoredObject(key, st.st_size, datetime.fromtimestamp(st.st_mtime, timezone.utc).replace(tzinfo=None))

    def verify(self, key: str, sha256: str, size: int) -> None:
        data = self.get(key)
        if len(data) != size or hashlib.sha256(data).hexdigest() != sha256:
            raise StorageError("STORAGE_VERIFY_FAILED", "The stored object does not match its SHA-256 / size.")

    def iter_objects(self, prefix: str) -> Iterator[StoredObject]:
        base = self._path(prefix) if prefix else self.root
        if not base.is_dir():
            return
        for p in base.rglob("*"):
            if p.is_file():
                st = p.stat()
                yield StoredObject(p.relative_to(self.root).as_posix(), st.st_size,
                                   datetime.fromtimestamp(st.st_mtime, timezone.utc).replace(tzinfo=None))

    def delete(self, key: str) -> None:
        p = self._path(validate_key(key))
        if p.exists():
            p.unlink()

    def health(self) -> list[str]:
        return [] if self.root.is_dir() and os.access(self.root, os.W_OK) else ["local storage root is not writable"]


class S3ObjectStorage:
    """MinIO / S3-compatible storage (application identity: put / get / head / list — no delete)."""
    name = "s3"

    def __init__(self, client: S3Client, bucket_prefix: str) -> None:
        self.client, self.prefix = client, bucket_prefix

    def bucket(self, key: str) -> str:
        return f"{self.prefix}-{validate_key(key).split('/', 1)[0]}"

    def put(self, key: str, data: bytes, content_type: str) -> None:
        digest = hashlib.sha256(data).hexdigest()
        r = self.client.request("PUT", self.bucket(key), key, body=data, payload_sha256=digest,
                                headers={"content-type": content_type, "x-amz-server-side-encryption": "AES256",
                                         "x-amz-meta-sha256": digest})
        if r.status != 200:
            raise StorageError("STORAGE_WRITE_FAILED", str(self.client.error(r)))
        if r.headers.get("x-amz-server-side-encryption") != "AES256":
            raise StorageError("STORAGE_NOT_ENCRYPTED", "The object store did not confirm server-side encryption (SSE-S3); refused.")

    def _head(self, key: str) -> dict[str, str] | None:
        r = self.client.request("HEAD", self.bucket(key), key)
        if r.status == 404:
            return None
        if r.status != 200:
            raise StorageError("STORAGE_READ_FAILED", f"HEAD failed with HTTP {r.status}")
        return r.headers

    def stat(self, key: str) -> StoredObject | None:
        h = self._head(key)
        if h is None:
            return None
        modified = datetime.strptime(h.get("last-modified", "Thu, 01 Jan 1970 00:00:00 GMT"), "%a, %d %b %Y %H:%M:%S GMT")
        return StoredObject(key, int(h.get("content-length", "0")), modified, h.get("x-amz-meta-sha256"))

    def exists(self, key: str) -> bool:
        return self._head(key) is not None

    def verify(self, key: str, sha256: str, size: int) -> None:
        h = self._head(key)
        if h is None or int(h.get("content-length", "-1")) != size or h.get("x-amz-meta-sha256") != sha256:
            raise StorageError("STORAGE_VERIFY_FAILED", "The stored object does not match its SHA-256 / size.")
        if h.get("x-amz-server-side-encryption") != "AES256":
            raise StorageError("STORAGE_NOT_ENCRYPTED", "The stored object is not server-side encrypted.")

    def get(self, key: str) -> bytes:
        r = self.client.request("GET", self.bucket(key), key)
        if r.status != 200:
            raise StorageError("STORAGE_READ_FAILED", str(self.client.error(r)))
        return r.body

    def iter_objects(self, prefix: str) -> Iterator[StoredObject]:
        env = prefix.split("/", 1)[0]
        if env not in ENVIRONMENTS:
            raise StorageError("INVALID_STORAGE_KEY", "Listing is per environment prefix (live/ or demo/).")
        for o in self.client.list_objects(f"{self.prefix}-{env}", prefix):
            yield StoredObject(o.key, o.size, o.last_modified)

    def health(self) -> list[str]:
        problems: list[str] = []
        for env in ENVIRONMENTS:
            bucket = f"{self.prefix}-{env}"
            try:
                if not self.client.versioning_enabled(bucket):
                    problems.append(f"bucket {bucket}: versioning is not enabled")
                policy = self.client.bucket_policy(bucket)
                if policy and _is_public(policy):
                    problems.append(f"bucket {bucket}: a bucket policy grants public access")
            except OSError as e:
                problems.append(f"bucket {bucket}: unreachable ({type(e).__name__})")
            except S3Error as e:                                   # 5xx = outage; 4xx = configuration / permission problem
                problems.append(f"bucket {bucket}: unreachable (HTTP {e.status})" if e.status >= 500 else f"bucket {bucket}: {e.code}")
        return problems


class S3DeletionStorage:
    """The separate deletion identity (D8 / D10): used only by the orphan-deletion job after a locked re-check."""

    def __init__(self, client: S3Client, bucket_prefix: str) -> None:
        self.client, self.prefix = client, bucket_prefix

    def delete(self, key: str) -> None:
        r = self.client.request("DELETE", f"{self.prefix}-{validate_key(key).split('/', 1)[0]}", key)
        if r.status not in (200, 204):
            raise StorageError("STORAGE_DELETE_FAILED", str(self.client.error(r)))


def _is_public(policy: str) -> bool:
    import json
    try:
        doc = json.loads(policy)
    except ValueError:
        return True                                                   # unreadable policy: treat as unsafe
    for st in doc.get("Statement", []) if isinstance(doc, dict) else []:
        principal = st.get("Principal")
        aws = principal.get("AWS") if isinstance(principal, dict) else None
        anyone = principal == "*" or aws == "*" or (isinstance(aws, list) and "*" in aws)
        if st.get("Effect") == "Allow" and anyone:
            return True
    return False


def _client(access_key: str, secret_key: str) -> S3Client:
    s = get_settings()
    assert s.OBJECT_STORAGE_ENDPOINT
    return S3Client(s.OBJECT_STORAGE_ENDPOINT, s.OBJECT_STORAGE_REGION, access_key, secret_key, ca_cert=s.OBJECT_STORAGE_CA_CERT,
                    timeout=s.OBJECT_STORAGE_TIMEOUT_SECONDS)


def local_root() -> Path:
    s = get_settings()
    return Path(s.LOCAL_STORAGE_ROOT) if s.LOCAL_STORAGE_ROOT else Path(__file__).resolve().parents[3] / "storage" / "local-dev"


@lru_cache
def get_storage() -> ObjectStorage:
    s = get_settings()
    if s.STORAGE_BACKEND == "local":
        if s.is_production:
            raise RuntimeError("STORAGE_BACKEND=local is not allowed in production; configure the MinIO (s3) backend.")
        return LocalFileStorage(local_root())
    if s.STORAGE_BACKEND == "s3":
        assert s.OBJECT_STORAGE_ACCESS_KEY and s.OBJECT_STORAGE_SECRET_KEY
        return S3ObjectStorage(_client(s.OBJECT_STORAGE_ACCESS_KEY, s.OBJECT_STORAGE_SECRET_KEY), s.OBJECT_STORAGE_BUCKET_PREFIX)
    raise RuntimeError(f"STORAGE_BACKEND={s.STORAGE_BACKEND!r} is not supported.")


def get_deletion_storage() -> DeletionStorage | None:
    """None = deletion disabled (no separate deletion identity configured)."""
    s = get_settings()
    st = get_storage()
    if isinstance(st, LocalFileStorage):
        return st
    if s.OBJECT_STORAGE_DELETE_ACCESS_KEY and s.OBJECT_STORAGE_DELETE_SECRET_KEY:
        return S3DeletionStorage(_client(s.OBJECT_STORAGE_DELETE_ACCESS_KEY, s.OBJECT_STORAGE_DELETE_SECRET_KEY), s.OBJECT_STORAGE_BUCKET_PREFIX)
    return None
