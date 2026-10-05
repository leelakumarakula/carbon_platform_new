import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { GeoMap, supportsWebGl } from './geo-map';

describe('GeoMap default view', () => {
  beforeEach(() => TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] }));
  afterEach(() => vi.restoreAllMocks());

  function create(inputs: Record<string, unknown>) {
    const f = TestBed.createComponent(GeoMap);
    for (const [k, v] of Object.entries(inputs)) f.componentRef.setInput(k, v);
    (f.componentInstance as unknown as { ngOnInit(): void }).ngOnInit();
    return { f, mode: (f.componentInstance as unknown as { mode(): string }).mode() };
  }

  it('opens in 3D when the browser supports WebGL, in 2D for editors, without WebGL or when 3D is not offered', () => {
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({} as RenderingContext);
    expect(supportsWebGl()).toBe(true);
    expect(create({}).mode).toBe('3d');
    expect(create({ defaultMode: '2d' }).mode).toBe('2d');            // boundary editor: drawing happens in 2D
    expect(create({ allow3d: false }).mode).toBe('2d');
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
    expect(supportsWebGl()).toBe(false);
    expect(create({}).mode).toBe('2d');                                // no WebGL: never a broken 3D view
  });

  it('falls back to 2D when the 3D view reports that it cannot start', () => {
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({} as RenderingContext);
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const { f } = create({});
    const cmp = f.componentInstance as unknown as { mode(): string; fallBack(reason: string): void };
    expect(cmp.mode()).toBe('3d');
    cmp.fallBack('no WebGL context');
    expect(cmp.mode()).toBe('2d');
  });
});
