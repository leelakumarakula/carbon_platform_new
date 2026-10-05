import { DatePipe, DecimalPipe, JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatTooltipModule } from '@angular/material/tooltip';

import { ApiError } from '../../core/api/api.models';
import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { reloadOn } from '../../shared/reload-on';
import { runAction } from '../../shared/run-action';
import { StateView } from '../../shared/state-view';
import { StatusBadge } from '../../shared/status-badge';
import {
  EXTERNAL_FETCH_KIND, ExternalDataType, ExternalDataView, ExternalObservation, ExternalProvider, Farm, NdviInterval, WeatherDay,
} from '../farm.models';
import { FarmsApi } from '../farms.api';

const TYPES: ExternalDataType[] = ['WEATHER', 'SOIL', 'SATELLITE_NDVI', 'LAND_RECORD'];
const FETCH_LABEL: Record<ExternalDataType, string> = {
  WEATHER: 'Fetch weather', SOIL: 'Fetch soil data', SATELLITE_NDVI: 'Fetch satellite NDVI', LAND_RECORD: 'Fetch land records',
};
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export interface MonthRow { month: string; label: string; days: number; rain: number | null; tmax: number | null; tmin: number | null }
interface Tick { y: number; text: string }
interface RainChart { title: string; base: number; ticks: Tick[]; bars: { d: string; x: number; label: string; title: string }[] }
interface NdviChart { title: string; base: number; ticks: Tick[]; path: string; points: { x: number; y: number; title: string }[];
  first: string; last: string }
interface ObsView { o: ExternalObservation; months: MonthRow[]; rain: RainChart | null; ndvi: NdviChart | null }

