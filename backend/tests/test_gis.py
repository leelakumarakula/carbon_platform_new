"""GIS: parsing, SQL Server validity/area (STArea), orientation, holes, KML safety, spatial search (STDistance, STIntersects)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailed
from app.rules.geometry_io import GeometryError, parse_geojson, parse_kml, wkt_to_geojson
from app.services import gis_service
from tests.conftest import Actor
from tests.phase2 import square

KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>
73.8,20.0,0 73.801,20.0,0 73.801,20.001,0 73.8,20.001,0 73.8,20.0,0
</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></kml>"""


def check(db: Session, geo: object = None, kml: str | None = None) -> gis_service.BoundaryCheck:
    return gis_service.check_boundary(db, gis_service.parse_input(geo, kml))


def test_area_is_computed_by_sql_server(db: Session) -> None:
    c = check(db, square())
    # 0.001° × 0.001° at 20°N ≈ 111.1 m × 104.5 m ≈ 1.16 ha (SQL Server geodesic STArea)
    assert 1.15 < c.area_hectares < 1.17
    assert c.perimeter_m == pytest.approx(431, abs=3) and c.vertex_count == 5
    assert c.centroid_lat == pytest.approx(20.0005, abs=1e-4)


def test_clockwise_and_unclosed_ring_are_normalised(db: Session) -> None:
    ccw = check(db, square())
    cw = check(db, {"type": "Polygon", "coordinates": [[[73.8, 20.0], [73.8, 20.001], [73.801, 20.001], [73.801, 20.0]]]})
    assert cw.area_hectares == pytest.approx(ccw.area_hectares, rel=1e-6)
    assert any("not closed" in n for n in cw.notes) and any("orientation" in n for n in cw.notes)


def test_self_intersecting_polygon_rejected_with_reason(db: Session) -> None:
    bowtie = {"type": "Polygon", "coordinates": [[[73.8, 20.0], [73.801, 20.001], [73.801, 20.0], [73.8, 20.001], [73.8, 20.0]]]}
    with pytest.raises(ValidationFailed) as e:
        check(db, bowtie)
    assert e.value.error_code == "INVALID_POLYGON" and "intersects itself" in e.value.message


@pytest.mark.parametrize("geo,code", [
    ({"type": "Polygon", "coordinates": [[[20.0, 173.8], [20.1, 173.8], [20.1, 173.9], [20.0, 173.8]]]}, "COORDINATE_OUT_OF_RANGE"),
    ({"type": "Polygon", "coordinates": [[[73.8, 20.0], [73.801, 20.0], [73.8, 20.0]]]}, "TOO_FEW_POINTS"),
    ({"type": "Point", "coordinates": [73.8, 20.0]}, "UNSUPPORTED_GEOMETRY"),
    ({"type": "FeatureCollection", "features": []}, "INVALID_GEOJSON"),
    ({"type": "Polygon", "coordinates": [[["a", "b"], [1, 2], [2, 2], [1, 1]]]}, "INVALID_GEOMETRY"),
])
def test_structural_rejections(db: Session, geo: object, code: str) -> None:
    with pytest.raises(ValidationFailed) as e:
        check(db, geo)
    assert e.value.error_code == code


def test_hole_reduces_area_and_multipolygon_adds(db: Session) -> None:
    outer = square()["coordinates"][0]
    hole = [[73.8004, 20.0004], [73.8004, 20.0006], [73.8006, 20.0006], [73.8006, 20.0004], [73.8004, 20.0004]]
    with_hole = check(db, {"type": "Polygon", "coordinates": [outer, hole]})
    plain = check(db, square())
    assert with_hole.area_hectares < plain.area_hectares
    multi = check(db, {"type": "MultiPolygon", "coordinates": [square()["coordinates"], square(73.81)["coordinates"]]})
    assert multi.area_hectares == pytest.approx(2 * plain.area_hectares, rel=1e-3)
    assert multi.geojson["type"] == "MultiPolygon" and len(multi.geojson["coordinates"]) == 2


