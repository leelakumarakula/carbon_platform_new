"""SQL Server spatial operations. SQL Server is the authoritative calculator for validity, area and overlap.

Uses: geometry::IsValidDetailed (self-intersection), geography STArea / STLength / EnvelopeAngle /
ReorientObject, STIntersects, STIntersection, STContains, STDistance, plus the spatial index on
farm_boundaries.boundary.
"""
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class GeometryReport:
    valid: bool
    reason: str | None
    wkt: str | None = None            # normalised (correct ring orientation) WKT to store
    area_m2: float = 0.0
    perimeter_m: float = 0.0
    centroid_lat: float = 0.0
    centroid_lon: float = 0.0
    reoriented: bool = False


_VALIDATE = text("""
SET NOCOUNT ON;
DECLARE @wkt nvarchar(max) = :wkt;
DECLARE @planar geometry = geometry::STGeomFromText(@wkt, 4326);
IF @planar.STIsValid() = 0
BEGIN
    SELECT CAST(0 AS bit) AS valid, @planar.IsValidDetailed() AS reason, NULL AS wkt, 0.0 AS area_m2, 0.0 AS perimeter_m,
           0.0 AS lat, 0.0 AS lon, CAST(0 AS bit) AS reoriented;
    RETURN;
END
DECLARE @g geography = geography::STGeomFromText(@wkt, 4326);
DECLARE @re bit = 0;
-- A ring drawn in the "wrong" direction describes the whole globe minus the farm; flip it.
IF @g.EnvelopeAngle() > 90 BEGIN SET @g = @g.ReorientObject(); SET @re = 1; END
IF @g.STIsValid() = 0
BEGIN
    SELECT CAST(0 AS bit), @g.IsValidDetailed(), NULL, 0.0, 0.0, 0.0, 0.0, @re;
    RETURN;
END
DECLARE @c geography = @g.EnvelopeCenter();
SELECT CAST(1 AS bit), NULL, @g.STAsText(), @g.STArea(), @g.STLength(), @c.Lat, @c.Long, @re;
""")


def validate_geometry(db: Session, wkt: str) -> GeometryReport:
    try:
        row = db.execute(_VALIDATE, {"wkt": wkt}).one()
    except DBAPIError as e:  # e.g. unclosed ring, malformed WKT, crosses a hemisphere boundary
        msg = str(getattr(e, "orig", e)).split("\n")[0]
        return GeometryReport(False, _clean(msg))
    valid, reason, norm, area, perim, lat, lon, re = row
    return GeometryReport(bool(valid), reason, norm, float(area or 0), float(perim or 0), float(lat or 0), float(lon or 0), bool(re))


_UNION = text("""
SET NOCOUNT ON;
SELECT geometry::UnionAggregate(geometry::STGeomFromText(j.value, 4326).MakeValid()).STAsText()
FROM OPENJSON(:wkts) j;
""")


def union_polygons(db: Session, wkts: list[str]) -> str | None:
    """Dissolve several polygons (e.g. adjacent mapped zones sharing edges, which are invalid as one MultiPolygon) into one
    POLYGON / MULTIPOLYGON WKT. None when SQL Server cannot parse them or the result is not areal."""
    try:
        wkt = db.execute(_UNION, {"wkts": json.dumps(wkts)}).scalar()
    except DBAPIError:
        return None
    return wkt if isinstance(wkt, str) and wkt.upper().startswith(("POLYGON", "MULTIPOLYGON")) else None


def _clean(msg: str) -> str:
    i = msg.find("System.FormatException:")
    j = msg.find("System.ArgumentException:")
    k = max(i, j)
    return msg[k:].split(":", 1)[-1].strip()[:300] if k >= 0 else "SQL Server rejected the geometry."


