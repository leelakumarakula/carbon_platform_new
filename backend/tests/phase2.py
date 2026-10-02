"""Helpers for Phase 2 (farmer & farm) tests."""
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Organization
from tests.conftest import Actor, login, make_org, make_user

PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
BASE_LON, BASE_LAT = 73.80, 20.00


def square(lon: float = BASE_LON, lat: float = BASE_LAT, size: float = 0.001) -> dict[str, Any]:
    return {"type": "Polygon", "coordinates": [[[lon, lat], [lon + size, lat], [lon + size, lat + size], [lon, lat + size], [lon, lat]]]}


def staff(db: Session, client: TestClient, org: Organization, *roles: str) -> Actor:
    u = make_user(db, roles=[(r, org) for r in roles])
    return Actor(u, login(client, u))


def upload(client: TestClient, h: dict, url: str, category: str, content: bytes = PDF, name: str = "doc.pdf",
           title: str = "") -> Any:
    return client.post(url, headers=h, files={"file": (name, content, "application/octet-stream")},
                       data={"category": category, "title": title})


def create_farmer(client: TestClient, h: dict, org: Organization, **kw: Any) -> dict:
    body = {"organization_id": str(org.id), "full_name": "Asha Patil", "village": "Pimpalgaon", "district": "Nashik",
            "state": "Maharashtra", "country": "IN", "primary_phone": "+91 98765 43210", **kw}
    r = client.post("/api/v1/farmers", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def register(client: TestClient, h: dict, farmer_id: str) -> dict:
    r = client.post(f"/api/v1/farmers/{farmer_id}/status", headers=h, json={"status": "REGISTERED", "reason": "profile complete"})
    assert r.status_code == 200, r.text
    return r.json()


def kyc_verified_farmer(client: TestClient, submitter: Actor, reviewer: Actor, org: Organization, id_number: str = "1234 5678 9012",
                        **kw: Any) -> dict:
    f = create_farmer(client, submitter.headers, org, **kw)
    register(client, submitter.headers, f["id"])
    doc = upload(client, submitter.headers, f"/api/v1/farmers/{f['id']}/documents", "KYC_ID").json()["id"]
    r = client.post(f"/api/v1/farmers/{f['id']}/kyc", headers=submitter.headers,
                    json={"id_type": "NATIONAL_ID", "id_number": id_number, "document_id": doc})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/farmers/{f['id']}/kyc/decision", headers=reviewer.headers,
                    json={"decision": "VERIFIED", "notes": "documents match", "acknowledge_possible_duplicate": True})
    assert r.status_code == 200, r.text
    return r.json()


def create_farm(client: TestClient, h: dict, farmer_id: str, **kw: Any) -> dict:
    body = {"farmer_id": farmer_id, "name": "North field", "village": "Pimpalgaon", "district": "Nashik", "state": "Maharashtra",
            "country": "IN", "land_tenure": "OWNED", **kw}
    r = client.post("/api/v1/farms", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def set_boundary(client: TestClient, h: dict, farm_id: str, geo: dict | None = None) -> dict:
    r = client.post(f"/api/v1/farms/{farm_id}/boundary", headers=h, json={"geojson": geo or square(), "source": "DRAWN"})
    assert r.status_code == 200, r.text
    return r.json()


def add_owner(client: TestClient, h: dict, farm_id: str, **kw: Any) -> dict:
    body = {"owner_type": "INDIVIDUAL", "owner_name": "Ramesh Patil", "operator_relationship": "TENANT", "title_reference": "7/12-445",
            **kw}
    r = client.post(f"/api/v1/farms/{farm_id}/ownership", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def dev_org(db: Session, code: str | None = None) -> Organization:
    return make_org(db, code, org_type="PROJECT_DEVELOPER")
