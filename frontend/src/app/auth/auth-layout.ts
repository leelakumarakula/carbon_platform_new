import { ChangeDetectionStrategy, Component } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

import { CountUp } from '../shared/count-up';
import { FieldScene } from './field-scene';

/** The five stages the product showcase walks through, left to right. */
const PIPELINE = [
  { icon: 'agriculture', label: 'Farm' },
  { icon: 'colorize', label: 'Sample' },
  { icon: 'science', label: 'Lab' },
  { icon: 'verified', label: 'Credit' },
  { icon: 'payments', label: 'Payout' },
];

/**
 * Split layout shared by the sign-in and password screens. The left side is a product showcase: a field map with
 * floating cards that follow one sample from the soil to an issued credit. The form is projected on the right.
 * Everything on the left is illustrative (aria-hidden); no real data is shown before sign-in.
 */
@Component({
  selector: 'app-auth-layout',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatIconModule, FieldScene, CountUp],
  template: `
    <main class="auth">
      <aside class="showcase" aria-hidden="true">
        <div class="glow g1"></div><div class="glow g2"></div>

        <header class="top">
          <span class="wordmark">Carbon<b>Platform</b></span>
          <span class="pill"><span class="live"></span>dMRV · Soil carbon</span>
        </header>

        <div class="stage">
          <div class="visual">
            <figure class="map-card">
              <app-field-scene />
              <figcaption>
                <span><i class="sw boundary"></i>Project boundary</span>
                <span><i class="sw point"></i>Sampling points</span>
                <span class="right">Area measured Accurately</span>
              </figcaption>
            </figure>

            <div class="float f-sample">
              <span class="f-ico"><mat-icon>science</mat-icon></span>
              <span class="f-body"><small>Soil sample · 0–30 cm</small><strong>SOC 1.84 %</strong></span>
              <span class="ok"><mat-icon>check</mat-icon>Lab QA</span>
            </div>

            <div class="float f-credit">
              <small>Credits issued</small>
              <strong><app-count-up [value]="1240" [duration]="1800" /> <em>tCO₂e</em></strong>
              <span class="meta">VM0042 · Vintage 2026</span>
              <span class="bar"><i></i></span>
            </div>

            <div class="float f-payout">
              <span class="f-ico lime"><mat-icon>volunteer_activism</mat-icon></span>
              <span class="f-body"><small>Farmer share</small><strong>Settled</strong></span>
            </div>
          </div>

          <div class="copy">
            <h2>From soil to <span class="hl">verified</span> credit.</h2>
            <p class="tag">Every farm, sample and credit — traceable end to end.</p>
            <ol class="pipe">
              @for (p of pipeline; track p.label; let i = $index) {
                <li [style.--i]="i"><span class="pi"><mat-icon>{{ p.icon }}</mat-icon></span>{{ p.label }}</li>
              }
              <span class="runner"></span>
            </ol>
          </div>
        </div>

        <footer class="facts">
          <span><mat-icon>account_tree</mat-icon>Full lineage</span>
          <span><mat-icon>verified_user</mat-icon>Independent QA &amp; VVB</span>
          <span><mat-icon>history_edu</mat-icon>Immutable audit trail</span>
        </footer>
      </aside>

      <section class="form-panel">
        <div class="form-wrap"><ng-content /></div>
        <p class="legal"><mat-icon inline>lock</mat-icon> Encrypted session · Accounts are created by your administrator</p>
      </section>
    </main>
  `,
  styles: `
    :host { display: block; }
    .auth { min-height: 100vh; display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(440px, .85fr); background: #fff; }

    /* ---------- showcase ---------- */
    .showcase { position: relative; overflow: hidden; display: flex; flex-direction: column; gap: 28px; min-height: 100vh; box-sizing: border-box;
      padding: 36px clamp(32px, 4.5vw, 72px) 32px; color: #cfe0d4; background-color: #032a17;
      background-image: radial-gradient(rgb(255 255 255 / 7%) 1px, transparent 1px); background-size: 22px 22px; }
    .glow { position: absolute; border-radius: 50%; filter: blur(70px); pointer-events: none; animation: drift 16s ease-in-out infinite alternate; }
    .g1 { width: 520px; height: 520px; left: -160px; top: -180px; background: rgb(143 179 57 / 22%); }
    .g2 { width: 460px; height: 460px; right: -140px; bottom: -160px; background: rgb(29 107 67 / 45%); animation-delay: -8s; }
    @keyframes drift { to { transform: translate(60px, 40px) scale(1.12); } }
    .top, .stage, .facts { position: relative; }
    .top { display: flex; align-items: center; justify-content: space-between; gap: 12px; animation: cp-rise .6s var(--cp-ease) both; }
    .wordmark { font: 300 22px/1 var(--cp-font); color: #fff; letter-spacing: -.02em; }
    .wordmark b { font-weight: 600; color: var(--cp-lime-2); margin-left: 1px; }
    .pill { display: inline-flex; align-items: center; gap: 8px; height: 30px; padding: 0 12px; border-radius: 99px; font-size: 12px; color: #d8e8dc;
      background: rgb(255 255 255 / 6%); border: 1px solid rgb(255 255 255 / 12%); backdrop-filter: blur(6px); }
    .live { width: 7px; height: 7px; border-radius: 50%; background: var(--cp-lime); animation: ping 2s ease-out infinite; }
    @keyframes ping { 0% { box-shadow: 0 0 0 0 rgb(143 179 57 / 60%); } 70%, 100% { box-shadow: 0 0 0 7px rgb(143 179 57 / 0%); } }

    .stage { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 44px; }
    .visual { position: relative; margin: 0 28px 0 0; animation: cp-rise .8s .1s var(--cp-ease) both; }
    .map-card { margin: 0; border-radius: 18px; overflow: hidden; background: #1f4a32; border: 1px solid rgb(255 255 255 / 12%);
      box-shadow: 0 30px 60px rgb(0 0 0 / 35%), 0 0 0 6px rgb(255 255 255 / 3%); }
    .map-card app-field-scene { height: clamp(220px, 34vh, 340px); }
    figcaption { display: flex; flex-wrap: wrap; gap: 18px; align-items: center; padding: 11px 16px; font-size: 12px; color: #a9c4b2;
      background: rgb(0 25 14 / 85%); border-top: 1px solid rgb(255 255 255 / 8%); }
    figcaption span { display: inline-flex; align-items: center; gap: 8px; }
    figcaption .right { margin-left: auto; color: #e3efe6; }
    .sw { display: inline-block; width: 14px; height: 10px; border-radius: 2px; }
    .sw.boundary { border: 2px solid #e8c547; box-sizing: border-box; }
    .sw.point { width: 9px; height: 9px; border-radius: 50%; background: #fff; }

    /* floating glass cards */
    .float { position: absolute; display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-radius: 14px; color: #fff;
      background: rgb(8 40 24 / 72%); border: 1px solid rgb(255 255 255 / 14%); backdrop-filter: blur(14px) saturate(1.3);
      box-shadow: 0 18px 40px rgb(0 0 0 / 35%); }
    .float small { display: block; font-size: 11.5px; color: #a9c4b2; }
    .float strong { display: block; font: 600 16px/1.3 var(--cp-font); letter-spacing: -.01em; }
    .f-ico { display: grid; place-items: center; width: 36px; height: 36px; border-radius: 10px; background: rgb(255 255 255 / 10%); color: #e8f2ea; }
    .f-ico.lime { background: var(--cp-lime); color: #10301c; }
    .f-ico mat-icon { font-size: 19px; width: 19px; height: 19px; }
    .ok { display: inline-flex; align-items: center; gap: 3px; margin-left: 6px; padding: 3px 8px 3px 5px; border-radius: 99px; font-size: 11px;
      font-weight: 500; color: #10301c; background: var(--cp-lime-2); }
    .ok mat-icon { font-size: 14px; width: 14px; height: 14px; }
    .f-sample { top: -22px; right: -28px; animation: pop .6s .9s var(--cp-ease) both, bob 6s 1.5s ease-in-out infinite; }
    .f-credit { left: -26px; bottom: 34px; flex-direction: column; align-items: flex-start; gap: 2px; min-width: 210px; padding: 14px 16px;
      animation: pop .6s 1.3s var(--cp-ease) both, bob 7s 2s ease-in-out infinite; }
    .f-credit strong { font-size: 26px; font-weight: 600; color: #fff; }
    .f-credit em { margin-left: 4px; font-style: normal; font-size: 13px; font-weight: 500; color: var(--cp-lime-2); }
    .f-credit .meta { font-size: 11.5px; color: #a9c4b2; }
    .bar { display: block; width: 100%; height: 4px; margin-top: 8px; border-radius: 4px; background: rgb(255 255 255 / 10%); overflow: hidden; }
    .bar i { display: block; height: 100%; width: 100%; border-radius: 4px; background: var(--cp-lime); transform-origin: left;
      animation: fill 1.8s 1.4s var(--cp-ease) both; }
    .f-payout { right: -28px; top: 46%; animation: pop .6s 1.7s var(--cp-ease) both, bob 6.5s 2.4s ease-in-out infinite; }
    @keyframes pop { from { opacity: 0; transform: translateY(14px) scale(.94); } to { opacity: 1; transform: none; } }
    @keyframes bob { 0%, 100% { translate: 0 0; } 50% { translate: 0 -6px; } }
    @keyframes fill { from { transform: scaleX(0); } }

    /* headline + pipeline: a light travels Farm → Payout and lights each stage as it passes */
    .copy { animation: cp-rise .8s .25s var(--cp-ease) both; }
    h2 { margin: 0; color: #fff; font: 600 clamp(30px, 3.1vw, 46px)/1.08 var(--cp-font); letter-spacing: -.03em; }
    .hl { color: var(--cp-lime-2); }
    .tag { margin: 12px 0 24px; font: italic 400 clamp(15px, 1.3vw, 18px)/1.45 var(--cp-serif); color: #b9d0c0; }
    .pipe { position: relative; list-style: none; margin: 0; padding: 0; display: flex; justify-content: space-between; max-width: 520px; }
    .pipe::before { content: ''; position: absolute; left: 18px; right: 18px; top: 17px; height: 2px; background: rgb(255 255 255 / 12%); }
    .pipe li { position: relative; display: flex; flex-direction: column; align-items: center; gap: 6px; font-size: 12px; color: #b9d0c0; }
    .pi { display: grid; place-items: center; width: 36px; height: 36px; border-radius: 50%; background: #0a3a22; border: 1px solid rgb(255 255 255 / 16%);
      color: #dcebdf; animation: lit 5s calc(var(--i) * 1.1s) ease-in-out infinite; }
    .pi mat-icon { font-size: 18px; width: 18px; height: 18px; }
    @keyframes lit { 0%, 26%, 100% { background: #0a3a22; color: #dcebdf; border-color: rgb(255 255 255 / 16%); }
      6%, 16% { background: var(--cp-lime); color: #10301c; border-color: var(--cp-lime); } }
    .runner { position: absolute; top: 14px; left: 18px; width: 8px; height: 8px; border-radius: 50%; background: var(--cp-lime);
      box-shadow: 0 0 12px 3px rgb(143 179 57 / 60%); animation: run 5s linear infinite; }
    @keyframes run { from { left: 18px; } 88% { opacity: 1; } to { left: calc(100% - 26px); opacity: 0; } }

    .facts { display: flex; flex-wrap: wrap; gap: 10px 26px; padding-top: 20px; border-top: 1px solid rgb(255 255 255 / 9%); font-size: 13px;
      color: #b9d0c0; animation: cp-fade .8s .5s both; }
    .facts span { display: inline-flex; align-items: center; gap: 8px; }
    .facts mat-icon { color: var(--cp-lime-2); font-size: 18px; width: 18px; height: 18px; }

    /* ---------- form ---------- */
    .form-panel { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px 32px 24px;
      box-sizing: border-box; background: #fff; }
    .form-wrap { width: 100%; max-width: 384px; margin: auto 0; animation: cp-rise .7s .15s var(--cp-ease) both; }
    .legal { display: flex; align-items: center; gap: 6px; margin: 24px 0 0; font-size: 12px; color: var(--cp-ink-3); text-align: center; }

    @media (max-width: 1180px) { .f-payout { display: none; } .visual { margin-right: 16px; } }
    @media (max-width: 900px) {
      .auth { grid-template-columns: 1fr; grid-template-rows: auto 1fr; }
      .showcase { min-height: 0; padding: 20px 24px 24px; gap: 14px; }
      .visual, .facts, .tag, .pipe, .pill { display: none; }
      .stage { gap: 0; }
      h2 { font-size: 26px; }
      .form-panel { justify-content: flex-start; padding-top: 32px; }
      .form-wrap { margin: 0 0 auto; }
    }
  `,
})
export class AuthLayout {
  protected readonly pipeline = PIPELINE;
}
