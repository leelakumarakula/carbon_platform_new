"""TEST-ONLY S3-compatible stub server (Phase 12B). It is never imported by the application.

It exercises the real `S3Client` / `S3ObjectStorage` / `S3DeletionStorage` over HTTP on 127.0.0.1 and enforces what the platform relies
on from MinIO: AWS SigV4 on every request (signature recomputed from the received request; unknown key, wrong secret, unsigned
host / date / payload hash or any tampering -> 403), the signed payload hash must match the body (400 XAmzContentSHA256Mismatch), two
identities (the application identity has no delete permission; the deletion identity has), SSE-S3 confirmation (switchable off to
prove the client refuses unencrypted writes), bucket versioning (overwrites and deletes keep earlier versions), bucket policies
(public or not) and ListObjectsV2 pagination. It is a protocol double, not a substitute for testing against a real MinIO deployment.
"""
import hashlib
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit
from xml.sax.saxutils import escape

from app.integrations.s3 import sign

APP_KEY, APP_SECRET = "test-app-access", "test-app-secret-0123456789"
DELETE_KEY, DELETE_SECRET = "test-delete-access", "test-delete-secret-0123456789"
REGION = "us-east-1"
_AUTH = re.compile(r"AWS4-HMAC-SHA256 Credential=([^/]+)/(\d{8})/([^/]+)/s3/aws4_request,SignedHeaders=([^,]+),Signature=([0-9a-f]{64})$")


@dataclass
class Version:
    data: bytes
    headers: dict[str, str]
    modified: datetime
    delete_marker: bool = False


@dataclass
class Bucket:
    versioning: bool = True
    policy: str | None = None
    objects: dict[str, list[Version]] = field(default_factory=dict)

    def current(self, key: str) -> Version | None:
        vs = self.objects.get(key)
        return vs[-1] if vs and not vs[-1].delete_marker else None


class S3Stub:
    def __init__(self, bucket_prefix: str = "carbon") -> None:
        self.identities: dict[str, tuple[str, set[str]]] = {
            APP_KEY: (APP_SECRET, {"get", "put", "head", "list", "config"}),
            DELETE_KEY: (DELETE_SECRET, {"get", "head", "list", "delete"}),
        }
        self.buckets = {f"{bucket_prefix}-live": Bucket(), f"{bucket_prefix}-demo": Bucket()}
        self.encrypt = True             # False: the server ignores SSE (the client must refuse)
        self.page_size = 1000
        self.fail_puts = False          # True: every PUT answers 503
        self.requests: list[tuple[str, str, str]] = []   # (method, path, access key)
        self.lock = threading.Lock()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(self))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def start(self) -> "S3Stub":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def age(self, bucket: str, key: str, when: datetime) -> None:
        self.buckets[bucket].objects[key][-1].modified = when

    def put_raw(self, bucket: str, key: str, data: bytes, encrypted: bool = True, sha: str | None = None) -> None:
        headers = {"content-type": "application/octet-stream", "x-amz-meta-sha256": sha or hashlib.sha256(data).hexdigest()}
        if encrypted:
            headers["x-amz-server-side-encryption"] = "AES256"
        self.buckets[bucket].objects.setdefault(key, []).append(Version(data, headers, _now()))


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)


def _xml_error(code: str, message: str = "") -> bytes:
    return f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><Error><Code>{code}</Code><Message>{escape(message)}</Message></Error>".encode()


