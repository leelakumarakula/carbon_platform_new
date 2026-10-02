"""Phase 4 — standard → activity → methodology → version: catalog, versioning with separation of duties, candidate
evaluation (applicable / not applicable / missing data / evidence required), specialist review, confirmation and lock,
version selection and history, permissions and audit."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import AuditLog, MethodologyChangeHistory
from tests.conftest import Actor, login, make_org, make_user
from tests.phase2 import staff
from tests.phase3 import PR, Team, catalog, team
from tests.phase4 import (
    ALM_RULES,
    WETLAND_RULES,
    M,
    approved_version,
    methodology,
    project_at_activity_selected,
    specialists,
)


@pytest.fixture()
def t(db: Session, client: TestClient) -> Team:
    return team(db, client)


@pytest.fixture()
def setup(db: Session, client: TestClient) -> dict:
    cat = catalog(db)
    author, approver = specialists(db, client)
    s1, a1 = str(cat["s1"].id), str(cat["a1"].id)
    alm = methodology(client, author, s1, [a1], f"TALM-{cat['s1'].code[-6:]}")
    rice = methodology(client, author, s1, [a1], f"TRICE-{cat['s1'].code[-6:]}")
    v1 = approved_version(client, author, approver, alm["id"], "1.0", ALM_RULES)
    rv = approved_version(client, author, approver, rice["id"], "1.0", WETLAND_RULES)
    return {"cat": cat, "author": author, "approver": approver, "alm": alm, "rice": rice, "alm_v1": v1, "rice_v1": rv}


def _actions(db: Session, entity_type: str, entity_id: str) -> set[str]:
    return set(db.scalars(select(AuditLog.action).where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)).all())


def _evaluate(client: TestClient, actor: Actor, pid: str, declared: dict | None = None):  # type: ignore[no-untyped-def]
    return client.post(f"{PR}/{pid}/methodology/candidates", headers=actor.headers, json={"declared_facts": declared or {}})


def _candidate(ev: dict, code_prefix: str) -> dict:
    return next(c for c in ev["candidates"] if c["methodology_code"].startswith(code_prefix))


# ---------------------------------------------------------------- catalog & versioning
def test_catalog_permissions(client: TestClient, db: Session, t: Team) -> None:
    cat = catalog(db)
    body = {"code": "NOPE", "name": "Not allowed", "standard_id": str(cat["s1"].id), "activity_ids": [str(cat["a1"].id)]}
    for role in ("PROJECT_MANAGER", "FINANCE_MANAGER", "QA_OFFICER", "FIELD_AGENT"):
        assert client.post(M, headers=staff(db, client, t.org, role).headers, json=body).status_code == 403, role
    lab = make_user(db, roles=[("LAB_TECHNICIAN", make_org(db, org_type="LABORATORY"))])
    assert client.post(M, headers=login(client, lab), json=body).status_code == 403
    assert client.get(M, headers=login(client, lab)).status_code == 403  # lab has no methodology access at all
    author, _ = specialists(db, client)
    bad = body | {"activity_ids": [str(cat["a1"].id), str(cat["a2"].id)], "standard_id": str(cat["s2"].id), "code": "BAD-LINK"}
    assert client.post(M, headers=author.headers, json=bad).json()["error_code"] == "ACTIVITY_NOT_IN_STANDARD"
    assert client.get(M, headers=t.pm.headers).status_code == 200  # project managers can read the catalog


def test_version_lifecycle_separation_of_duties_and_history(client: TestClient, db: Session) -> None:
    cat = catalog(db)
    author, approver = specialists(db, client)
    m = methodology(client, author, str(cat["s1"].id), [str(cat["a1"].id)], "LIFE-1", source_url="https://example.org/m")
    v = client.post(f"{M}/{m['id']}/versions", headers=author.headers, json={"version_label": "1.0"}).json()
    vid = v["id"]
    assert v["status"] == "DRAFT" and v["calculation_readiness"] == "NOT_PRODUCTION_READY"
    r = client.post(f"{M}/versions/{vid}/submit", headers=author.headers, json={"reason": "go now"})
    assert r.status_code == 409 and set(r.json()["details"]["missing"]) == {
        "at least one applicability rule", "the authoritative source (name, URL or document)", "an effective date"}
    bad_rule = {**ALM_RULES[0], "operator": "IN", "expected_value": "IN"}
    assert client.post(f"{M}/versions/{vid}/rules/applicability", headers=author.headers, json=bad_rule).json()["error_code"] == "INVALID_RULE"
    for rule in ALM_RULES[:2]:
        assert client.post(f"{M}/versions/{vid}/rules/applicability", headers=author.headers, json=rule).status_code == 201
    mon = {"rule_code": "M1", "title": "Soil organic carbon stock", "parameter": "SOC stock", "unit": "t C/ha", "frequency": "per verification"}
    assert client.post(f"{M}/versions/{vid}/rules/monitoring", headers=author.headers, json=mon).status_code == 201
    calc = {"rule_code": "C1", "title": "Removals by SOC change", "step": "REMOVALS", "equation_reference": "Source eq. reference only"}
    c = client.post(f"{M}/versions/{vid}/rules/calculation", headers=author.headers, json=calc).json()
    assert c["data"]["implementation_status"] == "NOT_IMPLEMENTED"  # documentation only; no executable formula
    client.patch(f"{M}/versions/{vid}", headers=author.headers, json={"effective_from": "2020-01-01", "source_name": "TEST source"})
    assert client.post(f"{M}/versions/{vid}/submit", headers=author.headers, json={"reason": "ready for approval"}).json()["status"] == "IN_REVIEW"
    # Drafts never become active by themselves, and the submitter cannot approve.
    self_ok = client.post(f"{M}/versions/{vid}/approve", headers=author.headers, json={"reason": "self"})
    assert self_ok.status_code == 403 and self_ok.json()["error_code"] == "SEPARATION_OF_DUTIES"
    pm = staff(db, client, make_org(db), "PROJECT_MANAGER")
    assert client.post(f"{M}/versions/{vid}/approve", headers=pm.headers, json={"reason": "pm says ok"}).status_code == 403
    v = client.post(f"{M}/versions/{vid}/approve", headers=approver.headers, json={"reason": "checked against the source"}).json()
    assert v["status"] == "APPROVED" and v["approved_by"] == str(approver.user.id)
    # Approved versions are never edited.
    r = client.post(f"{M}/versions/{vid}/rules/applicability", headers=author.headers, json=ALM_RULES[2])
    assert r.status_code == 409 and r.json()["error_code"] == "VERSION_NOT_EDITABLE"
    # A new version copies the rules; editing a copied rule set bumps its revision counter.
    v2 = client.post(f"{M}/{m['id']}/versions", headers=author.headers,
                     json={"version_label": "2.0", "effective_from": "2026-01-01", "source_name": "TEST source v2", "based_on_version_id": vid}).json()
    assert v2["rule_counts"] == {"applicability": 2, "monitoring": 1, "calculation": 1, "general": 0} and v2["rules_version"] == 1
    client.post(f"{M}/versions/{v2['id']}/rules/applicability", headers=author.headers, json=ALM_RULES[2])
    v2 = client.get(f"{M}/versions/{v2['id']}", headers=author.headers).json()
    assert (v2["rules_version"], v2["monitoring_rules_version"], v2["calculation_rules_version"]) == (2, 1, 1)
    client.post(f"{M}/versions/{v2['id']}/submit", headers=author.headers, json={"reason": "v2 ready"})
    client.post(f"{M}/versions/{v2['id']}/approve", headers=approver.headers, json={"reason": "v2 checked", "supersedes_version_id": vid})
    statuses = {x["version_label"]: x["status"] for x in client.get(f"{M}/{m['id']}", headers=author.headers).json()["versions"]}
    assert statuses == {"1.0": "SUPERSEDED", "2.0": "APPROVED"}
    hist = [h["change_type"] for h in client.get(f"{M}/{m['id']}/history", headers=pm.headers).json()]
    for change in ("METHODOLOGY_CREATED", "METHODOLOGY_VERSION_CREATED", "METHODOLOGY_RULE_ADDED", "METHODOLOGY_VERSION_SUBMITTED",
                   "METHODOLOGY_VERSION_APPROVED", "METHODOLOGY_VERSION_SUPERSEDED"):
        assert change in hist, change
    assert {"METHODOLOGY_CREATED", "METHODOLOGY_RULE_ADDED"} <= _actions(db, "methodology", m["id"])


def test_change_history_is_append_only(client: TestClient, db: Session) -> None:
    from sqlalchemy.exc import DBAPIError

    from app.core.database import get_engine
    from app.models import Methodology
    cat = catalog(db)
    with get_engine().connect() as conn:
        trans = conn.begin()
        s = Session(bind=conn)
        from app.models import Standard
        std = Standard(code="APPEND-STD", name="x", program_type="OTHER")
        s.add(std)
        s.flush()
        m = Methodology(code="APPEND-M", name="x", standard_id=std.id)
        s.add(m)
        s.flush()
        s.add(MethodologyChangeHistory(methodology_id=m.id, change_type="TEST", summary="x"))
        s.flush()
        with pytest.raises(DBAPIError) as e:
            conn.execute(text("UPDATE dbo.methodology_change_history SET summary = N'changed'"))
        assert "append-only" in str(e.value)
        if trans.is_active:
            trans.rollback()
    assert cat


# ---------------------------------------------------------------- candidate evaluation
def test_candidates_applicable_not_applicable_missing_and_evidence(client: TestClient, db: Session, t: Team, setup: dict) -> None:
    p = project_at_activity_selected(client, t, setup["cat"], 76.10, 23.10, "7100 2000 3000")
    pid = p["id"]
    # A draft version is never a candidate.
    client.post(f"{M}/{setup['alm']['id']}/versions", headers=setup["author"].headers,
                json={"version_label": "9.9-draft", "effective_from": "2020-01-01"})
    ev = _evaluate(client, t.pm, pid)
    assert ev.status_code == 201, ev.text
    ev = ev.json()
    assert ev["candidate_count"] == 2 and {c["version_label"] for c in ev["candidates"]} == {"1.0"}
    alm, rice = _candidate(ev, "TALM"), _candidate(ev, "TRICE")
    assert rice["outcome"] == "NOT_APPLICABLE"
    w1 = rice["rules"][0]
    assert (w1["check"], w1["actual"], w1["expected"]) == ("FAIL", ["CROPLAND"], ["WETLAND"]) and "does not satisfy" in w1["reason"]
    assert alm["outcome"] == "NEEDS_INFORMATION"  # additionality not recorded yet
    a6 = next(r for r in alm["rules"] if r["rule_code"] == "A6")
    assert a6["check"] == "MISSING" and a6["effect"] == "NEEDS_INFORMATION"
    assert all(r["check"] == "PASS" for r in alm["rules"] if r["rule_code"] != "A6")
    assert ev["facts"]["land_use_history_years_min"] == {"value": 5, "source": "FARM_DATA", "detail": "fewest years of land-use history of any farm"}
    assert client.get(f"{PR}/{pid}", headers=t.pm.headers).json()["status"] == "METHODOLOGY_REVIEW"
    # Declared facts cannot override project data; a declared fact behind an evidence requirement → EVIDENCE_REQUIRED.
    r = _evaluate(client, t.pm, pid, {"country": "BR"})
    assert r.status_code == 422 and r.json()["error_code"] == "DECLARED_FACT_CONFLICT"
    ev2 = _evaluate(client, t.pm, pid, {"additionality_assessment": "COMPLETED"}).json()
    alm2 = _candidate(ev2, "TALM")
    assert alm2["outcome"] == "EVIDENCE_REQUIRED" and alm2["evidence_requirements"] == ["Additionality demonstration document"]
    assert ev2["facts"]["additionality_assessment"]["source"] == "DECLARED"
    hist = client.get(f"{PR}/{pid}/methodology/evaluations", headers=t.pm.headers).json()
    assert len(hist) == 2  # every evaluation is kept
    assert "PROJECT_METHODOLOGY_CANDIDATES_EVALUATED" in _actions(db, "project", pid)


def test_missing_farm_data_needs_information(client: TestClient, db: Session, t: Team, setup: dict) -> None:
    p = project_at_activity_selected(client, t, setup["cat"], 76.20, 23.20, "7200 2000 3000", history=False)
    ev = _evaluate(client, t.pm, p["id"]).json()
    alm = _candidate(ev, "TALM")
    assert alm["outcome"] == "NEEDS_INFORMATION"
    assert {r["rule_code"] for r in alm["rules"] if r["check"] == "MISSING"} >= {"A2", "A3", "A6"}


def test_evaluation_permissions_and_status(client: TestClient, db: Session, t: Team, setup: dict) -> None:
    p = project_at_activity_selected(client, t, setup["cat"], 76.30, 23.30, "7300 2000 3000")
    for actor in (t.agent, t.qa, t.gis):
        assert _evaluate(client, actor, p["id"]).status_code == 403
    other = team(db, client)
    assert _evaluate(client, other.pm, p["id"]).status_code == 404
    # The platform methodology specialist may run candidates for any project (methodologies.review_project).
    assert _evaluate(client, setup["author"], p["id"]).status_code == 201


# ---------------------------------------------------------------- review, confirm, lock
def test_review_confirm_lock_and_unlock(client: TestClient, db: Session, t: Team, setup: dict) -> None:
    p = project_at_activity_selected(client, t, setup["cat"], 76.40, 23.40, "7400 2000 3000")
    pid = p["id"]
    ev = _evaluate(client, t.pm, pid, {"additionality_assessment": "COMPLETED"}).json()
    alm, rice = _candidate(ev, "TALM"), _candidate(ev, "TRICE")
    spec = setup["author"]
    rev = f"{PR}/{pid}/methodology/reviews"
    conf = f"{PR}/{pid}/methodology/confirm"
    # Not-applicable candidates cannot be recommended or confirmed.
    r = client.post(rev, headers=spec.headers, json={"evaluation_result_id": rice["id"], "recommendation": "RECOMMENDED", "notes": "try it"})
    assert r.json()["error_code"] == "CANDIDATE_NOT_ELIGIBLE"
    assert client.post(conf, headers=t.pm.headers, json={"evaluation_result_id": rice["id"], "notes": "go go"}).json()["error_code"] \
        == "CANDIDATE_NOT_ELIGIBLE"
    # Confirmation needs a specialist recommendation; PMs cannot review; evidence must be acknowledged.
    r = client.post(conf, headers=t.pm.headers, json={"evaluation_result_id": alm["id"], "notes": "go go"})
    assert r.json()["error_code"] == "SPECIALIST_REVIEW_REQUIRED"
    assert client.post(rev, headers=t.pm.headers, json={"evaluation_result_id": alm["id"], "recommendation": "RECOMMENDED",
                                                        "notes": "self review"}).status_code == 403
    r = client.post(rev, headers=spec.headers, json={"evaluation_result_id": alm["id"], "recommendation": "RECOMMENDED", "notes": "fits"})
    assert r.json()["error_code"] == "EVIDENCE_NOT_ACKNOWLEDGED"
    r = client.post(rev, headers=spec.headers, json={"evaluation_result_id": alm["id"], "recommendation": "RECOMMENDED",
                                                     "notes": "Applicability checked; additionality report requested", "evidence_acknowledged": True})
    assert r.status_code == 201
    # Unauthorized confirmation: specialist, QA, field agent and other organizations' PMs.
    for actor in (spec, t.qa, t.agent):
        assert client.post(conf, headers=actor.headers, json={"evaluation_result_id": alm["id"], "notes": "go go"}).status_code == 403
    assert client.post(conf, headers=team(db, client).pm.headers, json={"evaluation_result_id": alm["id"], "notes": "go go"}).status_code == 404
    # A newer evaluation makes the old candidate outdated.
    ev3 = _evaluate(client, t.pm, pid, {"additionality_assessment": "COMPLETED"}).json()
    assert client.post(conf, headers=t.pm.headers, json={"evaluation_result_id": alm["id"], "notes": "go go"}).json()["error_code"] \
        == "EVALUATION_OUTDATED"
    alm3 = _candidate(ev3, "TALM")
    client.post(rev, headers=spec.headers, json={"evaluation_result_id": alm3["id"], "recommendation": "RECOMMENDED",
                                                 "notes": "still fits", "evidence_acknowledged": True})
    r = client.post(conf, headers=t.pm.headers, json={"evaluation_result_id": alm3["id"], "notes": "Confirmed with the specialist"})
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["methodology_status"] == "CONFIRMED" and view["project_status"] == "METHODOLOGY_CONFIRMED"
    cur = view["current"]
    assert cur["status"] == "LOCKED" and cur["version_label"] == "1.0" and cur["calculation_readiness"] == "NOT_PRODUCTION_READY"
    proj = client.get(f"{PR}/{pid}", headers=t.pm.headers).json()
    assert proj["methodology_status"] == "CONFIRMED"
    # Locked: no more evaluations, and editing project data needs an explicit unlock first.
    assert _evaluate(client, t.pm, pid).json()["error_code"] == "PROJECT_NOT_EDITABLE"
    assert client.post(f"{PR}/{pid}/reopen", headers=t.pm.headers, json={"reason": "change farms"}).json()["error_code"] == "PROJECT_NOT_EDITABLE"
    # A newer approved version does not silently change the lock.
    author, approver = setup["author"], setup["approver"]
    approved_version(client, author, approver, setup["alm"]["id"], "1.1", ALM_RULES, based_on_version_id=setup["alm_v1"]["id"])
    view = client.get(f"{PR}/{pid}/methodology", headers=t.pm.headers).json()
    assert view["current"]["version_label"] == "1.0" and view["current"]["newer_version_available"] is True
    assert client.post(f"{PR}/{pid}/methodology/unlock", headers=t.agent.headers, json={"reason": "nope nope"}).status_code == 403
    r = client.post(f"{PR}/{pid}/methodology/unlock", headers=t.pm.headers, json={"reason": "Adopt version 1.1"})
    assert r.json()["current"] is None and r.json()["history"][0]["status"] == "UNLOCKED" and r.json()["project_status"] == "METHODOLOGY_REVIEW"
    acts = _actions(db, "project", pid)
    assert {"PROJECT_METHODOLOGY_CANDIDATES_EVALUATED", "PROJECT_METHODOLOGY_REVIEWED", "PROJECT_METHODOLOGY_CONFIRMED",
            "PROJECT_METHODOLOGY_UNLOCKED"} <= acts
    hist = [h["action"] for h in client.get(f"{PR}/{pid}/status-history", headers=t.pm.headers).json()]
    assert hist[-3:] == ["METHODOLOGY_REVIEW_STARTED", "METHODOLOGY_CONFIRMED", "METHODOLOGY_UNLOCKED"]


def test_specialist_cannot_confirm_own_recommendation(client: TestClient, db: Session, t: Team, setup: dict) -> None:
    p = project_at_activity_selected(client, t, setup["cat"], 76.50, 23.50, "7500 2000 3000")
    both = staff(db, client, t.org, "PROJECT_MANAGER")
    from app.models import UserRole
    from tests.conftest import role
    db.add(UserRole(user_id=both.user.id, role_id=role(db, "METHODOLOGY_SPECIALIST").id, organization_id=None))
    db.flush()
    both = Actor(both.user, login(client, both.user))
    ev = _evaluate(client, both, p["id"], {"additionality_assessment": "COMPLETED"}).json()
    alm = _candidate(ev, "TALM")
    client.post(f"{PR}/{p['id']}/methodology/reviews", headers=both.headers,
                json={"evaluation_result_id": alm["id"], "recommendation": "RECOMMENDED", "notes": "fits", "evidence_acknowledged": True})
    r = client.post(f"{PR}/{p['id']}/methodology/confirm", headers=both.headers, json={"evaluation_result_id": alm["id"], "notes": "mine"})
    assert r.status_code == 403 and r.json()["error_code"] == "SEPARATION_OF_DUTIES"


def test_version_selection_effective_dates_and_crediting_rules(client: TestClient, db: Session, t: Team, setup: dict) -> None:
    author, approver = setup["author"], setup["approver"]
    mid = setup["alm"]["id"]
    # 2.0 is approved and effective; 0.9 expired before the project start; both 1.0 and 2.0 are candidates.
    v2 = approved_version(client, author, approver, mid, "2.0", ALM_RULES, based_on_version_id=setup["alm_v1"]["id"])
    approved_version(client, author, approver, mid, "0.9", ALM_RULES, effective_from="2015-01-01", effective_to="2019-12-31")
    rule = {"rule_code": "CP1", "title": "Crediting period length (TEST value)", "rule_type": "CREDITING_PERIOD",
            "parameters": {"min_years": 20}}
    v3 = client.post(f"{M}/{mid}/versions", headers=author.headers,
                     json={"version_label": "3.0", "effective_from": "2020-01-01", "source_name": "TEST", "based_on_version_id": v2["id"]}).json()
    client.post(f"{M}/versions/{v3['id']}/rules/general", headers=author.headers, json=rule)
    client.post(f"{M}/versions/{v3['id']}/submit", headers=author.headers, json={"reason": "ready for approval"})
    client.post(f"{M}/versions/{v3['id']}/approve", headers=approver.headers, json={"reason": "checked"})
    p = project_at_activity_selected(client, t, setup["cat"], 76.60, 23.60, "7600 2000 3000")
    ev = _evaluate(client, t.pm, p["id"], {"additionality_assessment": "COMPLETED"}).json()
    labels = sorted(c["version_label"] for c in ev["candidates"] if c["methodology_code"].startswith("TALM"))
    assert labels == ["1.0", "2.0", "3.0"]  # expired 0.9 excluded
    by_label = {c["version_label"]: c for c in ev["candidates"] if c["methodology_code"].startswith("TALM")}
    for label in ("2.0", "3.0"):
        client.post(f"{PR}/{p['id']}/methodology/reviews", headers=author.headers,
                    json={"evaluation_result_id": by_label[label]["id"], "recommendation": "RECOMMENDED", "notes": "fits", "evidence_acknowledged": True})
    # 3.0 configures a 20-year minimum crediting period; the project's proposed period is 10 years → blocked.
    r = client.post(f"{PR}/{p['id']}/methodology/confirm", headers=t.pm.headers, json={"evaluation_result_id": by_label["3.0"]["id"], "notes": "x x"})
    assert r.status_code == 409 and r.json()["error_code"] == "CREDITING_PERIOD_NOT_COMPLIANT"
    r = client.post(f"{PR}/{p['id']}/methodology/confirm", headers=t.pm.headers, json={"evaluation_result_id": by_label["2.0"]["id"],
                                                                                       "notes": "Version 2.0 selected"})
    assert r.json()["current"]["version_label"] == "2.0" and r.json()["current"]["rules_version"] == 1


def test_reopen_from_methodology_review_resets_selection(client: TestClient, db: Session, t: Team, setup: dict) -> None:
    p = project_at_activity_selected(client, t, setup["cat"], 76.70, 23.70, "7700 2000 3000")
    _evaluate(client, t.pm, p["id"])
    r = client.post(f"{PR}/{p['id']}/reopen", headers=t.pm.headers, json={"reason": "add another farm"})
    assert r.json()["status"] == "DATA_COLLECTION" and r.json()["methodology_status"] == "NOT_SELECTED"
    assert len(client.get(f"{PR}/{p['id']}/methodology/evaluations", headers=t.pm.headers).json()) == 1  # history kept
