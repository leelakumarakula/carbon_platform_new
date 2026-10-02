"""Parse farm boundaries from GeoJSON / KML into WKT, and WKT back to GeoJSON.

Only structural checks happen here (shape, closure, coordinate ranges, vertex limits). Topological
validity (self-intersection), orientation and area are decided by SQL Server (app/repositories/gis.py).
"""
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

Ring = list[tuple[float, float]]          # (lon, lat)
Polygon = list[Ring]                      # outer ring + holes


class GeometryError(ValueError):
    def __init__(self, message: str, code: str = "INVALID_GEOMETRY") -> None:
        super().__init__(message)
        self.code = code


@dataclass
class ParsedBoundary:
    polygons: list[Polygon]
    notes: list[str] = field(default_factory=list)

    @property
    def vertex_count(self) -> int:
        return sum(len(r) for p in self.polygons for r in p)

    def to_wkt(self) -> str:
        def ring(r: Ring) -> str:
            return "(" + ", ".join(f"{_fmt(x)} {_fmt(y)}" for x, y in r) + ")"
        if len(self.polygons) == 1:
            return "POLYGON(" + ", ".join(ring(r) for r in self.polygons[0]) + ")"
        return "MULTIPOLYGON(" + ", ".join("(" + ", ".join(ring(r) for r in p) + ")" for p in self.polygons) + ")"


def _fmt(v: float) -> str:
    return f"{v:.8f}".rstrip("0").rstrip(".")


def _ring(coords: Any, notes: list[str], where: str) -> Ring:
    if not isinstance(coords, list) or not coords:
        raise GeometryError(f"{where}: expected a list of [longitude, latitude] positions.")
    pts: Ring = []
    for i, c in enumerate(coords):
        if not isinstance(c, (list, tuple)) or len(c) < 2:
            raise GeometryError(f"{where}, position {i + 1}: expected [longitude, latitude].")
        try:
            lon, lat = float(c[0]), float(c[1])
        except (TypeError, ValueError) as e:
            raise GeometryError(f"{where}, position {i + 1}: coordinates must be numbers.") from e
        if lon != lon or lat != lat:  # NaN
            raise GeometryError(f"{where}, position {i + 1}: coordinates must be numbers.")
        if not -180 <= lon <= 180 or not -90 <= lat <= 90:
            raise GeometryError(f"{where}, position {i + 1}: ({lon}, {lat}) is outside longitude -180..180 / latitude -90..90. "
                                "GeoJSON order is [longitude, latitude].", "COORDINATE_OUT_OF_RANGE")
        pts.append((lon, lat))
    if pts[0] != pts[-1]:
        pts.append(pts[0])
        notes.append(f"{where} was not closed; the first point was repeated to close it.")
    deduped: Ring = [pts[0]]
    for p in pts[1:]:
        if p != deduped[-1]:
            deduped.append(p)
    if len(deduped) < 4 or len(set(deduped)) < 3:
        raise GeometryError(f"{where}: a polygon needs at least 3 distinct corners.", "TOO_FEW_POINTS")
    return deduped


def _polygon(coords: Any, notes: list[str], where: str) -> Polygon:
    if not isinstance(coords, list) or not coords:
        raise GeometryError(f"{where}: polygon has no rings.")
    return [_ring(r, notes, f"{where} {'outer ring' if i == 0 else f'hole {i}'}") for i, r in enumerate(coords)]