/** YYYY-MM-DD in local time (toISOString would shift the day east of UTC). */
export function isoDay(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function daysAgo(n: number, from = new Date()): Date {
  const d = new Date(from);
  d.setDate(d.getDate() - n);
  return d;
}

const mean = (xs: number[]): number | null => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
const nums = (xs: (number | null)[]): number[] => xs.filter((x): x is number => x !== null && Number.isFinite(x));

/** Daily weather → one row per calendar month (rain summed, temperatures averaged; missing values skipped). */
export function monthlyWeather(daily: WeatherDay[]): MonthRow[] {
  const by = new Map<string, WeatherDay[]>();
  for (const d of daily) {
    const k = d.date.slice(0, 7);
    by.set(k, [...(by.get(k) ?? []), d]);
  }
  return [...by.keys()].sort().map((k) => {
    const ds = by.get(k)!;
    const rain = nums(ds.map((d) => d.precipitation_mm));
    return { month: k, label: `${MONTHS[Number(k.slice(5, 7)) - 1]} ${k.slice(0, 4)}`, days: ds.length,
      rain: rain.length ? rain.reduce((a, b) => a + b, 0) : null, tmax: mean(nums(ds.map((d) => d.temp_max_c))),
      tmin: mean(nums(ds.map((d) => d.temp_min_c))) };
  });
}

/** Rounded-up axis maximum (1, 2, 2.5, 5 × 10ⁿ steps). */
function niceMax(v: number): number {
  if (!(v > 0)) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  return [1, 2, 2.5, 5, 10].map((m) => m * p).find((m) => m >= v)!;
}

// Chart frame (viewBox units); the SVG scales to its container width.
const W = 360, L = 34, R = 8, T = 10;

function rainChart(rows: MonthRow[]): RainChart | null {
  const data = rows.filter((r) => r.rain !== null);
  if (!data.length) return null;
  const H = 150, base = H - 20, top = niceMax(Math.max(...data.map((r) => r.rain!)));
  const band = (W - L - R) / rows.length, w = Math.min(24, band - 2), y = (v: number) => base - (v / top) * (base - T);
  const every = Math.ceil(rows.length / 12);
  const bars = rows.flatMap((r, i) => {
    if (r.rain === null) return [];
    const x = L + i * band + (band - w) / 2, yy = y(r.rain), rr = Math.min(4, w / 2, base - yy);
    const d = `M${x},${base}V${yy + rr}Q${x},${yy} ${x + rr},${yy}H${x + w - rr}Q${x + w},${yy} ${x + w},${yy + rr}V${base}Z`;
    return [{ d, x: x + w / 2, label: i % every ? '' : r.label.slice(0, 3), title: `${r.label}: ${r.rain.toFixed(1)} mm` }];
  });
  const wettest = data.reduce((a, b) => (b.rain! > a.rain! ? b : a));
  return { base, bars, ticks: [0, top / 2, top].map((v) => ({ y: y(v), text: String(v) })),
    title: `Monthly rainfall in mm, ${rows[0].label} to ${rows[rows.length - 1].label}; wettest ${wettest.label} with ${wettest.rain!.toFixed(1)} mm` };
}

function ndviChart(intervals: NdviInterval[]): NdviChart | null {
  const data = intervals.filter((i) => i.mean !== null && Number.isFinite(i.mean)).map((i) => ({ i,
    t: (Date.parse(i.from) + Date.parse(i.to)) / 2 })).sort((a, b) => a.t - b.t);
  if (!data.length) return null;
  const H = 120, base = H - 18, lo = Math.min(0, ...data.map((d) => d.i.mean!)), hi = 1;
  const t0 = data[0].t, t1 = data[data.length - 1].t;
  const x = (t: number) => (t1 === t0 ? (L + W - R) / 2 : L + ((t - t0) / (t1 - t0)) * (W - L - R - 8) + 4);
  const y = (v: number) => base - ((v - lo) / (hi - lo)) * (base - T);
  const points = data.map((d) => ({ x: x(d.t), y: y(d.i.mean!), title: `${d.i.from} – ${d.i.to}: mean NDVI ${d.i.mean!.toFixed(3)}` }));
  const ticks = [...new Set([lo, 0, 0.5, 1])].map((v) => ({ y: y(v), text: String(Math.round(v * 100) / 100) }));
  const m = data.map((d) => d.i.mean!);
  return { base, ticks, points, path: points.map((p, k) => `${k ? 'L' : 'M'}${p.x},${p.y}`).join(''),
    first: data[0].i.from, last: data[data.length - 1].i.to,
    title: `Mean NDVI over time, ${data[0].i.from} to ${data[data.length - 1].i.to}; ${data.length} interval(s), ` +
      `range ${Math.min(...m).toFixed(2)} to ${Math.max(...m).toFixed(2)}` };
}

/** Weather, soil, satellite NDVI and land records from external providers — reference evidence only (spec: never drives status). */
@Component({
  selector: 'app-farm-external-data-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, DecimalPipe, JsonPipe, ReactiveFormsModule, MatButtonModule, MatExpansionModule, MatFormFieldModule, MatIconModule,
    MatInputModule, MatTooltipModule, StateView, StatusBadge],
  template: `
    <div class="tab-body">
      <p class="note" role="note" data-testid="external-notice"><mat-icon inline>info</mat-icon>
        External data is reference evidence only. It never changes a farm's status, verification or any calculation.</p>
      <app-state-view [loading]="loading()" [error]="error()" (retry)="load()" />
      @if (view(); as v) {
        @if (v.can_fetch && !v.has_boundary) {
          <p class="note warn" data-testid="no-boundary">Save a boundary first. External data is fetched for the farm's saved boundary.</p>
        }
        <div class="providers">
          @for (p of v.providers; track p.data_type) {
            <div class="provider" [attr.data-provider]="p.data_type">
              <div class="head"><strong>{{ p.label }}</strong>
                <app-status-badge [status]="p.enabled ? 'ACTIVE' : 'DEACTIVATED'" [text]="p.enabled ? 'Enabled' : 'Not enabled'" /></div>
              <div class="muted small">{{ p.provider }}</div>
              @if (p.note) { <div class="small pnote">{{ p.note }}</div> }
              @if (v.can_fetch && v.has_boundary && (p.enabled || p.data_type !== 'LAND_RECORD')) {
                @if (range(p.data_type); as g) {
                  <div class="range" [formGroup]="g">
                    <mat-form-field subscriptSizing="dynamic"><mat-label>From</mat-label><input matInput type="date" formControlName="from" /></mat-form-field>
                    <mat-form-field subscriptSizing="dynamic"><mat-label>To</mat-label><input matInput type="date" formControlName="to" /></mat-form-field>
                  </div>
                }
                <div class="row-actions">
                  <button mat-stroked-button type="button" [attr.data-testid]="'fetch-' + kind(p.data_type)" (click)="fetch(p)"
                          [disabled]="busy() || !p.enabled || !rangeOk(p.data_type)"><mat-icon>cloud_download</mat-icon> {{ fetchLabel(p.data_type) }}</button>
                </div>
              }
            </div>
          }
        </div>
        @if (!v.can_fetch) { <p class="muted small">You can view external data for this farm but not fetch new data.</p> }

        @for (g of groups(); track g.type) {
          <h3 class="group">{{ g.label }} <span class="muted small">({{ g.items.length }})</span></h3>
          <mat-accordion multi>
            @for (it of g.items; track it.o.id; let first = $first) {
              <mat-expansion-panel [expanded]="first" [attr.data-observation]="it.o.data_type">
                <mat-expansion-panel-header class="obs-head">
                  <mat-panel-title>{{ period(it.o) }}</mat-panel-title>
                  <mat-panel-description>
                    <span>fetched {{ it.o.fetched_at | date: 'mediumDate' }}</span>
                    @if (it.o.environment === 'DEMO') { <app-status-badge status="DEMO" /> }
                  </mat-panel-description>
                </mat-expansion-panel-header>
                <p class="muted small meta">Source: {{ it.o.provider }} · {{ it.o.dataset }} · fetched {{ it.o.fetched_at | date: 'medium' }}
                  by {{ it.o.fetched_by_name ?? 'system' }} · point {{ it.o.latitude | number: '1.5-5' }}, {{ it.o.longitude | number: '1.5-5' }}
                  @if (it.o.boundary_version !== null) { · boundary v{{ it.o.boundary_version }} }
                  · SHA-256 <code tabindex="0" [matTooltip]="it.o.sha256" [attr.aria-label]="'SHA-256 ' + it.o.sha256">{{ it.o.sha256.slice(0, 12) }}</code></p>
                @switch (it.o.data_type) {
                  @case ('WEATHER') {
                    @if (it.o.summary.totals; as t) {
                      <p class="totals" data-testid="weather-totals">{{ t.days }} days · rainfall {{ t.precipitation_mm | number: '1.0-1' }} mm ·
                        ET₀ {{ t.et0_mm | number: '1.0-1' }} mm · mean max {{ t.temp_max_mean_c | number: '1.1-1' }} °C ·
                        mean min {{ t.temp_min_mean_c | number: '1.1-1' }} °C</p>
                    }
                    <div class="two">
                      <div class="table-wrap"><table class="table">
                        <thead><tr><th>Month</th><th class="num">Rain mm</th><th class="num">Mean Tmax °C</th><th class="num">Mean Tmin °C</th></tr></thead>
                        <tbody>@for (m of it.months; track m.month) {
                          <tr><td>{{ m.label }}</td><td class="num">{{ m.rain === null ? '—' : (m.rain | number: '1.1-1') }}</td>
                            <td class="num">{{ m.tmax === null ? '—' : (m.tmax | number: '1.1-1') }}</td>
                            <td class="num">{{ m.tmin === null ? '—' : (m.tmin | number: '1.1-1') }}</td></tr>
                        } @empty { <tr><td colspan="4" class="muted">No daily values.</td></tr> }</tbody>
                      </table></div>
                      @if (it.rain; as c) {
                        <figure class="chart">
                          <svg viewBox="0 0 360 150" role="img" [attr.aria-label]="c.title" data-testid="rain-chart">
                            <title>{{ c.title }}</title>
                            <g class="axis">
                              @for (t of c.ticks; track t.y) {
                                <line x1="34" x2="352" [attr.y1]="t.y" [attr.y2]="t.y" />
                                <text x="30" [attr.y]="t.y + 3" text-anchor="end">{{ t.text }}</text>
                              }
                            </g>
                            @for (b of c.bars; track $index) {
                              <path class="bar" [attr.d]="b.d"><title>{{ b.title }}</title></path>
                              @if (b.label) { <text class="xlabel" [attr.x]="b.x" [attr.y]="c.base + 13" text-anchor="middle">{{ b.label }}</text> }
                            }
                          </svg>
                          <figcaption class="muted small">Monthly rainfall (mm)</figcaption>
                        </figure>
                      }
                    </div>
                  }
                  @case ('SOIL') {
                    <div class="table-wrap"><table class="table">
                      <thead><tr><th>Property</th><th>Depth</th><th class="num">Value</th><th>Unit</th></tr></thead>
                      <tbody>@for (s of it.o.summary.layers ?? []; track $index) {
                        <tr><td>{{ s.label }}</td><td>{{ s.depth }}</td><td class="num">{{ s.value === null ? '—' : (s.value | number: '1.0-3') }}</td>
                          <td>{{ s.unit }}</td></tr>
                      } @empty { <tr><td colspan="4" class="muted">No soil values returned.</td></tr> }</tbody>
                    </table></div>
                  }
                  @case ('SATELLITE_NDVI') {
                    @if (it.o.summary.max_cloud_pct !== undefined) {
                      <p class="muted small">{{ perScene(it.o) ? 'Scenes with at most ' + it.o.summary.max_cloud_pct + '% of the plot under cloud or shadow.'
                        : 'Scenes with up to ' + it.o.summary.max_cloud_pct + '% cloud cover.' }}</p>
                    }
                    @if (it.o.summary.land_surface_temperature; as t) {
                      <p class="small" data-testid="lst">Land surface temperature {{ t.mean_c | number: '1.1-1' }} °C (min {{ t.min_c | number: '1.1-1' }}, max
                        {{ t.max_c | number: '1.1-1' }}) on {{ t.date }} · Landsat, {{ t.pixel_count }} pixels</p>
                    }
                    <div class="two">
                      <div class="table-wrap"><table class="table">
                        <thead><tr><th>{{ perScene(it.o) ? 'Scene date' : 'Interval' }}</th><th class="num">NDVI mean</th><th class="num">Min</th><th class="num">Max</th>
                          @if (perScene(it.o)) { <th class="num">NDMI</th><th class="num">Plot cloud</th> }<th class="num">Valid pixels</th></tr></thead>
                        <tbody>@for (n of it.o.summary.intervals ?? []; track $index) {
                          <tr><td>{{ n.from === n.to ? n.from : n.from + ' – ' + n.to }}</td><td class="num">{{ ndvi(n.mean) }}</td><td class="num">{{ ndvi(n.min) }}</td>
                            <td class="num">{{ ndvi(n.max) }}</td>
                            @if (perScene(it.o)) { <td class="num">{{ ndvi(n.ndmi_mean ?? null) }}</td><td class="num">{{ n.plot_cloud_pct ?? '—' }}%</td> }
                            <td class="num">{{ valid(n) }}</td></tr>
                        } @empty { <tr><td [attr.colspan]="perScene(it.o) ? 7 : 5" class="muted">No clear scene in this period.</td></tr> }</tbody>
                      </table></div>
                      @if (it.ndvi; as c) {
                        <figure class="chart">
                          <svg viewBox="0 0 360 120" role="img" [attr.aria-label]="c.title" data-testid="ndvi-chart">
                            <title>{{ c.title }}</title>
                            <g class="axis">
                              @for (t of c.ticks; track t.text) {
                                <line x1="34" x2="352" [attr.y1]="t.y" [attr.y2]="t.y" />
                                <text x="30" [attr.y]="t.y + 3" text-anchor="end">{{ t.text }}</text>
                              }
                              <text x="34" [attr.y]="c.base + 13">{{ c.first }}</text>
                              <text x="352" [attr.y]="c.base + 13" text-anchor="end">{{ c.last }}</text>
                            </g>
                            <path class="line" [attr.d]="c.path" />
                            @for (p of c.points; track $index) {
                              <circle class="dot" [attr.cx]="p.x" [attr.cy]="p.y" r="4"><title>{{ p.title }}</title></circle>
                            }
                          </svg>
                          <figcaption class="muted small">Mean NDVI per {{ perScene(it.o) ? 'clear scene' : 'interval' }}</figcaption>
                        </figure>
                      }
                    </div>
                    @if (it.o.summary.skipped?.length) {
                      <p class="muted small">Skipped (plot under cloud): {{ skippedText(it.o) }}</p>
                    }
                  }
                  @default { <pre class="small raw">{{ it.o.summary | json }}</pre> }
                }
              </mat-expansion-panel>
            }
          </mat-accordion>
        } @empty {
          @if (!loading()) { <p class="muted">No external data has been fetched for this farm yet.</p> }
        }
      }
    </div>
  `,
  styles: `
    .note mat-icon { vertical-align: -2px; margin-right: 4px; }
    .providers { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin: 12px 0; }
    .provider { border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; padding: 12px; background: var(--mat-sys-surface);
      display: flex; flex-direction: column; gap: 4px; min-width: 0; }
    .head { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
    .pnote { color: var(--mat-sys-on-surface-variant); }
    .range { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
    .range mat-form-field { flex: 1; min-width: 130px; }
    .group { font: var(--mat-sys-title-medium); margin: 20px 0 8px; }
    .obs-head { height: auto; min-height: 48px; padding-top: 6px; padding-bottom: 6px; }
    mat-panel-description { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
    .meta { overflow-wrap: anywhere; }
    .totals { margin: 4px 0 12px; }
    .two { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; align-items: start; }
    @media (max-width: 760px) { .two { grid-template-columns: minmax(0, 1fr); } }
    .num { text-align: right; font-variant-numeric: tabular-nums; }
    .table th.num { text-align: right; }
    .chart { margin: 0; }
    .chart svg { width: 100%; max-width: 520px; height: auto; display: block; }
    .axis line { stroke: var(--mat-sys-outline-variant); stroke-width: 1; }
    .axis text, .xlabel { fill: var(--mat-sys-on-surface-variant); font-size: 10px; }
    .bar { fill: #1565c0; }
    .line { fill: none; stroke: #2e7d32; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
    .dot { fill: #2e7d32; stroke: var(--mat-sys-surface, #fff); stroke-width: 2; }
    .raw { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 240px; overflow: auto; }
  `,
})
export class FarmExternalDataPanel {
  readonly farm = input.required<Farm>();
  private readonly api = inject(FarmsApi);
  private readonly notify = inject(NotifyService);
  protected readonly view = signal<ExternalDataView | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly busy = signal(false);
  protected readonly fetchLabel = (t: ExternalDataType) => FETCH_LABEL[t];
  protected readonly kind = (t: ExternalDataType) => EXTERNAL_FETCH_KIND[t];
  /** Weather: the archive lags a few days, so the default year ends a week ago. NDVI: the last 180 days. */
  protected readonly weatherRange = new FormGroup({
    from: new FormControl(isoDay(daysAgo(7 + 364)), { nonNullable: true }), to: new FormControl(isoDay(daysAgo(7)), { nonNullable: true }),
  });
  protected readonly ndviRange = new FormGroup({
    from: new FormControl(isoDay(daysAgo(179)), { nonNullable: true }), to: new FormControl(isoDay(new Date()), { nonNullable: true }),
  });

