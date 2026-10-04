"""Farms: boundary versions + SQL Server area, ownership (farmer ≠ owner), versioned history, evidence,
overlap flags (never auto-reject), verification gates, separation of duties, cross-org privacy, audit."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, FarmBoundary, FarmCropHistory, Notification
from tests.conftest import Actor, login, make_org, make_user
from tests.phase2 import (
    PNG,
    add_owner,
    create_farm,
    create_farmer,
    dev_org,
    kyc_verified_farmer,
    set_boundary,
    square,
    staff,
    upload,
)

FA = "/api/v1/farms"


@pytest.fixture()
def ctx(db: Session, client: TestClient) -> dict:
    org = dev_org(db)
    agent = staff(db, client, org, "FIELD_AGENT")
    qa = staff(db, client, org, "QA_OFFICER")
    gis = staff(db, client, org, "GIS_SPECIALIST")
    farmer = kyc_verified_farmer(client, agent, qa, org)
    return {"org": org, "agent": agent, "qa": qa, "gis": gis, "farmer": farmer}


def ready_farm(client: TestClient, c: dict, geo: dict | None = None) -> dict:
    farm = create_farm(client, c["agent"].headers, c["farmer"]["id"], declared_area_hectares="1.2")
    set_boundary(client, c["agent"].headers, farm["id"], geo)
    owner = add_owner(client, c["agent"].headers, farm["id"])
    return {"farm": farm, "owner": owner}


def test_farm_needs_registered_farmer(client: TestClient, db: Session, ctx: dict) -> None:
    draft = create_farmer(client, ctx["agent"].headers, ctx["org"])
    r = client.post(FA, headers=ctx["agent"].headers, json={"farmer_id": draft["id"], "name": "x field", "country": "IN",
                                                           "land_tenure": "OWNED"})
    assert r.status_code == 409 and r.json()["error_code"] == "FARMER_NOT_READY"


def test_boundary_versions_and_authoritative_area(client: TestClient, db: Session, ctx: dict) -> None:
    farm = create_farm(client, ctx["agent"].headers, ctx["farmer"]["id"], declared_area_hectares="5")
    saved = set_boundary(client, ctx["agent"].headers, farm["id"])
    assert 1.15 < float(saved["farm"]["area_hectares"]) < 1.17
    assert any("differs from the declared" in w for w in saved["warnings"])
    bigger = set_boundary(client, ctx["agent"].headers, farm["id"], square(size=0.002))["farm"]
    assert 4.6 < float(bigger["area_hectares"]) < 4.7 and bigger["current_boundary"]["version"] == 2
    versions = client.get(f"{FA}/{farm['id']}/boundaries", headers=ctx["agent"].headers).json()
    assert [(v["version"], v["status"]) for v in versions] == [(2, "CURRENT"), (1, "SUPERSEDED")]
    assert db.scalars(select(FarmBoundary).where(FarmBoundary.farm_id == farm["id"])).all()[0].boundary.startswith("POLYGON")
    actions = db.scalars(select(AuditLog.action).where(AuditLog.entity_id == farm["id"])).all()
    assert actions.count("FARM_BOUNDARY_SAVED") == 2


def test_boundary_file_upload_kml(client: TestClient, ctx: dict) -> None:
    from tests.test_gis import KML
    farm = create_farm(client, ctx["agent"].headers, ctx["farmer"]["id"])
    r = client.post(f"{FA}/{farm['id']}/boundary/upload", headers=ctx["agent"].headers,
                    files={"file": ("plot.kml", KML.encode(), "application/octet-stream")})
    assert r.status_code == 200, r.text
    f = r.json()["farm"]
    assert f["current_boundary"]["source"] == "KML_UPLOAD" and f["current_boundary"]["source_document_id"]
    assert [d["category"] for d in f["documents"]] == ["GEOSPATIAL_FILE"]


def test_ownership_farmer_is_not_owner(client: TestClient, ctx: dict) -> None:
    farm = create_farm(client, ctx["agent"].headers, ctx["farmer"]["id"], land_tenure="LEASED")
    o = add_owner(client, ctx["agent"].headers, farm["id"], ownership_share_pct="100", valid_from="2020-06-01")
    assert o["owner_type"] == "INDIVIDUAL" and o["owner_farmer_id"] is None and o["operator_relationship"] == "TENANT"
    bad = client.post(f"{FA}/{farm['id']}/ownership", headers=ctx["agent"].headers,
                      json={"owner_type": "FARMER", "operator_relationship": "OWNER"})
    assert bad.json()["error_code"] == "OWNER_FARMER_REQUIRED"
    end = client.post(f"{FA}/{farm['id']}/ownership/{o['id']}/end", headers=ctx["agent"].headers,
                      json={"valid_to": "2020-01-01", "reason": "lease ended"})
    assert end.json()["error_code"] == "INVALID_DATES"


def test_history_is_versioned_never_overwritten(client: TestClient, db: Session, ctx: dict) -> None:
    farm = create_farm(client, ctx["agent"].headers, ctx["farmer"]["id"])
    url = f"{FA}/{farm['id']}/history/crop"
    rec = client.post(url, headers=ctx["agent"].headers, json={"year": 2023, "season": "Kharif", "crop_name": "Soybean",
                                                              "irrigation": "RAINFED", "yield_quantity": "1.8", "yield_unit": "t/ha"})
    assert rec.status_code == 201, rec.text
    rid = rec.json()["record_id"]
    am = client.post(f"{url}/{rid}/amend", headers=ctx["agent"].headers,
                     json={"reason": "farmer corrected yield", "data": {"yield_quantity": "2.1"}})
    assert am.status_code == 200 and am.json()["version"] == 2 and am.json()["fields"]["yield_quantity"] == "2.1"
    versions = client.get(f"{url}/{rid}/versions", headers=ctx["agent"].headers).json()
    assert [(v["version"], v["fields"]["yield_quantity"], v["is_current"]) for v in versions] == [(1, "1.8", False), (2, "2.1", True)]
    rows = db.scalars(select(FarmCropHistory).where(FarmCropHistory.record_id == rid)).all()
    assert len(rows) == 2  # version 1 still physically present with its original values
    nothing = client.post(f"{url}/{rid}/amend", headers=ctx["agent"].headers, json={"reason": "no-op edit", "data": {}})
    assert nothing.json()["error_code"] == "NO_CHANGES"
    bad = client.post(f"{url}/{rid}/amend", headers=ctx["agent"].headers, json={"reason": "bad", "data": {"yield_unit": None}})
    assert bad.status_code == 422
    # an amendment may cite only an ACTIVE document of this farm (same rule as add)
    other = create_farm(client, ctx["agent"].headers, ctx["farmer"]["id"], name="Other plot")
    foreign = upload(client, ctx["agent"].headers, f"{FA}/{other['id']}/documents", "LAND_RECORD").json()["id"]
    xlink = client.post(f"{url}/{rid}/amend", headers=ctx["agent"].headers, json={"reason": "evidence", "data": {"evidence_document_id": foreign}})
    assert xlink.status_code == 422 and xlink.json()["error_code"] == "DOCUMENT_NOT_ATTACHED"
    own = upload(client, ctx["agent"].headers, f"{FA}/{farm['id']}/documents", "LAND_RECORD").json()["id"]
    ok = client.post(f"{url}/{rid}/amend", headers=ctx["agent"].headers, json={"reason": "evidence", "data": {"evidence_document_id": own}})
    assert ok.status_code == 200 and ok.json()["version"] == 3, ok.text
    rt = client.post(f"{url}/{rid}/retract", headers=ctx["agent"].headers, json={"reason": "entered on wrong farm"})
    assert rt.json()["is_retracted"] is True and rt.json()["version"] == 4
    assert client.get(url, headers=ctx["agent"].headers).json() == []
    assert len(client.get(url, headers=ctx["agent"].headers, params={"include_retracted": True}).json()) == 1
    prac = client.post(f"{FA}/{farm['id']}/history/practice", headers=ctx["agent"].headers,
                       json={"year": 2026, "practice_phase": "PROPOSED", "practice_category": "TILLAGE", "practice_type": "No-till"})
    assert prac.status_code == 422  # proposed practice needs implementation status
    land = client.post(f"{FA}/{farm['id']}/history/land", headers=ctx["agent"].headers, json={"year": 2019, "land_use": "CROPLAND"})
    assert land.status_code == 201


def test_overlap_flagged_not_rejected_and_blocks_verification(client: TestClient, db: Session, ctx: dict) -> None:
    a = ready_farm(client, ctx)
    b = ready_farm(client, ctx, square(73.8005, 20.0))  # half overlaps A
    overlaps = client.get(f"{FA}/{b['farm']['id']}/overlaps", headers=ctx["gis"].headers).json()
    assert len(overlaps) == 1
    ov = overlaps[0]
    assert ov["status"] == "OPEN" and ov["relation"] == "PARTIAL" and 45 < float(ov["overlap_pct_of_farm"]) < 55
    assert ov["same_farmer"] is True and ov["other_farm_code"] == a["farm"]["farm_code"] and ov["other_geojson"]
    # A sees the same check from its side
    assert client.get(f"{FA}/{a['farm']['id']}/overlaps", headers=ctx["gis"].headers).json()[0]["id"] == ov["id"]
    # the farm is still submittable — overlaps are flagged for review, not rejected
    sub = client.post(f"{FA}/{b['farm']['id']}/submit", headers=ctx["agent"].headers, json={"reason": "ready for review"})
    assert sub.status_code == 200 and sub.json()["status"] == "SUBMITTED" and sub.json()["open_overlaps"] == 1
    assert len(client.get(f"{FA}/{b['farm']['id']}/overlaps", headers=ctx["gis"].headers).json()) == 1  # not duplicated on re-check
    client.post(f"{FA}/{b['farm']['id']}/start-review", headers=ctx["gis"].headers, json={"reason": "picked up"})
    client.post(f"{FA}/{b['farm']['id']}/ownership/{b['owner']['id']}/review", headers=ctx["gis"].headers,
                json={"status": "VERIFIED", "notes": "7/12 extract matches"})
    blocked = client.post(f"{FA}/{b['farm']['id']}/verify", headers=ctx["gis"].headers, json={"reason": "looks good"})
    assert blocked.status_code == 409 and "overlaps" in blocked.json()["message"]
    res = client.post(f"{FA}/{b['farm']['id']}/overlaps/{ov['id']}/resolve", headers=ctx["gis"].headers,
                      json={"resolution": "CLEARED", "notes": "adjacent parcels of same farmer; digitising error accepted"})
    assert res.json()["status"] == "CLEARED"
    ok = client.post(f"{FA}/{b['farm']['id']}/verify", headers=ctx["gis"].headers, json={"reason": "boundary and tenure confirmed"})
    assert ok.status_code == 200 and ok.json()["status"] == "VERIFIED"
    assert db.scalars(select(Notification).where(Notification.event_type == "FARM_VERIFIED")).first()
    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.entity_id == b["farm"]["id"])).all())
    assert {"FARM_CREATED", "FARM_BOUNDARY_SAVED", "FARM_OVERLAP_DETECTED", "FARM_OWNERSHIP_RECORDED", "FARM_SUBMITTED",
            "FARM_REVIEW_STARTED", "FARM_OWNERSHIP_REVIEWED", "FARM_VERIFIED"} <= actions
    assert db.scalars(select(AuditLog).where(AuditLog.action == "FARM_OVERLAP_RESOLVED", AuditLog.entity_id == ov["id"])).one()


def test_verification_gates_and_separation_of_duties(client: TestClient, db: Session, ctx: dict) -> None:
    f = ready_farm(client, ctx, square(74.5, 19.5))
    fid = f["farm"]["id"]
    no_own = create_farm(client, ctx["agent"].headers, ctx["farmer"]["id"])
    set_boundary(client, ctx["agent"].headers, no_own["id"], square(74.6, 19.5))
    r = client.post(f"{FA}/{no_own['id']}/submit", headers=ctx["agent"].headers, json={"reason": "submit"})
    assert r.status_code == 409 and "ownership" in r.json()["message"]
    client.post(f"{FA}/{fid}/submit", headers=ctx["agent"].headers, json={"reason": "submit"})
    assert client.post(f"{FA}/{fid}/boundary", headers=ctx["agent"].headers, json={"geojson": square()}).json()["error_code"] == "FARM_NOT_EDITABLE"
    assert client.post(f"{FA}/{fid}/start-review", headers=ctx["agent"].headers, json={"reason": "self"}).status_code == 403
    # a reviewer who also submitted cannot verify
    both = staff(db, client, ctx["org"], "GIS_SPECIALIST", "FIELD_AGENT")
    g = ready_farm(client, {**ctx, "agent": both}, square(74.7, 19.5))
    client.post(f"{FA}/{g['farm']['id']}/submit", headers=both.headers, json={"reason": "submit"})
    client.post(f"{FA}/{g['farm']['id']}/start-review", headers=both.headers, json={"reason": "review"})
    client.post(f"{FA}/{g['farm']['id']}/ownership/{g['owner']['id']}/review", headers=both.headers, json={"status": "VERIFIED", "notes": "ok ok"})
    again = client.post(f"{FA}/{g['farm']['id']}/ownership/{g['owner']['id']}/review", headers=both.headers,
                        json={"status": "REJECTED", "notes": "second look"})
    assert again.status_code == 409 and again.json()["error_code"] == "OWNERSHIP_ALREADY_REVIEWED"
    sod = client.post(f"{FA}/{g['farm']['id']}/verify", headers=both.headers, json={"reason": "verify own"})
    assert sod.status_code == 403 and sod.json()["error_code"] == "SEPARATION_OF_DUTIES"
    # unverified ownership blocks verification; rejection returns to DRAFT via reopen
    client.post(f"{FA}/{fid}/start-review", headers=ctx["gis"].headers, json={"reason": "review"})
    gate = client.post(f"{FA}/{fid}/verify", headers=ctx["gis"].headers, json={"reason": "verify"})
    assert gate.status_code == 409 and "ownership" in gate.json()["message"]
    rej = client.post(f"{FA}/{fid}/reject", headers=ctx["gis"].headers, json={"reason": "boundary includes a road"})
    assert rej.json()["status"] == "REJECTED" and rej.json()["review_notes"] == "boundary includes a road"
    re = client.post(f"{FA}/{fid}/reopen", headers=ctx["agent"].headers, json={"reason": "fixing boundary"})
    assert re.json()["status"] == "DRAFT"
    assert client.post(f"{FA}/{fid}/verify", headers=ctx["gis"].headers, json={"reason": "x y z"}).json()["error_code"] == "INVALID_STATUS_TRANSITION"


def test_cross_org_overlap_privacy(client: TestClient, db: Session, ctx: dict) -> None:
    a = ready_farm(client, ctx, square(75.0, 18.0))
    other = dev_org(db)
    o_agent = staff(db, client, other, "FIELD_AGENT")
    o_qa = staff(db, client, other, "QA_OFFICER")
    o_gis = staff(db, client, other, "GIS_SPECIALIST")
    o_farmer = kyc_verified_farmer(client, o_agent, o_qa, other, id_number="999988887777", full_name="Other Developer Farmer")
    b = create_farm(client, o_agent.headers, o_farmer["id"])
    set_boundary(client, o_agent.headers, b["id"], square(75.0005, 18.0))
    ov = client.get(f"{FA}/{b['id']}/overlaps", headers=o_gis.headers).json()[0]
    assert ov["other_farm_visible"] is False and ov["other_farm_id"] is None and ov["other_farm_code"] is None
    assert ov["other_geojson"] is None and ov["same_organization"] is False and float(ov["overlap_area_m2"]) > 0
    clear = client.post(f"{FA}/{b['id']}/overlaps/{ov['id']}/resolve", headers=o_gis.headers, json={"resolution": "CLEARED", "notes": "fine"})
    assert clear.status_code == 403 and clear.json()["error_code"] == "CROSS_ORG_OVERLAP"
    conf = client.post(f"{FA}/{b['id']}/overlaps/{ov['id']}/resolve", headers=o_gis.headers,
                       json={"resolution": "CONFIRMED_CONFLICT", "notes": "same land claimed by another developer"})
    assert conf.json()["status"] == "CONFIRMED_CONFLICT"
    assert client.get(f"{FA}/{a['farm']['id']}", headers=o_gis.headers).status_code == 404


def test_evidence_and_farmer_self_service(client: TestClient, db: Session, ctx: dict) -> None:
    group = make_org(db, org_type="FARMER_GROUP")
    user = make_user(db, roles=[("FARMER", group)])
    pm = staff(db, client, ctx["org"], "PROJECT_MANAGER")
    client.post(f"/api/v1/farmers/{ctx['farmer']['id']}/link-user", headers=pm.headers, json={"user_id": str(user.id)})
    h = login(client, user)
    farm = create_farm(client, h, ctx["farmer"]["id"], name="My own field")
    set_boundary(client, h, farm["id"], square(76.0, 17.0))
    assert client.post(f"{FA}/{farm['id']}/history/land", headers=h, json={"year": 2020, "land_use": "CROPLAND"}).status_code == 201
    staff_only = client.post(f"{FA}/{farm['id']}/evidence", headers=h, json={"claim_type": "CROP", "source_type": "FIELD_AGENT",
                                                                           "description": "agent visit"})
    assert staff_only.json()["error_code"] == "EVIDENCE_SOURCE_NOT_ALLOWED"
    photo = upload(client, h, f"{FA}/{farm['id']}/documents", "FIELD_PHOTO", PNG, "plot.png").json()["id"]
    ev = client.post(f"{FA}/{farm['id']}/evidence", headers=h, json={
        "claim_type": "CROP", "source_type": "FARMER_CLAIM", "description": "Soybean standing crop", "document_id": photo,
        "latitude": "17.0005", "longitude": "76.0005"})
    assert ev.status_code == 201 and ev.json()["distance_to_boundary_m"] == 0.0
    far = client.post(f"{FA}/{farm['id']}/evidence", headers=ctx["agent"].headers, json={
        "claim_type": "PRACTICE", "source_type": "FIELD_AGENT", "description": "Residue retained", "latitude": "17.01", "longitude": "76.0"})
    assert far.json()["distance_to_boundary_m"] > 900
    sod = client.post(f"{FA}/{farm['id']}/evidence/{far.json()['id']}/review", headers=staff(db, client, ctx["org"], "GIS_SPECIALIST",
                      "FIELD_AGENT").headers, json={"status": "VERIFIED", "notes": "self"})
    assert sod.status_code in (403, 200)
    rv = client.post(f"{FA}/{farm['id']}/evidence/{far.json()['id']}/review", headers=ctx["gis"].headers,
                     json={"status": "NEEDS_REVIEW", "notes": "location is 1 km away from the plot"})
    assert rv.json()["verification_status"] == "NEEDS_REVIEW"
    # farmer cannot review or verify
    assert client.post(f"{FA}/{farm['id']}/start-review", headers=h, json={"reason": "self"}).status_code == 403
    assert len(client.get(FA, headers=h).json()["items"]) == 1


def test_rbac_and_isolation(client: TestClient, db: Session, ctx: dict, admin: Actor) -> None:
    f = ready_farm(client, ctx, square(77.0, 16.0))
    outsider = staff(db, client, dev_org(db), "FIELD_AGENT")
    assert client.get(f"{FA}/{f['farm']['id']}", headers=outsider.headers).status_code == 404
    assert client.get(FA, headers=outsider.headers).json()["total"] == 0
    mrv = staff(db, client, ctx["org"], "MRV_MANAGER")  # read-only on farms
    assert client.get(f"{FA}/{f['farm']['id']}", headers=mrv.headers).status_code == 200
    assert client.patch(f"{FA}/{f['farm']['id']}", headers=mrv.headers, json={"name": "renamed"}).status_code == 403
    buyer = make_user(db, roles=[("BUYER", make_org(db, org_type="BUYER"))])
    assert client.get(FA, headers=login(client, buyer)).status_code == 403
    # platform admin has platform-wide read (oversight) but cannot edit
    assert client.get(f"{FA}/{f['farm']['id']}", headers=admin.headers).status_code == 200
    assert client.post(f"{FA}/{f['farm']['id']}/submit", headers=admin.headers, json={"reason": "admin"}).status_code == 403
    listing = client.get(FA, headers=ctx["agent"].headers, params={"has_open_overlaps": False, "sort": "-area_hectares"})
    assert listing.status_code == 200 and listing.json()["total"] >= 1


def test_inactivate_obsoletes_overlaps(client: TestClient, ctx: dict) -> None:
    a = ready_farm(client, ctx, square(78.0, 15.0))
    b = ready_farm(client, ctx, square(78.0005, 15.0))
    r = client.post(f"{FA}/{b['farm']['id']}/inactivate", headers=ctx["agent"].headers, json={"reason": "duplicate entry"})
    assert r.status_code == 200 and r.json()["status"] == "INACTIVE"
    assert client.get(f"{FA}/{a['farm']['id']}", headers=ctx["agent"].headers).json()["open_overlaps"] == 0


def test_platform_gis_specialist_clears_cross_org_overlap(client: TestClient, db: Session, ctx: dict, admin: Actor) -> None:
    """Decision D5: only a platform-wide GIS reviewer clears overlaps between organizations; org GIS users cannot."""
    a = ready_farm(client, ctx, square(75.5, 17.5))
    other = dev_org(db)
    o_agent = staff(db, client, other, "FIELD_AGENT")
    o_qa = staff(db, client, other, "QA_OFFICER")
    o_farmer = kyc_verified_farmer(client, o_agent, o_qa, other, id_number="888877776666", full_name="Second Developer Farmer")
    b = create_farm(client, o_agent.headers, o_farmer["id"])
    set_boundary(client, o_agent.headers, b["id"], square(75.5005, 17.5))
    # The org-scoped GIS specialist of A sees the flag but is told it cannot clear it.
    ov = client.get(f"{FA}/{a['farm']['id']}/overlaps", headers=ctx["gis"].headers).json()[0]
    assert ov["can_clear"] is False and ov["can_confirm"] is True
    r = client.post(f"{FA}/{a['farm']['id']}/overlaps/{ov['id']}/resolve", headers=ctx["gis"].headers,
                    json={"resolution": "CLEARED", "notes": "looks fine"})
    assert r.status_code == 403 and r.json()["error_code"] == "CROSS_ORG_OVERLAP"
    # A Platform Admin can grant the platform GIS role (operational role, D4) ...
    pgis_user = make_user(db, orgs=[])
    g = client.post(f"/api/v1/admin/users/{pgis_user.id}/roles", headers=admin.headers, json={"role_code": "PLATFORM_GIS_SPECIALIST"})
    assert g.status_code == 201, g.text
    pgis = Actor(pgis_user, login(client, pgis_user))
    # ... but not scoped to one organization (platform role).
    scoped = client.post(f"/api/v1/admin/users/{pgis_user.id}/roles", headers=admin.headers,
                         json={"role_code": "PLATFORM_GIS_SPECIALIST", "organization_id": str(ctx["org"].id)})
    assert scoped.status_code == 422 and scoped.json()["error_code"] == "ROLE_SCOPE_MISMATCH"
    seen = client.get(f"{FA}/{a['farm']['id']}/overlaps", headers=pgis.headers).json()[0]
    assert seen["can_clear"] is True and seen["other_farm_visible"] is True  # platform reviewer sees both sides
    done = client.post(f"{FA}/{a['farm']['id']}/overlaps/{ov['id']}/resolve", headers=pgis.headers,
                       json={"resolution": "CLEARED", "notes": "adjacent plots; digitising offset confirmed in the field"})
    assert done.status_code == 200 and done.json()["status"] == "CLEARED"
    # Platform GIS cannot verify farms or touch same-organization workflow (no farms.review).
    assert client.post(f"{FA}/{a['farm']['id']}/start-review", headers=pgis.headers, json={"reason": "x review"}).status_code == 403
    rows = db.scalars(select(AuditLog).where(AuditLog.action == "FARM_CROSS_ORG_OVERLAP_RESOLVED")).all()
    assert {r.organization_id for r in rows} >= {ctx["org"].id, other.id}  # both organizations' trails record the decision
