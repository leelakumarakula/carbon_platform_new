import type { GeoGeometry } from '../farms/farm.models';

export type LonLat = [number, number];

/** Polygon from drawn vertices (lon, lat). The ring is closed here; SQL Server fixes orientation. */
export function polygonFromVertices(vertices: readonly LonLat[]): GeoGeometry | null {
  const pts = vertices.filter((v, i) => i === 0 || v[0] !== vertices[i - 1][0] || v[1] !== vertices[i - 1][1]);
  if (new Set(pts.map((p) => p.join(','))).size < 3) return null;
  const ring = [...pts.map((p) => [round(p[0]), round(p[1])])];
  const first = ring[0];
  const last = ring[ring.length - 1];
  if (first[0] !== last[0] || first[1] !== last[1]) ring.push([...first]);
  return { type: 'Polygon', coordinates: [ring] };
}

export function round(v: number, digits = 7): number {
  const f = 10 ** digits;
  return Math.round(v * f) / f;
}

export function formatArea(hectares: number | string | null | undefined): string {
  if (hectares === null || hectares === undefined || hectares === '') return '—';
  const n = Number(hectares);
  return `${n.toLocaleString(undefined, { maximumFractionDigits: n < 10 ? 4 : 2 })} ha`;
}

/** [[minLon, minLat], [maxLon, maxLat]] over polygons and extra (lon, lat) positions; null when there is nothing to frame. */
export function boundsOf(geometries: readonly GeoGeometry[], extra: readonly LonLat[] = []): [LonLat, LonLat] | null {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const visit = (c: unknown): void => {
    if (Array.isArray(c) && typeof c[0] === 'number') {
      const [x, y] = c as number[];
      minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    } else if (Array.isArray(c)) {
      c.forEach(visit);
    }
  };
  geometries.forEach((g) => visit(g.coordinates));
  extra.forEach(visit);
  return Number.isFinite(minX) ? [[minX, minY], [maxX, maxY]] : null;
}

/** A typed coordinate is usable only as a finite WGS84 latitude / longitude. */
export function validLatLon(lat: number, lon: number): boolean {
  return Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180;
}

/**
 * Typed / pasted corners, one per line as "latitude, longitude" (comma, semicolon, tab or space separated; blank lines
 * ignored). Returns the corners as (lon, lat) plus a message per unusable line. Nothing is guessed: a line that is not
 * exactly two numbers in range is reported, never fixed.
 */
export function parseLatLonLines(text: string): { points: LonLat[]; errors: string[] } {
  const points: LonLat[] = [];
  const errors: string[] = [];
  text.split(/\r?\n/).forEach((line, i) => {
    const raw = line.trim();
    if (!raw) return;
    const parts = raw.split(/[\s,;]+/).filter(Boolean);
    const [lat, lon] = parts.map(Number);
    if (parts.length !== 2 || !validLatLon(lat, lon)) {
      errors.push(`Line ${i + 1}: "${raw}" is not "latitude, longitude" (latitude −90…90, longitude −180…180).`);
    } else {
      points.push([lon, lat]);
    }
  });
  return { points, errors };
}

/** Decide whether an uploaded boundary file is KML (otherwise it is treated as GeoJSON). */
export function isKml(fileName: string, text: string): boolean {
  return /\.kml$/i.test(fileName) || /^\s*(<\?xml[^>]*>\s*)?<kml[\s>]/i.test(text);
}
