"""The dataset snapshot carries every current approved stratum of the project (once per stratum record), not only the strata that hold
sampling points: methods without sampling (default factors recorded per stratum, e.g. GS 402 Approach 3) need the stratum and its area
(regression: their calculation was blocked with "No eligible input for AREA")."""
import json
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import MrvDataset
from tests.phase5 import MRV, approved_plan, approved_stratum, collecting_period, locked_project


def test_snapshot_includes_strata_without_sampling_points(client: TestClient, db: Session) -> None:
    c = locked_project(db, client, 78.45, 23.45, "8460 2000 3000", n_farms=2, monitoring=False)
    plan = approved_plan(client, c)
    mp = collecting_period(client, c)
    till = next(m for m in plan["measurements"] if m["code"] == "TILL")
    rec = client.post(f"{MRV}/monitoring-records", headers=c.collector.headers, json={
        "monitoring_period_id": mp["id"], "measurement_id": till["id"], "farm_id": c.farms[0]["id"], "value": "REDUCED", "observed_on": mp["start_date"]})
    assert rec.status_code == 201, rec.text
    s1 = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    s2 = approved_stratum(client, c, "S2", [c.farms[1]["id"]])
    r = client.post(f"{MRV}/datasets", headers=c.mrv.headers, json={"monitoring_period_id": mp["id"]})
    assert r.status_code == 201, r.text
    sub = client.post(f"{MRV}/datasets/{r.json()['id']}/submit", headers=c.mrv.headers, json={"reason": "collection complete"})
    assert sub.status_code == 200, sub.text
    ds = db.get(MrvDataset, uuid.UUID(r.json()["id"]))
    assert ds is not None
    db.refresh(ds)
    assert ds.snapshot
    strata = json.loads(ds.snapshot)["strata"]
    assert sorted(s["code"] for s in strata) == ["S1", "S2"]
    assert {s["id"] for s in strata} == {s1["id"], s2["id"]} and len({s["record_id"] for s in strata}) == 2
