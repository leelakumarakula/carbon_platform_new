import { MapConfig } from '../core/api/client-config.service';
import { boundsOf } from './geo';
import { expandTileUrl, style3d } from './geo-map-3d';

const BASE: MapConfig = { provider: 'osm-dev', tile_url: 'https://tile.example/{z}/{x}/{y}.png', attribution: 'OSM', max_zoom: 19,
  subdomains: [] };

describe('3D map helpers', () => {
  it('expands Leaflet {s} subdomains into one URL each', () => {
    expect(expandTileUrl('https://t.example/{z}/{x}/{y}.png', [])).toEqual(['https://t.example/{z}/{x}/{y}.png']);
    expect(expandTileUrl('https://{s}.t.example/{z}.png', ['x', 'y'])).toEqual(['https://x.t.example/{z}.png', 'https://y.t.example/{z}.png']);
    expect(expandTileUrl('https://{s}.t.example/{z}.png', [])).toHaveLength(3);
  });

  it('adds terrain and hillshade only when an elevation source is configured', () => {
    const flat = style3d(BASE);
    expect(Object.keys(flat.sources)).toEqual(['base']);
    expect(flat.terrain).toBeUndefined();
    const relief = style3d({ ...BASE, terrain: { tile_url: 'https://dem.example/{z}/{x}/{y}.png', encoding: 'terrarium', max_zoom: 15,
      attribution: 'DEM' } });
    expect(relief.terrain).toEqual({ source: 'terrain', exaggeration: 1.5 });
    expect(relief.sources['terrain']).toMatchObject({ type: 'raster-dem', encoding: 'terrarium', maxzoom: 15 });
    expect(relief.layers.map((l) => l.id)).toEqual(['base', 'hillshade']);
  });

  it('adds satellite imagery only when configured, and shows either it or the basemap', () => {
    expect(style3d(BASE, 'satellite').layers.map((l) => l.id)).toEqual(['base']);   // nothing configured: basemap only
    const sat = { ...BASE, satellite: { tile_url: 'https://img.example/{z}/{y}/{x}', max_zoom: 18, attribution: 'Imagery' } };
    const s = style3d(sat, 'satellite');
    expect(s.sources['satellite']).toMatchObject({ type: 'raster', tiles: ['https://img.example/{z}/{y}/{x}'], maxzoom: 18 });
    expect(s.layers.map((l) => [l.id, l.layout?.visibility])).toEqual([['base', 'none'], ['satellite', 'visible']]);
    expect(style3d(sat, 'map').layers.map((l) => [l.id, l.layout?.visibility])).toEqual([['base', 'visible'], ['satellite', 'none']]);
  });

  it('frames polygons, multipolygons and extra points', () => {
    expect(boundsOf([])).toBeNull();
    const b = boundsOf([
      { type: 'Polygon', coordinates: [[[73.79, 20.0], [73.80, 20.0], [73.80, 20.01], [73.79, 20.0]]] },
      { type: 'MultiPolygon', coordinates: [[[[73.70, 19.9], [73.71, 19.9], [73.71, 19.91], [73.70, 19.9]]]] },
    ], [[73.85, 20.05]]);
    expect(b).toEqual([[73.70, 19.9], [73.85, 20.05]]);
  });
});