_OVERLAPS = text("""
SET NOCOUNT ON;
DECLARE @g geography = (SELECT boundary FROM dbo.farm_boundaries WHERE id = :bid);
DECLARE @area float = @g.STArea();
SELECT ob.id AS other_boundary_id, ob.farm_id AS other_farm_id,
       @g.STIntersection(ob.boundary).STArea() AS overlap_m2, @area AS area_m2, ob.boundary.STArea() AS other_area_m2,
       CASE WHEN @g.STEquals(ob.boundary) = 1 THEN 'EQUAL'
            WHEN @g.STContains(ob.boundary) = 1 THEN 'CONTAINS'
            WHEN ob.boundary.STContains(@g) = 1 THEN 'WITHIN'
            ELSE 'PARTIAL' END AS relation,
       f.farmer_id AS other_farmer_id, f.organization_id AS other_organization_id
FROM dbo.farm_boundaries ob
JOIN dbo.farms f ON f.id = ob.farm_id
WHERE ob.status = 'CURRENT' AND ob.farm_id <> :farm_id AND f.environment = :env
  -- an INACTIVE farm still taking part in an open project keeps its land, so a new farm drawn on it is flagged (double counting)
  AND (f.status <> 'INACTIVE' OR EXISTS (SELECT 1 FROM dbo.project_farms pf JOIN dbo.projects p ON p.id = pf.project_id
                                         WHERE pf.farm_id = f.id AND pf.status = 'ACTIVE'
                                           -- projects.holds_land: open, or CLOSED after it monitored the land
                                           AND (p.status <> 'CLOSED' OR EXISTS (SELECT 1 FROM dbo.monitoring_periods mp
                                  WHERE mp.project_id = p.id
                                  AND mp.status IN ('ACTIVE', 'DATA_COLLECTION', 'SUBMITTED', 'QA_REVIEW', 'REJECTED', 'APPROVED', 'CLOSED')))))
  AND ob.boundary.STIntersects(@g) = 1;
""")


@dataclass(frozen=True)
class OverlapHit:
    other_boundary_id: uuid.UUID
    other_farm_id: uuid.UUID
    overlap_m2: float
    area_m2: float
    other_area_m2: float
    relation: str
    other_farmer_id: uuid.UUID
    other_organization_id: uuid.UUID


def find_overlaps(db: Session, boundary_id: uuid.UUID, farm_id: uuid.UUID, environment: str) -> list[OverlapHit]:
    rows = db.execute(_OVERLAPS, {"bid": boundary_id, "farm_id": farm_id, "env": environment}).all()
    return [OverlapHit(uuid.UUID(str(r[0])), uuid.UUID(str(r[1])), float(r[2] or 0), float(r[3] or 0), float(r[4] or 0), r[5],
                       uuid.UUID(str(r[6])), uuid.UUID(str(r[7]))) for r in rows]


_AT_POINT = text("""
SET NOCOUNT ON;
DECLARE @p geography = geography::Point(:lat, :lon, 4326);
SELECT b.farm_id FROM dbo.farm_boundaries b JOIN dbo.farms f ON f.id = b.farm_id
WHERE b.status = 'CURRENT' AND f.environment = :env AND b.boundary.STIntersects(@p) = 1;
""")

_NEAR = text("""
SET NOCOUNT ON;
DECLARE @p geography = geography::Point(:lat, :lon, 4326);
SELECT TOP (:lim) b.farm_id, b.boundary.STDistance(@p) AS distance_m
FROM dbo.farm_boundaries b JOIN dbo.farms f ON f.id = b.farm_id
WHERE b.status = 'CURRENT' AND f.environment = :env AND b.boundary.STDistance(@p) <= :radius
ORDER BY distance_m;
""")


def farms_at_point(db: Session, lat: float, lon: float, environment: str) -> list[uuid.UUID]:
    return [uuid.UUID(str(r[0])) for r in db.execute(_AT_POINT, {"lat": lat, "lon": lon, "env": environment}).all()]


