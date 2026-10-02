"""Boundary validation pipeline: parse (GeoJSON/KML) → structural checks → SQL Server validity/area → warnings."""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ValidationFailed
from app.repositories import gis
from app.rules.geometry_io import GeometryError, ParsedBoundary, parse_geojson, parse_kml, wkt_to_geojson


@dataclass
class BoundaryCheck:
    wkt: str
    geojson: dict[str, Any]
    area_m2: float
    area_hectares: float
    perimeter_m: float
    centroid_lat: float
    centroid_lon: float
    vertex_count: int
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_input(geojson: Any | None = None, kml: str | None = None) -> ParsedBoundary:
    s = get_settings()
    try:
        if kml is not None:
            return parse_kml(kml, s.FARM_MAX_VERTICES)
        if geojson is None:
            raise GeometryError("Provide a GeoJSON geometry or a KML document.", "GEOMETRY_REQUIRED")
        return parse_geojson(geojson, s.FARM_MAX_VERTICES)
    except GeometryError as e:
        raise ValidationFailed(str(e), error_code=e.code) from e


def check_boundary(db: Session, parsed: ParsedBoundary, declared_area_ha: Decimal | None = None) -> BoundaryCheck:
    s = get_settings()
    report = gis.validate_geometry(db, parsed.to_wkt())
    if not report.valid or not report.wkt:
        raise ValidationFailed(f"The boundary is not a valid polygon: {report.reason}", error_code="INVALID_POLYGON",
                               details={"reason": report.reason})
    if report.area_m2 <= 0:
        raise ValidationFailed("The boundary has no area.", error_code="INVALID_POLYGON")
    ha = report.area_m2 / 10_000
    notes = list(parsed.notes)
    if report.reoriented:
        notes.append("Ring orientation was corrected (the polygon had been drawn clockwise).")
    warnings: list[str] = []
    if ha > s.FARM_AREA_WARNING_HA:
        warnings.append(f"Measured area {ha:,.2f} ha is unusually large for one farm; check the boundary.")
    if declared_area_ha and declared_area_ha > 0:
        diff = abs(ha - float(declared_area_ha)) / float(declared_area_ha) * 100
        if diff > s.FARM_DECLARED_AREA_WARNING_PCT:
            warnings.append(f"Measured area {ha:,.4f} ha differs from the declared {float(declared_area_ha):,.4f} ha by {diff:.0f}%.")
    return BoundaryCheck(wkt=report.wkt, geojson=wkt_to_geojson(report.wkt), area_m2=report.area_m2, area_hectares=ha,
                         perimeter_m=report.perimeter_m, centroid_lat=report.centroid_lat, centroid_lon=report.centroid_lon,
                         vertex_count=parsed.vertex_count, notes=notes, warnings=warnings)
