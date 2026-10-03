"""Minimal S3-compatible client for MinIO (Phase 12B D2 / D3): AWS Signature Version 4 over the Python standard library only.

Path-style requests (`https://endpoint/<bucket>/<key>`), signed headers + signed payload hash (the server rejects a body whose SHA-256
differs — a corrupted upload never lands). Only the operations the platform needs: PUT / GET / HEAD / DELETE object, ListObjectsV2,
GET bucket versioning and policy. No public URL, presigned URL or bucket-administration call is ever made.
"""
import hashlib
import hmac
import http.client
import ssl
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


class S3Error(RuntimeError):
    def __init__(self, status: int, code: str, message: str = "") -> None:
        super().__init__(f"S3 {status} {code}: {message}"[:500])
        self.status, self.code = status, code


def _uri(value: str, safe: str) -> str:
    return quote(value, safe=safe + "-_.~")


def canonical_query(query: Mapping[str, str]) -> str:
    return "&".join(f"{_uri(k, '')}={_uri(v, '')}" for k, v in sorted(query.items()))


def signing_key(secret_key: str, date: str, region: str, service: str = "s3") -> bytes:
    k = hmac.new(("AWS4" + secret_key).encode(), date.encode(), hashlib.sha256).digest()
    for part in (region, service, "aws4_request"):
        k = hmac.new(k, part.encode(), hashlib.sha256).digest()
    return k


def sign(method: str, path: str, query: Mapping[str, str], headers: Mapping[str, str], payload_sha256: str, access_key: str,
         secret_key: str, region: str, amz_date: str, service: str = "s3") -> str:
    """The Authorization header value for AWS Signature V4 (header-based). `headers` must already contain host, x-amz-date and
    x-amz-content-sha256; every header passed is signed."""
    lower = {k.lower().strip(): " ".join(str(v).strip().split()) for k, v in headers.items()}
    signed = ";".join(sorted(lower))
    canonical = "\n".join([method, _uri(path, "/"), canonical_query(query), "".join(f"{k}:{lower[k]}\n" for k in sorted(lower)), signed,
                           payload_sha256])
    date = amz_date[:8]
    scope = f"{date}/{region}/{service}/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    signature = hmac.new(signing_key(secret_key, date, region, service), to_sign.encode(), hashlib.sha256).hexdigest()
    return f"AWS4-HMAC-SHA256 Credential={access_key}/{scope},SignedHeaders={signed},Signature={signature}"


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class ListedObject:
    key: str
    size: int
    last_modified: datetime   # naive UTC


def _parse(body: bytes) -> ET.Element:
    """Responses come only from the configured storage endpoint. A document with a DTD / entity declaration is refused outright (no S3
    response carries one), so entity-expansion and external-entity payloads never reach the parser."""
    if b"<!DOCTYPE" in body or b"<!ENTITY" in body:
        raise ET.ParseError("XML with a document type declaration is not accepted")
    return ET.fromstring(body)  # noqa: S314 - DTDs refused above; the source is the configured object store


class S3Client:
    def __init__(self, endpoint: str, region: str, access_key: str, secret_key: str, *, ca_cert: str | None = None, timeout: int = 30
                 ) -> None:
        u = urlsplit(endpoint)
        if u.scheme not in ("http", "https") or not u.hostname:
            raise ValueError("OBJECT_STORAGE_ENDPOINT must be an http(s) URL")
        self.scheme, self.host, self.port = u.scheme, u.hostname, u.port
        self.netloc = u.netloc
        self.region, self.access_key, self.secret_key, self.timeout = region, access_key, secret_key, timeout
        self.ssl = ssl.create_default_context(cafile=ca_cert) if u.scheme == "https" else None

    def request(self, method: str, bucket: str, key: str | None = None, *, query: Mapping[str, str] | None = None,
                headers: Mapping[str, str] | None = None, body: bytes = b"", payload_sha256: str | None = None) -> Response:
        path = f"/{bucket}" + (f"/{key}" if key else "")
        query = dict(query or {})
        digest = payload_sha256 or (hashlib.sha256(body).hexdigest() if body else EMPTY_SHA256)
        amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        hdrs = {"host": self.netloc, "x-amz-date": amz_date, "x-amz-content-sha256": digest, **{k.lower(): v for k, v in (headers or {}).items()}}
        if body:
            hdrs["content-length"] = str(len(body))
        hdrs["authorization"] = sign(method, path, query, {k: v for k, v in hdrs.items() if k != "authorization"}, digest,
                                     self.access_key, self.secret_key, self.region, amz_date)
        target = _uri(path, "/") + (f"?{canonical_query(query)}" if query else "")
        conn: http.client.HTTPConnection = (http.client.HTTPSConnection(self.host, self.port, timeout=self.timeout, context=self.ssl)
                                            if self.scheme == "https" else http.client.HTTPConnection(self.host, self.port, timeout=self.timeout))
        try:
            conn.request(method, target, body=body or None, headers=hdrs)
            r = conn.getresponse()
            data = r.read()
            return Response(r.status, {k.lower(): v for k, v in r.getheaders()}, data)
        finally:
            conn.close()

    @staticmethod
    def error(resp: Response) -> S3Error:
        code, message = "HTTP_ERROR", ""
        try:
            root = _parse(resp.body) if resp.body else None
            if root is not None:
                code = (root.findtext("Code") or code)
                message = root.findtext("Message") or ""
        except ET.ParseError:
            pass
        return S3Error(resp.status, code, message)

    def list_objects(self, bucket: str, prefix: str) -> Iterator[ListedObject]:
        token: str | None = None
        while True:
            q = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
            if token:
                q["continuation-token"] = token
            r = self.request("GET", bucket, query=q)
            if r.status != 200:
                raise self.error(r)
            root = _parse(r.body)
            for c in root.iter(f"{_NS}Contents"):
                lm = (c.findtext(f"{_NS}LastModified") or "").replace("Z", "+00:00")
                yield ListedObject(c.findtext(f"{_NS}Key") or "", int(c.findtext(f"{_NS}Size") or 0),
                                   datetime.fromisoformat(lm).astimezone(timezone.utc).replace(tzinfo=None))
            if (root.findtext(f"{_NS}IsTruncated") or "false") != "true":
                return
            token = root.findtext(f"{_NS}NextContinuationToken")
            if not token:
                return

    def versioning_enabled(self, bucket: str) -> bool:
        r = self.request("GET", bucket, query={"versioning": ""})
        if r.status != 200:
            raise self.error(r)
        return (_parse(r.body).findtext(f"{_NS}Status") or "") == "Enabled"

    def bucket_policy(self, bucket: str) -> str | None:
        r = self.request("GET", bucket, query={"policy": ""})
        if r.status == 404:
            return None
        if r.status != 200:
            raise self.error(r)
        return r.body.decode("utf-8", "replace")