def farms_near(db: Session, lat: float, lon: float, radius_m: float, environment: str, limit: int = 100
               ) -> list[tuple[uuid.UUID, Decimal]]:
    rows = db.execute(_NEAR, {"lat": lat, "lon": lon, "radius": radius_m, "env": environment, "lim": limit}).all()
    return [(uuid.UUID(str(r[0])), Decimal(str(round(r[1], 2)))) for r in rows]


def point_distance_to_boundary_m(db: Session, boundary_id: uuid.UUID, lat: float, lon: float) -> float:
    row = db.execute(text("SELECT boundary.STDistance(geography::Point(:lat, :lon, 4326)) FROM dbo.farm_boundaries WHERE id = :bid"),
                     {"lat": lat, "lon": lon, "bid": boundary_id}).one()
    return float(row[0])



# ---------------------------------------------------------------- projects (Phase 3)
_PROJECT_UNION = text("""
SET NOCOUNT ON;
DECLARE @u geography = (
    SELECT geography::UnionAggregate(b.boundary)
    FROM dbo.project_farms pf
    JOIN dbo.farms f ON f.id = pf.farm_id
    JOIN dbo.farm_boundaries b ON b.id = f.current_boundary_id
    WHERE pf.project_id = :pid AND pf.status = 'ACTIVE');
DECLARE @sum float = (
    SELECT SUM(b.boundary.STArea())
    FROM dbo.project_farms pf
    JOIN dbo.farms f ON f.id = pf.farm_id
    JOIN dbo.farm_boundaries b ON b.id = f.current_boundary_id
    WHERE pf.project_id = :pid AND pf.status = 'ACTIVE');
SELECT @u.STAsText() AS wkt, @u.STArea() AS area_m2, @sum AS sum_m2, @u.STIsValid() AS valid, @u.EnvelopeAngle() AS angle,
       @u.STGeometryType() AS gtype, @u.STNumGeometries() AS parts;
""")


@dataclass(frozen=True)
class ProjectUnion:
    wkt: str | None
    area_m2: float
    sum_m2: float
    valid: bool
    geometry_type: str | None
    parts: int


def project_union(db: Session, project_id: uuid.UUID) -> ProjectUnion:
    """Union of the current boundaries of the project's active farms (geography::UnionAggregate). Overlapping
    farm areas count once in the union area; `sum_m2` is the plain sum, so sum - union = internal overlap."""
    r = db.execute(_PROJECT_UNION, {"pid": project_id}).one()
    return ProjectUnion(r[0], float(r[1] or 0), float(r[2] or 0), bool(r[3]) and (r[4] is None or float(r[4]) < 90), r[5], int(r[6] or 0))


_PROJECT_OVERLAPS = text("""
SET NOCOUNT ON;
DECLARE @g geography = (SELECT boundary FROM dbo.project_boundaries WHERE id = :bid);
SELECT ob.project_id, p.organization_id, @g.STIntersection(ob.boundary).STArea() AS overlap_m2
FROM dbo.project_boundaries ob
JOIN dbo.projects p ON p.id = ob.project_id
WHERE ob.status = 'CURRENT' AND ob.project_id <> :pid AND p.environment = :env
  -- projects.holds_land: open, or CLOSED after it monitored the land
  AND (p.status <> 'CLOSED' OR EXISTS (SELECT 1 FROM dbo.monitoring_periods mp
       WHERE mp.project_id = p.id AND mp.status IN ('ACTIVE', 'DATA_COLLECTION', 'SUBMITTED', 'QA_REVIEW', 'REJECTED', 'APPROVED', 'CLOSED')))
  AND ob.boundary.STIntersects(@g) = 1;
""")


def project_overlaps(db: Session, boundary_id: uuid.UUID, project_id: uuid.UUID, environment: str) -> list[tuple[uuid.UUID, uuid.UUID, float]]:
    rows = db.execute(_PROJECT_OVERLAPS, {"bid": boundary_id, "pid": project_id, "env": environment}).all()
    return [(uuid.UUID(str(r[0])), uuid.UUID(str(r[1])), float(r[2] or 0)) for r in rows]