def _handler(stub: S3Stub) -> type[BaseHTTPRequestHandler]:
    ns = "http://s3.amazonaws.com/doc/2006-03-01/"

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args: Any) -> None:
            return

        def _send(self, status: int, body: bytes = b"", headers: dict[str, str] | None = None) -> None:
            self.send_response(status)
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _auth(self, path: str, query: dict[str, str], body: bytes) -> str | None:
            m = _AUTH.match(self.headers.get("Authorization", ""))
            if not m:
                self._send(403, _xml_error("AccessDenied", "missing or malformed SigV4 authorization"))
                return None
            access, date, region, signed, _sig = m.groups()
            ident = stub.identities.get(access)
            names = signed.split(";")
            if ident is None:
                self._send(403, _xml_error("InvalidAccessKeyId"))
                return None
            if not {"host", "x-amz-date", "x-amz-content-sha256"} <= set(names) or region != REGION:
                self._send(403, _xml_error("AccessDenied", "host, x-amz-date and x-amz-content-sha256 must be signed"))
                return None
            hdrs = {n: self.headers.get(n, "") for n in names}
            payload = self.headers.get("x-amz-content-sha256", "")
            expected = sign(self.command, path, query, hdrs, payload, access, ident[0], REGION, self.headers.get("x-amz-date", ""))
            if expected != self.headers.get("Authorization"):
                self._send(403, _xml_error("SignatureDoesNotMatch"))
                return None
            if payload != hashlib.sha256(body).hexdigest():
                self._send(400, _xml_error("XAmzContentSHA256Mismatch", "payload hash does not match the body"))
                return None
            return access

        def _handle(self) -> None:
            u = urlsplit(self.path)
            path = unquote(u.path)
            query = dict(parse_qsl(u.query, keep_blank_values=True))
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            access = self._auth(path, query, body)
            if access is None:
                return
            perms = stub.identities[access][1]
            parts = path.lstrip("/").split("/", 1)
            bucket_name, key = parts[0], (parts[1] if len(parts) > 1 else None)
            with stub.lock:
                stub.requests.append((self.command, path, access))
                bucket = stub.buckets.get(bucket_name)
                if bucket is None:
                    return self._send(404, _xml_error("NoSuchBucket"))
                if key is None:
                    return self._bucket_op(bucket, query, perms)
                return self._object_op(bucket, key, body, perms)

        def _denied(self) -> None:
            self._send(403, _xml_error("AccessDenied", "this identity is not allowed to perform the operation"))

        def _bucket_op(self, bucket: Bucket, query: dict[str, str], perms: set[str]) -> None:
            if self.command != "GET":
                return self._send(405, _xml_error("MethodNotAllowed"))
            if "versioning" in query:
                if "config" not in perms:
                    return self._denied()
                status = "<Status>Enabled</Status>" if bucket.versioning else ""
                return self._send(200, f'<VersioningConfiguration xmlns="{ns}">{status}</VersioningConfiguration>'.encode())
            if "policy" in query:
                if "config" not in perms:
                    return self._denied()
                if bucket.policy is None:
                    return self._send(404, _xml_error("NoSuchBucketPolicy"))
                return self._send(200, bucket.policy.encode())
            if query.get("list-type") == "2":
                if "list" not in perms:
                    return self._denied()
                keys = sorted(k for k in bucket.objects if k.startswith(query.get("prefix", "")) and bucket.current(k))
                start = int(query.get("continuation-token") or 0)
                page = keys[start:start + min(stub.page_size, int(query.get("max-keys", "1000")))]
                more = start + len(page) < len(keys)
                items = "".join(f"<Contents><Key>{escape(k)}</Key><LastModified>{bucket.current(k).modified:%Y-%m-%dT%H:%M:%S.000Z}"  # type: ignore[union-attr]
                                f"</LastModified><Size>{len(bucket.current(k).data)}</Size></Contents>" for k in page)  # type: ignore[union-attr]
                token = f"<NextContinuationToken>{start + len(page)}</NextContinuationToken>" if more else ""
                return self._send(200, f'<ListBucketResult xmlns="{ns}">{items}<IsTruncated>{"true" if more else "false"}</IsTruncated>'
                                       f"{token}</ListBucketResult>".encode())
            return self._send(400, _xml_error("InvalidRequest"))

        def _object_op(self, bucket: Bucket, key: str, body: bytes, perms: set[str]) -> None:
            if self.command == "PUT":
                if "put" not in perms:
                    return self._denied()
                if stub.fail_puts:
                    return self._send(503, _xml_error("ServiceUnavailable"))
                headers = {k.lower(): v for k, v in self.headers.items() if k.lower().startswith("x-amz-meta-") or k.lower() == "content-type"}
                encrypted = stub.encrypt and self.headers.get("x-amz-server-side-encryption") == "AES256"
                if encrypted:
                    headers["x-amz-server-side-encryption"] = "AES256"
                v = Version(body, headers, _now())
                if bucket.versioning:
                    bucket.objects.setdefault(key, []).append(v)
                else:
                    bucket.objects[key] = [v]
                return self._send(200, b"", {"ETag": f'"{hashlib.md5(body, usedforsecurity=False).hexdigest()}"',
                                             **({"x-amz-server-side-encryption": "AES256"} if encrypted else {})})
            if self.command in ("GET", "HEAD"):
                if self.command.lower() not in perms:
                    return self._denied()
                cur = bucket.current(key)
                if cur is None:
                    return self._send(404, _xml_error("NoSuchKey"))
                return self._send(200, cur.data, {**cur.headers, "Last-Modified": f"{cur.modified:%a, %d %b %Y %H:%M:%S GMT}"})
            if self.command == "DELETE":
                if "delete" not in perms:
                    return self._denied()
                if bucket.versioning and key in bucket.objects:
                    bucket.objects[key].append(Version(b"", {}, _now(), delete_marker=True))   # earlier versions stay recoverable
                else:
                    bucket.objects.pop(key, None)
                return self._send(204)
            return self._send(405, _xml_error("MethodNotAllowed"))

        def do_GET(self) -> None:
            self._handle()

        do_PUT = do_HEAD = do_DELETE = do_GET

    return Handler
