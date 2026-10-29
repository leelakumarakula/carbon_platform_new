"""FarmFuture boundary import: response parsing, the token flow, the read-only API, phone rules, RBAC and audit.
No test reaches the internet: the HTTP transport is replaced by a fake that answers like api.farmfuture.io."""
import base64
import json
import time
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations import farmfuture as ff
from app.integrations.geodata import ProviderUnavailable
from app.models import AuditLog, FarmBoundary
from app.services import farmfuture_service as svc
from tests.conftest import login, make_org, make_user
from tests.phase2 import create_farm, dev_org, kyc_verified_farmer, staff

FA = "/api/v1/farms"
FF_FARM = "0c1e6f77-9b1d-441e-bda5-6531d8724f48"
FF_SINGLE = "8c953438-0324-4415-82fa-dc450d339e60"
ZONE_A = "POLYGON ((76.0572 12.0011, 76.0552 12.0010, 76.0551 12.0002, 76.0525 12.0021, 76.0545 12.0016, 76.0565 12.0028, 76.0572 12.0011))"
ZONE_B = "POLYGON ((76.0583 12.0012, 76.0572 12.0011, 76.0565 12.0028, 76.0571 12.0032, 76.0582 12.0018, 76.0583 12.0012))"


def _jwt(exp: float) -> str:
    def b64(d: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{b64({'alg': 'HS256'})}.{b64({'MobileNumber': '+919876543210', 'exp': exp})}.sig"


ESTATES = {"succeeded": True, "data": [
    {"estateId": "ff798ea2-a0ac-4e6d-ab53-41c47485ef42", "estateName": "Palthope estate", "zipCode": "571250", "isFpo": False, "farms": [
        {"farmId": FF_FARM, "farmName": "Palthope estate", "postalCode": "571250", "isOwnerEstate": True, "plantsPerHectare": 4000,
         "crops": [{"id": "1", "name": "Coffee-Robusta"}, {"id": "2", "name": "Coffee-Arabica"}], "isActiveSubscription": True},
        {"farmId": FF_SINGLE, "farmName": "Bicode ", "postalCode": "573215", "isOwnerEstate": False, "plantsPerHectare": 0, "crops": []}]}]}
AREAS = {"succeeded": True, "data": {
    "farmCoordinates": [
        {"area": {"id": "z2", "areaName": "Zone-2", "mainMapType": False, "polygon": ZONE_A},
         "coordinates": [{"lat": 12.0011, "long": 76.0572, "alt": 916.3, "number": 0}, {"lat": 12.0010, "long": 76.0552, "alt": 890.1, "number": 1}]},
        {"area": {"id": "z1", "areaName": "Zone-1", "mainMapType": False, "polygon": ZONE_B}, "coordinates": []}],
    "deviceCoordinates": [{"deviceName": "Soilsync Hub", "lat": 12.001157, "long": 76.056699, "deviceType": 4}, {"deviceName": "no position"}]}}


class FakeFarmFuture:
    """Answers like api.farmfuture.io; records every call."""

    def __init__(self, phones: tuple[str, ...] = ("+919876543210",)) -> None:
        self.phones, self.expired = phones, False
        self.calls: list[dict[str, Any]] = []

    def __call__(self, url: str, *, method: str = "GET", payload: dict[str, Any] | None = None, token: str | None = None,
                 timeout: int) -> ff._Response:
        self.calls.append({"url": url, "method": method, "payload": payload, "token": token})
        if url.endswith("/controller/ValidateMobileNumber"):
            ok = payload and payload["phoneNumber"] in self.phones
            data: dict[str, Any] = {"message": "User Already Exist.", "token": _jwt(time.time() + 7 * 86400)} if ok else {"message": "Invalid", "token": None}
            return ff._Response(200, json.dumps({"succeeded": True, "data": data}).encode())
        if not token or self.expired:
            self.expired = False
            return ff._Response(401, b"")
        if url.endswith("/Estate/GetUserEstatesAndFarmsList"):
            return ff._Response(200, json.dumps(ESTATES).encode())
        if url.endswith(f"/Data/GetFarmCoordinates/{FF_FARM}"):
            return ff._Response(200, json.dumps(AREAS).encode())
        return ff._Response(200, json.dumps({"succeeded": True, "data": {"farmCoordinates": [], "deviceCoordinates": []}}).encode())

    def logins(self) -> int:
        return sum(1 for c in self.calls if c["url"].endswith("ValidateMobileNumber"))


@pytest.fixture()
def fake(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeFarmFuture]:
    f = FakeFarmFuture()
    monkeypatch.setattr(ff, "_request", f)
    monkeypatch.setattr(svc, "_client", lambda: ff.FarmFutureClient("https://farmfuture.test/api", 5))
    ff.FarmFutureClient.forget_tokens()
    yield f
    ff.FarmFutureClient.forget_tokens()


# ---------------------------------------------------------------- parsing and the client
def test_estates_and_areas_are_normalised() -> None:
    estates = ff.parse_estates(ESTATES["data"])
    assert estates[0]["name"] == "Palthope estate" and estates[0]["postal_code"] == "571250"
    assert estates[0]["farms"][0] == {"farm_id": FF_FARM, "name": "Palthope estate", "postal_code": "571250",
                                      "crops": ["Coffee-Robusta", "Coffee-Arabica"], "plants_per_hectare": 4000.0, "is_owner_estate": True,
                                      "active_subscription": True}
    assert estates[0]["farms"][1]["name"] == "Bicode" and estates[0]["farms"][1]["active_subscription"] is False
    areas = ff.parse_coordinates(AREAS["data"])
    z = areas["zones"][0]
    assert (z["name"], z["is_main"], z["vertex_count"], z["mean_altitude_m"]) == ("Zone-2", False, 6, 903.2)
    assert z["geojson"]["type"] == "Polygon" and z["geojson"]["coordinates"][0][0] == [76.0572, 12.0011]
    assert areas["zones"][1]["mean_altitude_m"] is None
    assert areas["devices"] == [{"name": "Soilsync Hub", "lat": 12.001157, "lon": 76.056699, "device_type": 4.0}]   # no position: dropped


def test_zone_without_wkt_falls_back_to_its_numbered_corners() -> None:
    pts = [{"lat": 12.0, "long": 76.0, "number": 2}, {"lat": 12.0, "long": 76.001, "number": 0}, {"lat": 12.001, "long": 76.001, "number": 1}]
    z = ff.parse_coordinates({"farmCoordinates": [{"area": {"id": "x", "areaName": "", "polygon": None}, "coordinates": pts}]})["zones"][0]
    assert z["name"] == "Unnamed area" and z["geojson"]["coordinates"][0] == [[76.001, 12.0], [76.001, 12.001], [76.0, 12.0], [76.001, 12.0]]
    assert ff.parse_coordinates({"farmCoordinates": [{"area": {"polygon": ""}, "coordinates": pts[:2]}]})["zones"] == []
    assert ff.parse_coordinates(None) == {"zones": [], "devices": []}


def test_unsuccessful_or_non_json_answers_are_provider_errors() -> None:
    with pytest.raises(ProviderUnavailable):
        ff._data(b"<html>")
    with pytest.raises(ProviderUnavailable):
        ff._data(b'{"succeeded": false, "data": null}')
    with pytest.raises(ProviderUnavailable):
        ff._request("http://plain.example", timeout=1)                                        # HTTPS only
    with pytest.raises(ff.FarmFutureUserNotFound):
        ff.parse_token({"message": "Invalid", "token": None})


def test_token_is_cached_per_phone_and_renewed_once_on_401(fake: FakeFarmFuture) -> None:
    c = ff.FarmFutureClient("https://farmfuture.test/api", 5)
    c.estates("+919876543210")
    c.farm_coordinates("+919876543210", FF_FARM)
    assert fake.logins() == 1                                                                   # one token for both calls
    assert fake.calls[0]["payload"] == {"phoneNumber": "+919876543210"} and fake.calls[1]["token"]
    fake.expired = True                                                                         # FarmFuture revokes the token
    c.estates("+919876543210")
    assert fake.logins() == 2
    assert ff.token_expiry(_jwt(1234.0)) == 1234.0 and ff.token_expiry("not-a-jwt") == 0.0


@pytest.mark.parametrize(("raw", "phone"), [("+91 77996 61222", "+917799661222"), ("7799661222", "+917799661222"),
                                            ("07799661222", "+917799661222"), ("0044 20 7946 0958", "+442079460958"),
                                            ("(+91) 77996-61222", "+917799661222")])
def test_phone_numbers_are_normalised_to_e164(raw: str, phone: str) -> None:
    assert svc.normalise_phone(raw, "+91") == phone
    assert svc.mask(phone).startswith(phone[:3]) and svc.mask(phone).endswith(phone[-3:]) and "*" in svc.mask(phone)


def test_unusable_phone_numbers_are_refused() -> None:
    from app.core.errors import ValidationFailed
    for raw in ("12345", "+0123456789", "abc"):
        with pytest.raises(ValidationFailed):
            svc.normalise_phone(raw, "+91")


# ---------------------------------------------------------------- the API
@pytest.fixture()
def world(db: Session, client: TestClient) -> dict[str, Any]:
    org = dev_org(db)
    agent, qa = staff(db, client, org, "FIELD_AGENT"), staff(db, client, org, "QA_OFFICER")
    farmer = kyc_verified_farmer(client, agent, qa, org)                                       # primary phone +91 98765 43210
    farm = create_farm(client, agent.headers, farmer["id"])
    return {"org": org, "agent": agent, "qa": qa, "farmer": farmer, "farm": farm}


def test_lookup_uses_the_farmers_phone_and_is_read_only_and_audited(client: TestClient, db: Session, world: dict[str, Any],
                                                                     fake: FakeFarmFuture) -> None:
    fid, h = world["farm"]["id"], world["agent"].headers
    r = client.post(f"{FA}/{fid}/farmfuture/estates", headers=h, json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["phone_source"] == "FARMER_PRIMARY_PHONE" and body["phone_masked"] == "+91*******210"
    assert [f["name"] for f in body["estates"][0]["farms"]] == ["Palthope estate", "Bicode"]
    a = client.post(f"{FA}/{fid}/farmfuture/farms/{FF_FARM}/areas", headers=h, json={}).json()
    assert [z["name"] for z in a["zones"]] == ["Zone-2", "Zone-1"] and len(a["devices"]) == 1
    assert a["combined_geojson"]["type"] == "Polygon"                                          # two adjacent zones dissolved by SQL Server
    # a candidate becomes a boundary only through the normal flow
    saved = client.post(f"{FA}/{fid}/boundary", headers=h, json={"geojson": a["combined_geojson"], "source": "IMPORT"})
    assert saved.status_code == 200, saved.text
    b = db.scalars(select(FarmBoundary).where(FarmBoundary.farm_id == uuid.UUID(fid))).one()
    assert b.source == "IMPORT" and saved.json()["farm"]["status"] == "DRAFT"
    audit = db.scalars(select(AuditLog).where(AuditLog.entity_id == fid, AuditLog.action.like("FARMFUTURE_%"))).all()
    assert sorted(x.action for x in audit) == ["FARMFUTURE_AREAS_FETCHED", "FARMFUTURE_LOOKUP"]
    assert all("9876543210" not in (x.new_value or "") for x in audit)                        # only the masked number is logged
    assert all("token" not in json.dumps(c["payload"] or {}) for c in fake.calls)


def test_farm_without_mapped_areas(client: TestClient, world: dict[str, Any], fake: FakeFarmFuture) -> None:
    fid, h = world["farm"]["id"], world["agent"].headers
    a = client.post(f"{FA}/{fid}/farmfuture/farms/{FF_SINGLE}/areas", headers=h, json={"phone_number": "9876543210"}).json()
    assert a["zones"] == [] and a["combined_geojson"] is None and a["devices"] == []


def test_unknown_numbers_unlisted_farms_and_switched_off(client: TestClient, world: dict[str, Any], fake: FakeFarmFuture,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    fid, h = world["farm"]["id"], world["agent"].headers
    # staff cannot look up a stranger's number: FarmFuture would return someone else's estates and boundaries
    calls = len(fake.calls)
    r = client.post(f"{FA}/{fid}/farmfuture/estates", headers=h, json={"phone_number": "+91 90000 00000"})
    assert r.status_code == 403 and r.json()["error_code"] == "PHONE_NOT_OWN" and len(fake.calls) == calls
    # once recorded as the farmer's contact (audited), the number is looked up; FarmFuture does not know it
    c = client.post(f"/api/v1/farmers/{world['farmer']['id']}/contacts", headers=h,
                    json={"contact_type": "ALTERNATE_PHONE", "value": "+91 90000 00000"})
    assert c.status_code == 201, c.text
    r = client.post(f"{FA}/{fid}/farmfuture/estates", headers=h, json={"phone_number": "+91 90000 00000"})
    assert r.status_code == 404 and r.json()["error_code"] == "FARMFUTURE_USER_NOT_FOUND"
    r = client.post(f"{FA}/{fid}/farmfuture/estates", headers=h, json={"phone_number": "12345"})
    assert r.status_code == 422
    other = str(uuid.uuid4())                                                                   # not one of this number's farms
    r = client.post(f"{FA}/{fid}/farmfuture/farms/{other}/areas", headers=h, json={})
    assert r.status_code == 404 and r.json()["error_code"] == "FARMFUTURE_FARM_NOT_FOUND"
    assert not any(c["url"].endswith(other) for c in fake.calls)
    monkeypatch.setattr(svc, "_client", lambda: None)
    r = client.post(f"{FA}/{fid}/farmfuture/estates", headers=h, json={})
    assert r.status_code == 409 and r.json()["error_code"] == "PROVIDER_NOT_CONFIGURED"


def test_outage_is_a_503(client: TestClient, world: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    def down(url: str, **_: Any) -> ff._Response:
        raise ProviderUnavailable("FarmFuture could not be reached (URLError)")
    monkeypatch.setattr(ff, "_request", down)
    monkeypatch.setattr(svc, "_client", lambda: ff.FarmFutureClient("https://farmfuture.test/api", 5))
    ff.FarmFutureClient.forget_tokens()
    r = client.post(f"{FA}/{world['farm']['id']}/farmfuture/estates", headers=world["agent"].headers, json={})
    assert r.status_code == 503 and r.json()["error_code"] == "EXTERNAL_PROVIDER_UNAVAILABLE"


def test_permissions_and_farmer_self_service_phone_rule(client: TestClient, db: Session, world: dict[str, Any],
                                                        fake: FakeFarmFuture) -> None:
    fid = world["farm"]["id"]
    assert client.post(f"{FA}/{fid}/farmfuture/estates", headers=world["qa"].headers, json={}).status_code in (403, 404)
    outsider = staff(db, client, dev_org(db), "FIELD_AGENT")
    assert client.post(f"{FA}/{fid}/farmfuture/estates", headers=outsider.headers, json={}).status_code == 404
    # the farm's own farmer: only their registered numbers
    user = make_user(db, roles=[("FARMER", make_org(db, org_type="FARMER_GROUP"))])
    pm = staff(db, client, world["org"], "PROJECT_MANAGER")
    client.post(f"/api/v1/farmers/{world['farmer']['id']}/link-user", headers=pm.headers, json={"user_id": str(user.id)})
    h = login(client, user)
    assert client.post(f"{FA}/{fid}/farmfuture/estates", headers=h, json={}).status_code == 200
    assert client.post(f"{FA}/{fid}/farmfuture/estates", headers=h, json={"phone_number": "98765 43210"}).status_code == 200
    r = client.post(f"{FA}/{fid}/farmfuture/estates", headers=h, json={"phone_number": "+91 77996 61222"})
    assert r.status_code == 403 and r.json()["error_code"] == "PHONE_NOT_OWN"