  /** Observations (newest first from the server) grouped by type, with client-side monthly / chart data. */
  protected readonly groups = computed(() => {
    const v = this.view();
    if (!v) return [];
    return TYPES.map((type) => ({
      type, label: v.providers.find((p) => p.data_type === type)?.label ?? label(type),
      items: v.observations.filter((o) => o.data_type === type).map((o): ObsView => {
        const months = type === 'WEATHER' ? monthlyWeather(o.summary.daily ?? []) : [];
        return { o, months, rain: type === 'WEATHER' ? rainChart(months) : null,
          ndvi: type === 'SATELLITE_NDVI' ? ndviChart(o.summary.intervals ?? []) : null };
      }),
    })).filter((g) => g.items.length);
  });

  constructor() {
    // Reload when the farm changes or a new boundary version is saved (has_boundary / centroid change).
    reloadOn(() => [this.farm().id, this.farm().current_boundary?.version], () => this.load());
  }

  load(): void {
    this.error.set(null);
    this.api.externalData(this.farm().id).subscribe({
      next: (v) => {
        this.view.set(v);
        this.loading.set(false);
      },
      error: (e: unknown) => {
        this.error.set(ApiError.from(e));
        this.loading.set(false);
      },
    });
  }

  range(t: ExternalDataType): FormGroup<{ from: FormControl<string>; to: FormControl<string> }> | null {
    return t === 'WEATHER' ? this.weatherRange : t === 'SATELLITE_NDVI' ? this.ndviRange : null;
  }

