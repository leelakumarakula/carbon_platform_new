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

/** Decide whether an uploaded boundary file is KML (otherwise it is treated as GeoJSON). */
export function isKml(fileName: string, text: string): boolean {
  return /\.kml$/i.test(fileName) || /^\s*(<\?xml[^>]*>\s*)?<kml[\s>]/i.test(text);
}
