"""Deterministic candidate generation for sampling points (pure, no database).

The generator only proposes candidate coordinates inside a bounding box; SQL Server decides which candidates lie
inside the stratum's farm boundaries (authoritative containment). The sample *count* always comes from the approved
sampling design — this module never derives a count from area.

- SIMPLE_RANDOM / STRATIFIED_RANDOM: seeded uniform candidates in the box (the stratum is the strata unit for
  STRATIFIED_RANDOM; allocation per stratum is configured in the design)
- SYSTEMATIC_GRID: a regular grid with a seeded random offset; spacing starts at sqrt(area / n) and is tightened
  until enough grid nodes fall inside the stratum

Coordinates are WGS84 degrees; a local metres-per-degree factor is used for spacing (accurate for farm-sized areas).
"""
import math
import random
from collections.abc import Iterator
from dataclasses import dataclass

EARTH_M_PER_DEG_LAT = 111_320.0


@dataclass(frozen=True)
class BBox:
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    @property
    def center_lat(self) -> float:
        return (self.min_lat + self.max_lat) / 2


def bbox_of(coords: list[tuple[float, float]]) -> BBox:
    """coords are (lon, lat) pairs."""
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return BBox(min(lons), min(lats), max(lons), max(lats))


def metres_per_degree_lon(lat: float) -> float:
    return EARTH_M_PER_DEG_LAT * math.cos(math.radians(lat))


def distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Approximate ground distance between (lat, lon) points (equirectangular; fine for spacing checks)."""
    mid = math.radians((a[0] + b[0]) / 2)
    dy = (a[0] - b[0]) * EARTH_M_PER_DEG_LAT
    dx = (a[1] - b[1]) * EARTH_M_PER_DEG_LAT * math.cos(mid)
    return math.hypot(dx, dy)


def random_candidates(box: BBox, seed: int, batch: int) -> Iterator[list[tuple[float, float]]]:
    """Endless batches of seeded uniform (lat, lon) candidates."""
    rng = random.Random(seed)  # noqa: S311 (seeded, reproducible sampling — not security)
    while True:
        yield [(rng.uniform(box.min_lat, box.max_lat), rng.uniform(box.min_lon, box.max_lon)) for _ in range(batch)]


def grid_candidates(box: BBox, area_m2: float, n: int, seed: int, shrink: float) -> list[tuple[float, float]]:
    """Grid nodes (lat, lon) with spacing sqrt(area / n) * shrink metres and a seeded offset."""
    spacing = max(math.sqrt(max(area_m2, 1.0) / max(n, 1)) * shrink, 1.0)
    dlat = spacing / EARTH_M_PER_DEG_LAT
    dlon = spacing / metres_per_degree_lon(box.center_lat)
    rng = random.Random(seed)  # noqa: S311 (seeded, reproducible sampling — not security)
    lat0 = box.min_lat + rng.random() * dlat
    lon0 = box.min_lon + rng.random() * dlon
    out: list[tuple[float, float]] = []
    lat = lat0
    while lat <= box.max_lat:
        lon = lon0
        while lon <= box.max_lon:
            out.append((round(lat, 7), round(lon, 7)))
            lon += dlon
        lat += dlat
    return out


def accept_spaced(candidates: list[tuple[float, float]], accepted: list[tuple[float, float]], min_distance_m: float, limit: int
                  ) -> list[tuple[float, float]]:
    """Accept candidates in order while they keep `min_distance_m` from every accepted point (and each other)."""
    out: list[tuple[float, float]] = []
    for c in candidates:
        if len(accepted) + len(out) >= limit:
            break
        if all(distance_m(c, a) >= min_distance_m for a in [*accepted, *out]):
            out.append(c)
    return out
