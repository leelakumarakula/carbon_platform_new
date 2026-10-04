import { ChangeDetectionStrategy, Component } from '@angular/core';

interface Plot { d: string; fill: string; delay: number }
interface Pt { x: number; y: number }

/** Deterministic pseudo-random numbers (mulberry32): the scene is identical on every load and in every test. */
function rng(seed: number): () => number {
  let a = seed;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const W = 640, H = 400, COLS = 8, ROWS = 5;
const FILLS = ['#2c5e3c', '#356b40', '#3f7843', '#4f8746', '#5d9149', '#6f9c4b', '#82a94d'];

function buildScene(): { plots: Plot[]; points: Pt[]; boundary: string } {
  const r = rng(7);
  const cw = W / COLS, ch = H / ROWS;
  // jittered lattice with shared corners, so plots tile like real field patchwork
  const node = Array.from({ length: ROWS + 1 }, (_, j) => Array.from({ length: COLS + 1 }, (_, i) => ({
    x: i * cw + (i > 0 && i < COLS ? (r() - .5) * cw * .45 : 0),
    y: j * ch + (j > 0 && j < ROWS ? (r() - .5) * ch * .45 : 0),
  })));
  const plots: Plot[] = [];
  const points: Pt[] = [];
  for (let j = 0; j < ROWS; j++) {
    for (let i = 0; i < COLS; i++) {
      const [a, b, c, d] = [node[j][i], node[j][i + 1], node[j + 1][i + 1], node[j + 1][i]];
      const cx = (a.x + b.x + c.x + d.x) / 4, cy = (a.y + b.y + c.y + d.y) / 4;
      const shrink = (p: { x: number; y: number }) => {
        const dx = cx - p.x, dy = cy - p.y, len = Math.hypot(dx, dy) || 1;
        return `${(p.x + (dx / len) * 4).toFixed(1)},${(p.y + (dy / len) * 4).toFixed(1)}`;
      };
      plots.push({ d: `M${shrink(a)} L${shrink(b)} L${shrink(c)} L${shrink(d)} Z`, fill: FILLS[Math.floor(r() * FILLS.length)],
        delay: +((i + j) * 0.04).toFixed(2) });
      if (i >= 2 && i <= 5 && j >= 1 && j <= 3 && r() > .45) points.push({ x: +cx.toFixed(1), y: +cy.toFixed(1) });
    }
  }
  const p = (jj: number, ii: number) => `${node[jj][ii].x.toFixed(1)},${node[jj][ii].y.toFixed(1)}`;
  const boundary = `M${p(1, 2)} L${p(1, 4)} L${p(1, 6)} L${p(2, 6)} L${p(4, 6)} L${p(4, 4)} L${p(4, 2)} L${p(3, 2)} Z`;
  return { plots, points, boundary };
}

const SCENE = buildScene();

/** Aerial field-map illustration for the sign-in screen: field plots, a project boundary and its sampling points. Plots fade in and the
 *  boundary traces once on load; sampling points pulse and a satellite pass sweeps the fields. Decorative only (aria-hidden by the parent). */
@Component({
  selector: 'app-field-scene',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg [attr.viewBox]="'0 0 ' + w + ' ' + h" preserveAspectRatio="xMidYMid slice" class="scene">
      <rect [attr.width]="w" [attr.height]="h" fill="#1f4a32" />
      <g class="plots">
        @for (pl of plots; track $index) {
          <path [attr.d]="pl.d" [attr.fill]="pl.fill" [style.animation-delay]="pl.delay + 's'" />
        }
      </g>
      <path class="boundary" [attr.d]="boundary" pathLength="1" />
      @for (pt of points; track $index) {
        <circle class="ring" [attr.cx]="pt.x" [attr.cy]="pt.y" r="4.5" [style.animation-delay]="(1.8 + $index * .35) + 's'" />
        <circle class="dot" [attr.cx]="pt.x" [attr.cy]="pt.y" r="4.5" />
      }
      <!-- satellite pass: a soft band sweeps the fields -->
      <defs>
        <linearGradient id="fs-scan" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stop-color="#b3cd6b" stop-opacity="0" />
          <stop offset=".85" stop-color="#b3cd6b" stop-opacity=".22" />
          <stop offset="1" stop-color="#e9f5c9" stop-opacity=".9" />
        </linearGradient>
      </defs>
      <rect class="scan" x="0" y="-90" [attr.width]="w" height="90" fill="url(#fs-scan)" />
    </svg>
  `,
  styles: `
    :host { display: block; }
    .scene { width: 100%; height: 100%; display: block; }
    .plots path { stroke: #1f4a32; stroke-width: 1; opacity: 0; animation: plot .5s ease-out forwards; }
    .boundary { fill: rgb(232 197 71 / 8%); stroke: #e8c547; stroke-width: 2.2; stroke-dasharray: 1; stroke-dashoffset: 1; stroke-linejoin: round;
      animation: trace 1.2s .5s cubic-bezier(.4,0,.2,1) forwards; }
    .dot { fill: #ffffff; stroke: #1f4a32; stroke-width: 2; opacity: 0; animation: plot .3s 1.6s ease-out forwards; }
    .ring { fill: none; stroke: #ffffff; stroke-width: 1.5; opacity: 0; transform-box: fill-box; transform-origin: center;
      animation: ring 2.8s ease-out infinite; }
    .scan { animation: scan 7s 1.2s cubic-bezier(.45,0,.55,1) infinite; }
    @keyframes ring { 0% { opacity: .9; transform: scale(1); } 100% { opacity: 0; transform: scale(3.6); } }
    @keyframes scan { 0% { transform: translateY(0); } 60%, 100% { transform: translateY(500px); } }
    @keyframes plot { to { opacity: 1; } }
    @keyframes trace { to { stroke-dashoffset: 0; } }
    @media (prefers-reduced-motion: reduce) {
      .plots path, .dot { opacity: 1; animation: none; } .boundary { stroke-dashoffset: 0; animation: none; } .ring, .scan { display: none; }
    }
  `,
})
export class FieldScene {
  protected readonly w = W;
  protected readonly h = H;
  protected readonly plots = SCENE.plots;
  protected readonly points = SCENE.points;
  protected readonly boundary = SCENE.boundary;
}