def test_feature_wrappers_and_vertex_limit() -> None:
    assert parse_geojson({"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": square()}]}).vertex_count == 5
    big = {"type": "Polygon", "coordinates": [[[73.8 + i * 1e-6, 20.0 + (i % 2) * 1e-6] for i in range(60)] + [[73.8, 20.0]]]}
    with pytest.raises(GeometryError) as e:
        parse_geojson(big, max_vertices=50)
    assert e.value.code == "TOO_MANY_VERTICES"


def test_kml_parsed_and_unsafe_kml_rejected(db: Session) -> None:
    assert check(db, kml=KML).area_hectares == pytest.approx(check(db, square()).area_hectares, rel=1e-6)
    with pytest.raises(GeometryError) as e:
        parse_kml('<?xml version="1.0"?><!DOCTYPE kml [<!ENTITY x "y">]><kml>&x;</kml>')
    assert e.value.code == "UNSAFE_KML"
    with pytest.raises(GeometryError):
        parse_kml("<kml><Polygon><outerBoundaryIs><coordinates>abc def</coordinates></outerBoundaryIs></Polygon></kml>")


def test_wkt_round_trip() -> None:
    gj = wkt_to_geojson("POLYGON ((73.8 20, 73.801 20, 73.801 20.001, 73.8 20))")
    assert gj == {"type": "Polygon", "coordinates": [[[73.8, 20.0], [73.801, 20.0], [73.801, 20.001], [73.8, 20.0]]]}


def test_validate_endpoint(client: TestClient, db: Session) -> None:
    from tests.phase2 import dev_org, staff
    org = dev_org(db)
    agent = staff(db, client, org, "FIELD_AGENT")
    r = client.post("/api/v1/farms/geometry/validate", headers=agent.headers, json={"geojson": square()})
    assert r.status_code == 200 and 1.15 < r.json()["area_hectares"] < 1.17
    bad = client.post("/api/v1/farms/geometry/validate", headers=agent.headers, json={"geojson": square(), "kml": KML})
    assert bad.status_code == 422


def test_large_and_mismatched_area_warnings(db: Session) -> None:
    from decimal import Decimal
    c = gis_service.check_boundary(db, gis_service.parse_input(square()), declared_area_ha=Decimal("3.0"))
    assert any("differs from the declared" in w for w in c.warnings)
    huge = check(db, square(size=0.5))
    assert any("unusually large" in w for w in huge.warnings)


def test_spatial_search_near_and_at_point(client: TestClient, db: Session, admin: Actor) -> None:
    from tests.phase2 import add_owner, create_farm, create_farmer, dev_org, register, set_boundary, staff
    org = dev_org(db)
    agent = staff(db, client, org, "FIELD_AGENT")
    farmer = create_farmer(client, agent.headers, org)
    register(client, agent.headers, farmer["id"])
    farm = create_farm(client, agent.headers, farmer["id"])
    set_boundary(client, agent.headers, farm["id"], square(80.0, 15.0))
    add_owner(client, agent.headers, farm["id"])
    inside = client.get("/api/v1/farms/spatial/at-point", headers=agent.headers, params={"lat": 15.0005, "lon": 80.0005}).json()
    assert [f["id"] for f in inside] == [farm["id"]]
    assert client.get("/api/v1/farms/spatial/at-point", headers=agent.headers, params={"lat": 15.01, "lon": 80.01}).json() == []
    near = client.get("/api/v1/farms/spatial/near", headers=agent.headers, params={"lat": 15.0, "lon": 80.0 - 0.002, "radius_m": 500}).json()
    assert near and near[0]["farm_id"] == farm["id"] and 150 < float(near[0]["distance_m"]) < 260
    # another organization's staff do not see it
    other = staff(db, client, dev_org(db), "FIELD_AGENT")
    assert client.get("/api/v1/farms/spatial/at-point", headers=other.headers, params={"lat": 15.0005, "lon": 80.0005}).json() == []
