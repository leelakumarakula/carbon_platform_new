"""Farmer onboarding: registration, KYC (privacy, duplicates, separation of duties), consents, agreements,
bank accounts (encryption, masking), self-service, RBAC and organization isolation."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import AuditLog, Farmer, FarmerBankAccount, Notification, WorkflowEvent
from app.security import crypto
from tests.conftest import login, make_org, make_user
from tests.phase2 import create_farmer, dev_org, kyc_verified_farmer, register, staff, upload

F = "/api/v1/farmers"


@pytest.fixture()
def org(db: Session):  # type: ignore[no-untyped-def]
    return dev_org(db)


@pytest.fixture()
def pm(db: Session, client: TestClient, org):  # type: ignore[no-untyped-def]
    return staff(db, client, org, "PROJECT_MANAGER")


@pytest.fixture()
def qa(db: Session, client: TestClient, org):  # type: ignore[no-untyped-def]
    return staff(db, client, org, "QA_OFFICER")


def test_create_farmer_generates_code_and_audits(client: TestClient, db: Session, pm, org) -> None:  # type: ignore[no-untyped-def]
    f = create_farmer(client, pm.headers, org, email="Asha@Example.com", preferred_language="mr")
    assert f["farmer_code"].startswith("FRM-") and len(f["farmer_code"]) == 15 and f["status"] == "DRAFT"
    assert {c["contact_type"] for c in f["contacts"]} == {"PHONE", "EMAIL"} and f["environment"] == "LIVE"
    assert f["organization_name"] == org.name and f["kyc"]["id_number_masked"] is None
    assert db.scalars(select(AuditLog).where(AuditLog.action == "FARMER_CREATED", AuditLog.entity_id == f["id"])).one()


def test_only_farmer_managing_org_types(client: TestClient, db: Session) -> None:
    lab = make_org(db, org_type="LABORATORY")
    u = make_user(db, roles=[("PROJECT_MANAGER", lab)])
    r = client.post(F, headers=login(client, u), json={"organization_id": str(lab.id), "full_name": "X Y", "country": "IN"})
    assert r.status_code == 422 and r.json()["error_code"] == "ORGANIZATION_TYPE_NOT_ALLOWED"


def test_registration_requires_phone_and_location(client: TestClient, pm, org) -> None:  # type: ignore[no-untyped-def]
    f = create_farmer(client, pm.headers, org, primary_phone=None, village=None, district=None)
    r = client.post(f"{F}/{f['id']}/status", headers=pm.headers, json={"status": "REGISTERED", "reason": "try"})
    assert r.status_code == 409 and r.json()["error_code"] == "REQUIREMENTS_NOT_MET"
    assert len(r.json()["details"]["missing"]) == 2
    bad = client.post(f"{F}/{f['id']}/status", headers=pm.headers, json={"status": "ACTIVE", "reason": "skip ahead"})
    assert bad.status_code == 409 and bad.json()["error_code"] == "INVALID_STATUS_TRANSITION"


def test_kyc_flow_privacy_and_separation_of_duties(client: TestClient, db: Session, pm, qa, org) -> None:  # type: ignore[no-untyped-def]
    f = create_farmer(client, pm.headers, org)
    register(client, pm.headers, f["id"])
    no_doc = client.post(f"{F}/{f['id']}/kyc", headers=pm.headers,
                         json={"id_type": "NATIONAL_ID", "id_number": "1234 5678 9012", "document_id": f["id"]})
    assert no_doc.json()["error_code"] == "DOCUMENT_NOT_ATTACHED"
    land = upload(client, pm.headers, f"{F}/{f['id']}/documents", "LAND_RECORD").json()["id"]
    wrong = client.post(f"{F}/{f['id']}/kyc", headers=pm.headers, json={"id_type": "NATIONAL_ID", "id_number": "1234 5678 9012", "document_id": land})
    assert wrong.json()["error_code"] == "DOCUMENT_WRONG_CATEGORY"
    doc = upload(client, pm.headers, f"{F}/{f['id']}/documents", "KYC_ID").json()["id"]
    r = client.post(f"{F}/{f['id']}/kyc", headers=pm.headers, json={"id_type": "NATIONAL_ID", "id_number": "1234 5678 9012", "document_id": doc})
    assert r.status_code == 200 and r.json()["status"] == "KYC_PENDING"
    assert r.json()["kyc"]["id_number_masked"] == "••••9012"
    # the raw identity number exists nowhere in the database
    row = db.get(Farmer, f["id"])
    assert row.kyc_id_last4 == "9012" and "123456789012" not in (row.kyc_id_hash or "")
    leaked = db.execute(text("SELECT COUNT(*) FROM audit_logs WHERE new_value LIKE '%56789012%' OR old_value LIKE '%56789012%'")).scalar()
    assert leaked == 0
    # submitter cannot verify own submission
    self_review = client.post(f"{F}/{f['id']}/kyc/decision", headers=pm.headers, json={"decision": "VERIFIED", "notes": "looks ok"})
    assert self_review.status_code == 403 and self_review.json()["error_code"] == "SEPARATION_OF_DUTIES"
    ok = client.post(f"{F}/{f['id']}/kyc/decision", headers=qa.headers, json={"decision": "VERIFIED", "notes": "id matches photo"})
    assert ok.status_code == 200 and ok.json()["status"] == "KYC_VERIFIED" and ok.json()["kyc"]["verified_by"] == str(qa.user.id)
    events = db.scalars(select(WorkflowEvent.to_status).where(WorkflowEvent.entity_id == f["id"]).order_by(WorkflowEvent.id)).all()
    assert list(events) == ["REGISTERED", "KYC_PENDING", "KYC_VERIFIED"]
    assert db.scalars(select(Notification).where(Notification.recipient_user_id == pm.user.id,
                                                 Notification.event_type == "FARMER_KYC_VERIFIED")).first()


def test_kyc_return_and_duplicate_flag(client: TestClient, db: Session, pm, qa, org) -> None:  # type: ignore[no-untyped-def]
    kyc_verified_farmer(client, pm, qa, org, id_number="5555-6666-7777")
    f = create_farmer(client, pm.headers, org, full_name="Second Person")
    register(client, pm.headers, f["id"])
    doc = upload(client, pm.headers, f"{F}/{f['id']}/documents", "KYC_ID").json()["id"]
    r = client.post(f"{F}/{f['id']}/kyc", headers=pm.headers, json={"id_type": "NATIONAL_ID", "id_number": "555566667777", "document_id": doc})
    assert r.json()["kyc"]["possible_duplicate"] is True
    blocked = client.post(f"{F}/{f['id']}/kyc/decision", headers=qa.headers, json={"decision": "VERIFIED", "notes": "looks fine"})
    assert blocked.status_code == 409 and blocked.json()["error_code"] == "DUPLICATE_REVIEW_REQUIRED"
    # the submitter cannot withdraw a pending KYC through a plain status change: only the independent reviewer returns it
    skip = client.post(f"{F}/{f['id']}/status", headers=pm.headers, json={"status": "REGISTERED", "reason": "withdraw"})
    assert skip.status_code == 409 and skip.json()["error_code"] == "USE_KYC_WORKFLOW"
    back = client.post(f"{F}/{f['id']}/kyc/decision", headers=qa.headers, json={"decision": "RETURNED", "notes": "duplicate identity"})
    assert back.json()["status"] == "REGISTERED" and back.json()["kyc"]["notes"] == "duplicate identity"


def test_consents_and_activation(client: TestClient, db: Session, pm, qa, org) -> None:  # type: ignore[no-untyped-def]
    f = kyc_verified_farmer(client, pm, qa, org)
    act = client.post(f"{F}/{f['id']}/status", headers=pm.headers, json={"status": "ACTIVE", "reason": "onboarded"})
    assert act.status_code == 409 and "Personal data processing consent granted (version 1)" in act.json()["message"]
    body = {"consent_type": "data_processing", "consent_text_version": "DPC-2026-01", "language": "mr", "capture_method": "PAPER_SIGNED"}
    c = client.post(f"{F}/{f['id']}/consents", headers=pm.headers, json=body)
    assert c.status_code == 201 and c.json()["consents"][0]["consent_type"] == "DATA_PROCESSING"
    assert client.post(f"{F}/{f['id']}/consents", headers=pm.headers, json=body).json()["error_code"] == "CONSENT_ALREADY_GRANTED"
    act = client.post(f"{F}/{f['id']}/status", headers=pm.headers, json={"status": "ACTIVE", "reason": "onboarded"})
    assert act.status_code == 200 and act.json()["status"] == "ACTIVE"
    cid = c.json()["consents"][0]["id"]
    w = client.post(f"{F}/{f['id']}/consents/{cid}/withdraw", headers=pm.headers, json={"reason": "farmer request"})
    assert w.json()["consents"][0]["status"] == "WITHDRAWN"
    again = client.post(f"{F}/{f['id']}/consents", headers=pm.headers, json=body | {"consent_text_version": "DPC-2026-02"}).json()
    assert [c["status"] for c in again["consents"]] == ["WITHDRAWN", "GRANTED"]  # history kept
    sus = client.post(f"{F}/{f['id']}/status", headers=pm.headers, json={"status": "SUSPENDED", "reason": "investigation"})
    assert sus.json()["status"] == "SUSPENDED"
    assert client.post(f"{F}/{f['id']}/status", headers=pm.headers, json={"status": "ACTIVE", "reason": "cleared"}).json()["status"] == "ACTIVE"


def test_consent_definitions_are_versioned_and_drive_activation(client: TestClient, db: Session, pm, qa, org, admin) -> None:  # type: ignore[no-untyped-def]
    """Decision D3: consent types are configuration; activation requires the current version of every required one."""
    defs = client.get("/api/v1/consent-definitions", headers=pm.headers).json()
    assert [(d["consent_type"], d["version"], d["required_for_activation"]) for d in defs] == [("DATA_PROCESSING", 1, True)]
    assert defs[0]["text_version"] == "DATA_PROCESSING-v1"                   # the consent form prefills the wording identifier from it
    # Only consent configurers may publish; project managers cannot.
    new_type = {"consent_type": "photo_use", "title": "Use of field photos", "required_for_activation": False}
    assert client.post("/api/v1/admin/consent-definitions", headers=pm.headers, json=new_type).status_code == 403
    r = client.post("/api/v1/admin/consent-definitions", headers=admin.headers, json=new_type)
    assert r.status_code == 201 and r.json()["consent_type"] == "PHOTO_USE" and r.json()["version"] == 1
    f = kyc_verified_farmer(client, pm, qa, org, id_number="2222 3333 4444")
    base = {"consent_text_version": "DPC-2026-01", "language": "mr", "capture_method": "PAPER_SIGNED"}
    unknown = client.post(f"{F}/{f['id']}/consents", headers=pm.headers, json=base | {"consent_type": "MARKETING"})
    assert unknown.status_code == 422 and unknown.json()["error_code"] == "UNKNOWN_CONSENT_TYPE"
    granted = client.post(f"{F}/{f['id']}/consents", headers=pm.headers, json=base | {"consent_type": "DATA_PROCESSING"}).json()
    c = granted["consents"][0]
    assert c["version"] == 1 and c["required_for_activation"] is True and c["granted"] is True and c["is_current_version"] is True
    # Publishing version 2 retires version 1; the farmer's v1 grant no longer satisfies activation.
    v2 = client.post("/api/v1/admin/consent-definitions", headers=admin.headers,
                     json={"consent_type": "DATA_PROCESSING", "title": "Personal data processing", "text_version": "DPC-2027-01",
                           "required_for_activation": True}).json()
    assert v2["version"] == 2
    all_defs = {(d["consent_type"], d["version"]): d["status"] for d in client.get("/api/v1/admin/consent-definitions", headers=admin.headers).json()}
    assert all_defs[("DATA_PROCESSING", 1)] == "RETIRED" and all_defs[("DATA_PROCESSING", 2)] == "ACTIVE"
    act = client.post(f"{F}/{f['id']}/status", headers=pm.headers, json={"status": "ACTIVE", "reason": "onboarded"})
    assert act.status_code == 409 and "(version 2)" in act.json()["message"]
    again = client.post(f"{F}/{f['id']}/consents", headers=pm.headers, json=base | {"consent_type": "DATA_PROCESSING",
                                                                                     "consent_text_version": "DPC-2027-01"}).json()
    assert [(x["version"], x["status"]) for x in again["consents"]] == [(1, "SUPERSEDED"), (2, "GRANTED")]  # history kept
    assert client.post(f"{F}/{f['id']}/status", headers=pm.headers, json={"status": "ACTIVE", "reason": "onboarded"}).status_code == 200
    # Retiring PHOTO_USE (not required) is audited.
    rid = next(d["id"] for d in client.get("/api/v1/admin/consent-definitions", headers=admin.headers).json() if d["consent_type"] == "PHOTO_USE")
    assert client.post(f"/api/v1/admin/consent-definitions/{rid}/retire", headers=admin.headers, json={"reason": "no longer used"}).json()["status"] == "RETIRED"
    from sqlalchemy import select

    from app.models import AuditLog
    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.entity_type == "consent_definition")).all())
    assert {"CONSENT_DEFINITION_PUBLISHED", "CONSENT_DEFINITION_RETIRED"} <= actions


def test_identity_locked_after_kyc(client: TestClient, pm, qa, org) -> None:  # type: ignore[no-untyped-def]
    f = kyc_verified_farmer(client, pm, qa, org)
    r = client.patch(f"{F}/{f['id']}", headers=pm.headers, json={"full_name": "Someone Else"})
    assert r.status_code == 409 and r.json()["error_code"] == "IDENTITY_LOCKED"
    assert client.patch(f"{F}/{f['id']}", headers=pm.headers, json={"village": "Ozar"}).json()["village"] == "Ozar"


def test_agreements(client: TestClient, pm, org) -> None:  # type: ignore[no-untyped-def]
    f = create_farmer(client, pm.headers, org)
    register(client, pm.headers, f["id"])
    a = client.post(f"{F}/{f['id']}/agreements", headers=pm.headers,
                    json={"agreement_type": "program_participation", "template_version": "PP-1.0", "effective_from": "2026-01-01"})
    assert a.status_code == 201
    ag = a.json()["agreements"][0]
    assert ag["agreement_number"].startswith("AGR-") and ag["status"] == "DRAFT"
    photo_doc = upload(client, pm.headers, f"{F}/{f['id']}/documents", "OTHER").json()["id"]
    wrong = client.post(f"{F}/{f['id']}/agreements/{ag['id']}/sign", headers=pm.headers,
                        json={"signed_document_id": photo_doc, "signature_method": "PAPER_SIGNED"})
    assert wrong.json()["error_code"] == "DOCUMENT_WRONG_CATEGORY"
    doc = upload(client, pm.headers, f"{F}/{f['id']}/documents", "AGREEMENT").json()["id"]
    s = client.post(f"{F}/{f['id']}/agreements/{ag['id']}/sign", headers=pm.headers, json={"signed_document_id": doc, "signature_method": "THUMBPRINT"})
    assert s.json()["agreements"][0]["status"] == "SIGNED"
    void = client.post(f"{F}/{f['id']}/agreements/{ag['id']}/status", headers=pm.headers, json={"status": "VOID", "reason": "mistake"})
    assert void.json()["error_code"] == "INVALID_STATUS_TRANSITION"
    t = client.post(f"{F}/{f['id']}/agreements/{ag['id']}/status", headers=pm.headers, json={"status": "TERMINATED", "reason": "farmer exit"})
    assert t.json()["agreements"][0]["status"] == "TERMINATED"


def test_bank_accounts_encrypted_masked_and_verified_by_finance(client: TestClient, db: Session, pm, org) -> None:  # type: ignore[no-untyped-def]
    f = create_farmer(client, pm.headers, org)
    body = {"account_holder_name": "Asha Patil", "bank_name": "State Bank", "routing_code": "sbin0001234", "account_number": "0012 3456 7890"}
    r = client.post(f"{F}/{f['id']}/bank-accounts", headers=pm.headers, json=body)
    assert r.status_code == 201
    acct = r.json()["bank_accounts"][0]
    assert acct["account_number_masked"] == "••••7890" and acct["routing_code"] == "SBIN0001234" and acct["status"] == "PENDING_VERIFICATION"
    assert "account_number" not in acct
    row = db.get(FarmerBankAccount, acct["id"])
    assert "001234567890" not in row.account_number_enc and crypto.decrypt(row.account_number_enc) == "001234567890"
    leaked = db.execute(text("SELECT COUNT(*) FROM audit_logs WHERE new_value LIKE '%34567890%'")).scalar()
    assert leaked == 0
    assert client.post(f"{F}/{f['id']}/bank-accounts", headers=pm.headers, json=body).json()["error_code"] == "BANK_ACCOUNT_EXISTS"
    assert client.post(f"{F}/{f['id']}/bank-accounts/{acct['id']}/decision", headers=pm.headers,
                       json={"decision": "VERIFIED", "notes": "ok"}).status_code == 403
    fin = staff(db, client, org, "FINANCE_MANAGER")
    v = client.post(f"{F}/{f['id']}/bank-accounts/{acct['id']}/decision", headers=fin.headers, json={"decision": "VERIFIED", "notes": "penny drop ok"})
    assert v.json()["bank_accounts"][0]["status"] == "VERIFIED"


def test_list_search_scope_and_isolation(client: TestClient, db: Session, pm, org) -> None:  # type: ignore[no-untyped-def]
    create_farmer(client, pm.headers, org, full_name="Kamala Unique")
    other_org = dev_org(db)
    other_pm = staff(db, client, other_org, "PROJECT_MANAGER")
    theirs = create_farmer(client, other_pm.headers, other_org, full_name="Kamala Elsewhere")
    mine = client.get(F, headers=pm.headers, params={"search": "Kamala"}).json()
    assert [x["full_name"] for x in mine["items"]] == ["Kamala Unique"] and mine["items"][0]["farm_count"] == 0
    assert client.get(f"{F}/{theirs['id']}", headers=pm.headers).status_code == 404
    assert client.patch(f"{F}/{theirs['id']}", headers=pm.headers, json={"village": "x"}).status_code == 404
    assert client.get(F, headers=pm.headers, params={"organization_id": str(other_org.id)}).status_code == 403
    # buyers and lab staff have no farmer access at all
    buyer = make_user(db, roles=[("BUYER", make_org(db, org_type="BUYER"))])
    assert client.get(F, headers=login(client, buyer)).status_code == 403
    # read-only roles cannot create or change
    gis = staff(db, client, org, "GIS_SPECIALIST")
    assert client.post(F, headers=gis.headers, json={"organization_id": str(org.id), "full_name": "No Way", "country": "IN"}).status_code == 403


def test_farmer_self_service(client: TestClient, db: Session, pm, org) -> None:  # type: ignore[no-untyped-def]
    f = create_farmer(client, pm.headers, org)
    group = make_org(db, org_type="FARMER_GROUP")
    user = make_user(db, roles=[("FARMER", group)])
    linked = client.post(f"{F}/{f['id']}/link-user", headers=pm.headers, json={"user_id": str(user.id)})
    assert linked.status_code == 200 and linked.json()["user_id"] == str(user.id)
    h = login(client, user)
    me = client.get(f"{F}/me", headers=h).json()
    assert me["id"] == f["id"] and me["is_self"] is True and me["can_verify_kyc"] is False
    assert client.get(F, headers=h).json()["total"] == 1
    c = client.post(f"{F}/{f['id']}/contacts", headers=h, json={"contact_type": "ALTERNATE_PHONE", "value": "+91 90000 00000"})
    assert c.status_code == 201
    assert client.post(f"{F}/{f['id']}/status", headers=h, json={"status": "REGISTERED", "reason": "self"}).status_code == 200
    # cannot see others, cannot verify, cannot create agreements, cannot suspend
    other = create_farmer(client, pm.headers, org, full_name="Neighbour")
    assert client.get(f"{F}/{other['id']}", headers=h).status_code == 404
    assert client.post(f"{F}/{f['id']}/agreements", headers=h, json={"agreement_type": "PROGRAM", "template_version": "1"}).status_code == 403
    another = make_user(db, roles=[("FARMER", group)])
    dup = client.post(f"{F}/{other['id']}/link-user", headers=pm.headers, json={"user_id": str(user.id)})
    assert dup.json()["error_code"] == "USER_ALREADY_LINKED"
    assert client.get(f"{F}/me", headers=login(client, another)).status_code == 404
