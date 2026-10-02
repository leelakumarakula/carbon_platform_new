"""Documents: content sniffing, size limit, malware hook, checksums, versions, restricted access, audited download."""
import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.integrations.malware import EICAR
from app.models import AuditLog, DocumentVersion, SecurityEvent
from tests.phase2 import PDF, PNG, create_farmer, dev_org, staff, upload


@pytest.fixture()
def setup(db: Session, client: TestClient) -> dict:
    org = dev_org(db)
    pm = staff(db, client, org, "PROJECT_MANAGER")
    farmer = create_farmer(client, pm.headers, org)
    return {"org": org, "pm": pm, "farmer": farmer, "url": f"/api/v1/farmers/{farmer['id']}/documents"}


def test_upload_stores_checksum_and_scan_status(client: TestClient, db: Session, setup: dict) -> None:
    r = upload(client, setup["pm"].headers, setup["url"], "LAND_RECORD", PDF, "../../evil name?.exe", "Land record")
    assert r.status_code == 201, r.text
    doc = client.get(f"/api/v1/evidence/documents/{r.json()['id']}", headers=setup["pm"].headers).json()
    v = doc["versions"][0]
    assert v["checksum_sha256"] == hashlib.sha256(PDF).hexdigest() and v["mime_type"] == "application/pdf"
    assert v["file_name"] == "evil name_.pdf"  # path stripped, extension from detected type
    assert v["scan_status"] == "NOT_SCANNED" and doc["sensitivity"] == "INTERNAL"
    assert db.scalars(select(AuditLog).where(AuditLog.action == "DOCUMENT_UPLOADED", AuditLog.entity_id == setup["farmer"]["id"])).first()


@pytest.mark.parametrize("content,code", [
    (b"MZ\x90\x00 this is a windows executable", "UNSUPPORTED_FILE_TYPE"),
    (b"<html><script>alert(1)</script></html>", "UNSUPPORTED_FILE_TYPE"),
    (b"", "EMPTY_FILE"),
])
def test_disguised_or_empty_files_rejected(client: TestClient, setup: dict, content: bytes, code: str) -> None:
    r = upload(client, setup["pm"].headers, setup["url"], "OTHER", content, "innocent.pdf")
    assert r.status_code == 422 and r.json()["error_code"] == code


def test_malware_signature_blocked_and_reported(client: TestClient, db: Session, setup: dict) -> None:
    r = upload(client, setup["pm"].headers, setup["url"], "OTHER", b"%PDF-1.4\n" + EICAR, "x.pdf")
    assert r.status_code == 422 and r.json()["error_code"] == "MALWARE_DETECTED"
    assert db.scalars(select(SecurityEvent).where(SecurityEvent.event_type == "MALWARE_UPLOAD_BLOCKED")).first()


def test_size_limit(client: TestClient, setup: dict, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "MAX_UPLOAD_BYTES", 50)
    r = upload(client, setup["pm"].headers, setup["url"], "OTHER", PDF + b"x" * 100)
    assert r.status_code == 422 and r.json()["error_code"] == "FILE_TOO_LARGE"


def test_category_type_rules(client: TestClient, setup: dict) -> None:
    geo = b'{"type": "Polygon", "coordinates": []}'
    assert upload(client, setup["pm"].headers, setup["url"], "KYC_ID", geo, "a.json").json()["error_code"] == "UNSUPPORTED_FILE_TYPE"
    assert upload(client, setup["pm"].headers, setup["url"], "FIELD_PHOTO", PNG).json()["error_code"] == "INVALID_CATEGORY"
    assert upload(client, setup["pm"].headers, setup["url"], "NOT_A_CATEGORY", PDF).status_code == 422


def test_versions_are_kept_and_immutable(client: TestClient, db: Session, setup: dict) -> None:
    doc_id = upload(client, setup["pm"].headers, setup["url"], "LAND_RECORD").json()["id"]
    v2 = PDF.replace(b"Catalog", b"Catalog2")
    r = client.post(f"/api/v1/evidence/documents/{doc_id}/versions", headers=setup["pm"].headers,
                    files={"file": ("v2.pdf", v2, "application/pdf")})
    assert r.status_code == 200 and r.json()["current_version"] == 2 and len(r.json()["versions"]) == 2
    old = client.get(f"/api/v1/evidence/documents/{doc_id}/download", headers=setup["pm"].headers, params={"version": 1})
    new = client.get(f"/api/v1/evidence/documents/{doc_id}/download", headers=setup["pm"].headers)
    assert old.content == PDF and new.content == v2
    assert "attachment" in new.headers["content-disposition"] and new.headers["x-content-type-options"] == "nosniff"
    assert db.scalars(select(AuditLog).where(AuditLog.action == "DOCUMENT_DOWNLOADED")).first()


def test_document_versions_append_only_in_database() -> None:
    from app.core.database import get_engine
    with get_engine().connect() as conn:
        trans = conn.begin()
        with pytest.raises(DBAPIError) as e:
            conn.execute(text("UPDATE document_versions SET file_name = 'x'"))
        assert "append-only" in str(e.value) or "0 rows" in str(e.value)
        if trans.is_active:
            trans.rollback()


def test_restricted_documents(client: TestClient, db: Session, setup: dict) -> None:
    kyc = upload(client, setup["pm"].headers, setup["url"], "KYC_ID").json()["id"]
    gis = staff(db, client, setup["org"], "GIS_SPECIALIST")  # can read farmers, but not KYC documents
    r = client.get(f"/api/v1/evidence/documents/{kyc}/download", headers=gis.headers)
    assert r.status_code == 403 and r.json()["error_code"] == "RESTRICTED_DOCUMENT"
    outsider = staff(db, client, dev_org(db), "PROJECT_MANAGER")
    assert client.get(f"/api/v1/evidence/documents/{kyc}", headers=outsider.headers).status_code == 404
    assert client.get(f"/api/v1/evidence/documents/{kyc}/download", headers=setup["pm"].headers).status_code == 200


def test_stored_file_tampering_detected(client: TestClient, db: Session, setup: dict) -> None:
    from app.integrations.storage import get_storage
    doc_id = upload(client, setup["pm"].headers, setup["url"], "LAND_RECORD").json()["id"]
    v = db.scalars(select(DocumentVersion).join(DocumentVersion.document).where(DocumentVersion.document_id == doc_id)).one()
    get_storage().put(v.storage_key, b"%PDF-tampered", "application/pdf")
    r = client.get(f"/api/v1/evidence/documents/{doc_id}/download", headers=setup["pm"].headers)
    assert r.status_code == 409 and r.json()["error_code"] == "DOCUMENT_INTEGRITY_FAILURE"