def parse_geojson(data: Any, max_vertices: int = 5000) -> ParsedBoundary:
    if isinstance(data, (str, bytes)):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            raise GeometryError(f"Not valid JSON: {e.msg} (line {e.lineno}).", "INVALID_GEOJSON") from e
    if not isinstance(data, dict):
        raise GeometryError("GeoJSON must be an object.", "INVALID_GEOJSON")
    t = data.get("type")
    if t == "FeatureCollection":
        feats = data.get("features") or []
        if len(feats) != 1:
            raise GeometryError(f"The FeatureCollection must contain exactly one feature (found {len(feats)}).", "INVALID_GEOJSON")
        return parse_geojson(feats[0], max_vertices)
    if t == "Feature":
        return parse_geojson(data.get("geometry"), max_vertices)
    notes: list[str] = []
    if t == "Polygon":
        polys = [_polygon(data.get("coordinates"), notes, "Polygon")]
    elif t == "MultiPolygon":
        coords = data.get("coordinates")
        if not isinstance(coords, list) or not coords:
            raise GeometryError("MultiPolygon has no polygons.", "INVALID_GEOJSON")
        polys = [_polygon(p, notes, f"Polygon {i + 1}") for i, p in enumerate(coords)]
    else:
        raise GeometryError(f"Farm boundaries must be a Polygon or MultiPolygon, not {t!r}.", "UNSUPPORTED_GEOMETRY")
    parsed = ParsedBoundary(polys, notes)
    if parsed.vertex_count > max_vertices:
        raise GeometryError(f"Too many vertices ({parsed.vertex_count}); the limit is {max_vertices}. Simplify the boundary.",
                            "TOO_MANY_VERTICES")
    return parsed


_KML_NS = re.compile(r"\{[^}]*\}")


def parse_kml(text: str, max_vertices: int = 5000) -> ParsedBoundary:
    head = text[:4096].upper()
    if "<!DOCTYPE" in head or "<!ENTITY" in text.upper():
        raise GeometryError("KML with DOCTYPE or ENTITY declarations is not accepted.", "UNSAFE_KML")
    try:
        root = ET.fromstring(text)  # noqa: S314  (entities rejected above; no external resolution in ElementTree)
    except ET.ParseError as e:
        raise GeometryError(f"Not valid KML/XML: {e}.", "INVALID_KML") from e

    def local(el: ET.Element) -> str:
        return _KML_NS.sub("", el.tag)

    polygons: list[list[Any]] = []
    for poly in (el for el in root.iter() if local(el) == "Polygon"):
        rings: list[Any] = []
        for part in poly:
            kind = local(part)
            if kind not in ("outerBoundaryIs", "innerBoundaryIs"):
                continue
            coords_el = next((e for e in part.iter() if local(e) == "coordinates"), None)
            raw = (coords_el.text or "").strip() if coords_el is not None else ""
            if not raw:
                raise GeometryError("A KML ring has no coordinates.", "INVALID_KML")
            try:
                ring = [[float(t.split(",")[0]), float(t.split(",")[1])] for t in raw.split()]
            except (ValueError, IndexError) as e:
                raise GeometryError("KML coordinates must be 'longitude,latitude[,altitude]' numbers.", "INVALID_KML") from e
            rings.insert(0, ring) if kind == "outerBoundaryIs" else rings.append(ring)
        polygons.append(rings)
    if not polygons:
        raise GeometryError("No Polygon found in the KML file.", "INVALID_KML")
    geo = {"type": "Polygon", "coordinates": polygons[0]} if len(polygons) == 1 else {"type": "MultiPolygon", "coordinates": polygons}
    return parse_geojson(geo, max_vertices)


_NUM = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"


def wkt_to_geojson(wkt: str) -> dict[str, Any]:
    """Minimal WKT → GeoJSON for POLYGON / MULTIPOLYGON as returned by SQL Server STAsText()."""
    w = wkt.strip()
    upper = w.upper()

    def rings_of(body: str) -> list[list[list[float]]]:
        return [[[float(a), float(b)] for a, b in re.findall(rf"({_NUM})\s+({_NUM})", r)] for r in re.findall(r"\(([^()]*)\)", body)]

    if upper.startswith("POLYGON"):
        return {"type": "Polygon", "coordinates": rings_of(w[w.index("("):])}
    if upper.startswith("MULTIPOLYGON"):
        inner = w[w.index("(") + 1: w.rindex(")")]
        polys, depth, start = [], 0, 0
        for i, ch in enumerate(inner):
            if ch == "(":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    polys.append(rings_of(inner[start: i + 1]))
        return {"type": "MultiPolygon", "coordinates": polys}
    raise GeometryError(f"Unsupported WKT geometry: {w[:30]}…", "UNSUPPORTED_GEOMETRY")
