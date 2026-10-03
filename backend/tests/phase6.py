"""Helpers for Phase 6 (laboratory) tests: a Phase 5 project with an ACCEPTED field collection, a laboratory organization with
its staff, and an ACTIVE engagement. Rules and values here are TEST fixtures, not real methodology requirements."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Organization
from tests.conftest import Actor, make_org
from tests.phase2 import staff
from tests.phase5 import MRV, MrvCtx, approved_design, approved_plan, approved_stratum, collect, collecting_period, locked_project

UTC = timezone.utc
LAB = "/api/v1/lab"
LABV = "/api/v1/laboratory"
PDF = b"%PDF-1.4\n% TEST laboratory report\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
SOC_RULE = {"rule_code": "SOC", "title": "Soil organic carbon", "parameter": "Soil organic carbon stock", "unit": "t C/ha",
            "measurement_source": "LABORATORY"}
TEXT_RULE = {"rule_code": "TEX", "title": "Texture class", "parameter": "Soil texture class", "unit": None, "measurement_source": "LABORATORY"}
FIELD_RULE = {"rule_code": "PHT", "title": "Plant height", "parameter": "Plant height", "unit": "cm", "measurement_source": "FIELD"}


@dataclass
class LabCtx:
    c: MrvCtx
    lab_org: Organization
    tech: Actor
    mgr: Actor          # accepts engagements; may request retests
    qa: Actor           # second, independent lab manager (approves)
    period: dict
    points: list[dict]
    fcs: list[dict]     # ACCEPTED field collections (one per point), collected by c.collector
    engagement: dict
    rules: dict[str, dict]


def now_iso(delta_min: int = 0) -> str:
    return (datetime.now(UTC) + timedelta(minutes=delta_min)).isoformat()


def lab_project(db: Session, client: TestClient, lon: float, lat: float, id_number: str, rules: list[dict[str, Any]] | None = None,
                n_points: int = 2, engage: list[str] | None = None, calculation_rules: list[dict[str, Any]] | None = None) -> LabCtx:
    c = locked_project(db, client, lon, lat, id_number, monitoring_rules=rules or [SOC_RULE], calculation_rules=calculation_rules)
    approved_plan(client, c)
    mp = collecting_period(client, c, start=(datetime.now(UTC) - timedelta(days=60)).date().isoformat(),
                           end=(datetime.now(UTC) + timedelta(days=300)).date().isoformat())
    st = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    d = approved_design(client, c, mp["id"], [{"stratum_id": st["id"], "sample_count": n_points}])
    pts = client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers).json()["points"]
    client.post(f"{MRV}/sampling-points/assign", headers=c.supervisor.headers,
                json={"point_ids": [p["id"] for p in pts], "collector_id": str(c.collector.user.id)})
    fcs = [collect(client, c, p, c.collector, when=now_iso(-30)) for p in pts]
    lab_org = make_org(db, org_type="LABORATORY")
    tech, mgr, qa = staff(db, client, lab_org, "LAB_TECHNICIAN"), staff(db, client, lab_org, "LAB_MANAGER"), staff(db, client, lab_org, "LAB_MANAGER")
    lab_rules = {r["rule_code"]: r for r in client.get(f"{LAB}/projects/{c.project['id']}/laboratory-rules", headers=c.mrv.headers).json()}
    scope = [lab_rules[k]["rule_id"] for k in (engage or list(lab_rules))]
    e = client.post(f"{LAB}/engagements", headers=c.mrv.headers, json={"project_id": c.project["id"], "laboratory_org_id": str(lab_org.id),
                                                                       "rule_ids": scope}).json()
    r = client.post(f"{LABV}/engagements/{e['id']}/accept", headers=mgr.headers)
    assert r.status_code == 200, r.text
    return LabCtx(c, lab_org, tech, mgr, qa, mp, pts, fcs, e, lab_rules)


def register(client: TestClient, x: LabCtx, fc: dict, actor: Actor | None = None, **kw: Any) -> dict:
    r = client.post(f"{LAB}/samples", headers=(actor or x.c.collector).headers,
                    json={"field_collection_id": fc["id"], "description": "Composite soil sample", "quantity": "0.5", "quantity_unit": "kg", **kw})
    assert r.status_code == 201, r.text
    return r.json()


def seal(client: TestClient, x: LabCtx, s: dict, actor: Actor | None = None, seal_no: str = "SEAL-1") -> dict:
    r = client.post(f"{LAB}/samples/{s['id']}/seal", headers=(actor or x.c.collector).headers, json={"seal_number": seal_no})
    assert r.status_code == 200, r.text
    return r.json()


def ship(client: TestClient, x: LabCtx, samples: list[dict]) -> dict:
    sh = client.post(f"{LAB}/shipments", headers=x.c.supervisor.headers,
                     json={"project_id": x.c.project["id"], "laboratory_org_id": str(x.lab_org.id), "carrier": "Courier"}).json()
    r = client.post(f"{LAB}/shipments/{sh['id']}/items", headers=x.c.supervisor.headers, json={"sample_ids": [s["id"] for s in samples]})
    assert r.status_code == 200, r.text
    r = client.post(f"{LAB}/shipments/{sh['id']}/dispatch", headers=x.c.supervisor.headers, json={})
    assert r.status_code == 200, r.text
    return r.json()


def receive(client: TestClient, x: LabCtx, sh: dict, samples: list[dict], seal_no: str = "SEAL-1") -> dict:
    r = client.post(f"{LABV}/shipments/{sh['id']}/receive", headers=x.tech.headers, json={"items": [
        {"sample_id": s["id"], "accepted": True, "condition": "intact", "seal_number_observed": seal_no} for s in samples]})
    assert r.status_code == 200, r.text
    for i, s in enumerate(samples):
        r = client.post(f"{LABV}/samples/{s['id']}/accession", headers=x.tech.headers, json={"accession_number": f"ACC-{i + 1}"})
        assert r.status_code == 200, r.text
    return r.json()


def to_lab(client: TestClient, x: LabCtx, fc_index: int = 0) -> dict:
    """Register (collector) → seal → ship (supervisor) → receive + accession (technician). Returns the lab view of the sample."""
    s = register(client, x, x.fcs[fc_index])
    seal(client, x, s)
    sh = ship(client, x, [s])
    receive(client, x, sh, [s])
    return client.get(f"{LABV}/samples/{s['id']}", headers=x.tech.headers).json()


def enter_result(client: TestClient, x: LabCtx, test_id: str, value: Any = "1.234", unit: str | None = "t C/ha", result_type: str = "NUMERIC",
                 report: bool = True, start: bool = True, actor: Actor | None = None) -> dict:
    a = actor or x.tech
    if start:
        r = client.post(f"{LABV}/tests/{test_id}/start", headers=a.headers, json={"method_reported": "Lab SOP 12 (TEST)"})
        assert r.status_code == 200, r.text
    body = {"result_type": result_type, "unit": unit, "analysed_at": now_iso(1)}
    body["value_number" if result_type == "NUMERIC" else "value_text"] = value
    r = client.post(f"{LABV}/tests/{test_id}/results", headers=a.headers, json=body)
    assert r.status_code == 201, r.text
    res = r.json()
    if report:
        r = client.post(f"{LABV}/results/{res['id']}/report", headers=a.headers, files={"file": ("report.pdf", PDF, "application/pdf")})
        assert r.status_code == 200, r.text
    r = client.post(f"{LABV}/results/{res['id']}/submit", headers=a.headers)
    assert r.status_code == 200, r.text
    return r.json()


def qa(client: TestClient, x: LabCtx, result_id: str, decision: str = "APPROVED", actor: Actor | None = None, ack: bool = False) -> Any:
    a = actor or x.qa
    r = client.post(f"{LABV}/qa/{result_id}/start", headers=a.headers)
    if r.status_code != 200:
        return r
    return client.post(f"{LABV}/qa/{result_id}/decision", headers=a.headers,
                       json={"decision": decision, "notes": f"QA {decision.lower()}", "acknowledge_configuration": ack})