_CROSS_PROJECT_FARM_OVERLAPS = text("""
SET NOCOUNT ON;
DECLARE @u geography = (
    SELECT geography::UnionAggregate(b.boundary)
    FROM dbo.project_farms pf
    JOIN dbo.farms f ON f.id = pf.farm_id
    JOIN dbo.farm_boundaries b ON b.id = f.current_boundary_id
    WHERE pf.project_id = :pid AND pf.status = 'ACTIVE');
SELECT pf.farm_id, opf.project_id, op.organization_id, opf.farm_id, b.boundary.STIntersection(ob.boundary).STArea() AS overlap_m2
FROM dbo.farm_boundaries ob
JOIN dbo.farms ofm ON ofm.current_boundary_id = ob.id
JOIN dbo.project_farms opf ON opf.farm_id = ofm.id AND opf.status = 'ACTIVE' AND opf.project_id <> :pid
JOIN dbo.projects op ON op.id = opf.project_id AND op.environment = :env
     -- projects.holds_land: open, or CLOSED after it monitored the land (its participation dates may have been credited)
     AND (op.status <> 'CLOSED' OR EXISTS (SELECT 1 FROM dbo.monitoring_periods mp
          WHERE mp.project_id = op.id AND mp.status IN ('ACTIVE', 'DATA_COLLECTION', 'SUBMITTED', 'QA_REVIEW', 'REJECTED', 'APPROVED', 'CLOSED')))
JOIN dbo.project_farms pf ON pf.project_id = :pid AND pf.status = 'ACTIVE' AND pf.farm_id <> ofm.id
JOIN dbo.farms f ON f.id = pf.farm_id
JOIN dbo.farm_boundaries b ON b.id = f.current_boundary_id
WHERE ob.boundary.STIntersects(@u) = 1 AND b.boundary.STIntersects(ob.boundary) = 1
  AND (opf.participation_end IS NULL OR pf.participation_start <= opf.participation_end)
  AND (pf.participation_end IS NULL OR opf.participation_start <= pf.participation_end);
""")


def cross_project_farm_overlaps(db: Session, project_id: uuid.UUID, environment: str
                                ) -> list[tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, float]]:
    """Live, farm-level form of the project-boundary overlap: (farm_id, other_project_id, other_organization_id, other_farm_id,
    overlap_m2) for each active farm of the project whose current boundary intersects the current boundary of a *different* farm
    actively participating, over overlapping dates, in another non-CLOSED project of the environment."""
    rows = db.execute(_CROSS_PROJECT_FARM_OVERLAPS, {"pid": project_id, "env": environment}).all()
    return [(uuid.UUID(str(r[0])), uuid.UUID(str(r[1])), uuid.UUID(str(r[2])), uuid.UUID(str(r[3])), float(r[4] or 0)) for r in rows]


# ---------------------------------------------------------------- MRV / sampling (Phase 5)
_STRATA_DISTANCE = text("""
SELECT a.geometry.STDistance(b.geometry) FROM dbo.project_strata a, dbo.project_strata b WHERE a.id = :a AND b.id = :b;
""")


def strata_distance_m(db: Session, a: uuid.UUID, b: uuid.UUID) -> float | None:
    """Shortest geodesic distance between two strata geometries (0 when they touch or overlap); None if either has none."""
    r = db.execute(_STRATA_DISTANCE, {"a": a, "b": b}).first()
    return float(r[0]) if r and r[0] is not None else None



_UNION_OF = text("""
SET NOCOUNT ON;
DECLARE @u geography = (SELECT geography::UnionAggregate(boundary) FROM dbo.farm_boundaries
                        WHERE id IN (SELECT CAST([value] AS uniqueidentifier) FROM OPENJSON(:ids)));
SELECT @u.STAsText(), @u.STArea(), @u.STIsValid(), @u.STGeometryType();
""")