  rangeOk(t: ExternalDataType): boolean {
    const g = this.range(t);
    if (!g) return true;
    const { from, to } = g.getRawValue();
    return !!from && !!to && from <= to;
  }

  fetch(p: ExternalProvider): void {
    const r = this.range(p.data_type)?.getRawValue();
    runAction(this.api.fetchExternalData(this.farm().id, EXTERNAL_FETCH_KIND[p.data_type],
      { period_start: r?.from || null, period_end: r?.to || null }), this.busy, this.notify, `${p.label} fetched.`, () => this.load());
  }

  period(o: ExternalObservation): string {
    return o.period_start || o.period_end ? `${o.period_start ?? '…'} → ${o.period_end ?? '…'}` : o.dataset;
  }

  protected perScene(o: ExternalObservation): boolean {
    return o.provider === 'planetary-computer';
  }

  protected skippedText(o: ExternalObservation): string {
    return (o.summary.skipped ?? []).map((x) => x.date + (x.plot_cloud_pct === null ? '' : ' (' + x.plot_cloud_pct + '%)')).join(', ');
  }

  ndvi(v: number | null): string {
    return v === null ? '—' : v.toFixed(3);
  }

  valid(n: NdviInterval): string {
    return n.sample_count === null ? '—' : String(n.sample_count - (n.no_data_count ?? 0));
  }
}