def union_of_boundaries(db: Session, boundary_ids: list[uuid.UUID]) -> tuple[str | None, float, bool, str | None]:
    """Union of the given farm boundary versions (stratum geometry). Area in m² by SQL Server."""
    import json as _json
    r = db.execute(_UNION_OF, {"ids": _json.dumps([str(b) for b in boundary_ids])}).one()
    return r[0], float(r[1] or 0), bool(r[2]), r[3]


_CONTAINS_MANY = text("""
SET NOCOUNT ON;
SELECT j.k, b.id, b.farm_id
FROM OPENJSON(:pts) WITH (k int '$.k', lat float '$.lat', lon float '$.lon') j
CROSS APPLY (SELECT TOP 1 fb.id, fb.farm_id FROM dbo.farm_boundaries fb
             WHERE fb.id IN (SELECT CAST([value] AS uniqueidentifier) FROM OPENJSON(:bids))
               AND fb.boundary.STIntersects(geography::Point(j.lat, j.lon, 4326)) = 1) b;
""")


def points_in_boundaries(db: Session, points: list[tuple[float, float]], boundary_ids: list[uuid.UUID]
                         ) -> dict[int, tuple[uuid.UUID, uuid.UUID]]:
    """Index of each point that lies inside one of the given farm boundaries → (boundary_id, farm_id). Authoritative
    containment by SQL Server (STIntersects); points on no boundary are absent from the result."""
    import json as _json
    if not points:
        return {}
    pts = _json.dumps([{"k": i, "lat": lat, "lon": lon} for i, (lat, lon) in enumerate(points)])
    rows = db.execute(_CONTAINS_MANY, {"pts": pts, "bids": _json.dumps([str(b) for b in boundary_ids])}).all()
    return {int(r[0]): (uuid.UUID(str(r[1])), uuid.UUID(str(r[2]))) for r in rows}


_NEAREST_EXISTING = text("""
SET NOCOUNT ON;
SELECT j.k, MIN(sp.location.STDistance(geography::Point(j.lat, j.lon, 4326)))
FROM OPENJSON(:pts) WITH (k int '$.k', lat float '$.lat', lon float '$.lon') j
JOIN dbo.sampling_points sp ON sp.monitoring_period_id = :period AND sp.status <> 'CANCELLED'
WHERE (:exclude IS NULL OR sp.id <> :exclude)
GROUP BY j.k;
""")


def nearest_existing_point_m(db: Session, period_id: uuid.UUID, points: list[tuple[float, float]],
                             exclude_id: uuid.UUID | None = None) -> dict[int, float]:
    import json as _json
    if not points:
        return {}
    pts = _json.dumps([{"k": i, "lat": lat, "lon": lon} for i, (lat, lon) in enumerate(points)])
    return {int(r[0]): float(r[1]) for r in db.execute(_NEAREST_EXISTING, {"pts": pts, "period": period_id, "exclude": exclude_id}).all()}


def distance_to_point_m(db: Session, point_id: uuid.UUID, lat: float, lon: float) -> float:
    row = db.execute(text("SELECT location.STDistance(geography::Point(:lat, :lon, 4326)) FROM dbo.sampling_points WHERE id = :pid"),
                     {"lat": lat, "lon": lon, "pid": point_id}).one()
    return float(row[0])


def point_inside_boundary(db: Session, boundary_id: uuid.UUID, lat: float, lon: float) -> bool:
    row = db.execute(text("SELECT boundary.STIntersects(geography::Point(:lat, :lon, 4326)) FROM dbo.farm_boundaries WHERE id = :bid"),
                     {"lat": lat, "lon": lon, "bid": boundary_id}).one()
    return bool(row[0])


def point_inside_project(db: Session, project_boundary_id: uuid.UUID, lat: float, lon: float) -> bool:
    row = db.execute(text("SELECT boundary.STIntersects(geography::Point(:lat, :lon, 4326)) FROM dbo.project_boundaries WHERE id = :bid"),
                     {"lat": lat, "lon": lon, "bid": project_boundary_id}).one()
    return bool(row[0])
