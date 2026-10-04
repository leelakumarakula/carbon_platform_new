import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { RouterLink } from '@angular/router';
import { Observable, catchError, forkJoin, map, of } from 'rxjs';

import { AuditApi, OrganizationsApi, UsersApi } from '../admin/admin.api';
import { AuditLog } from '../admin/admin.models';
import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NAVIGATION, visibleNavigation } from '../core/navigation/nav.config';
import { FarmersApi } from '../farmer/farmers.api';
import { FarmsApi } from '../farms/farms.api';
import { ProjectsApi } from '../projects/projects.api';
import { CountUp } from '../shared/count-up';

interface Kpi {
  label: string;
  value: number | null;
  icon: string;
  link: string;
  caption: string;
}

interface Stage { label: string; icon: string; route: string }

/** The platform lifecycle (spec §3), each stage linked to the page that runs it. */
/** Lifecycle phases drawn above the stepper; `start` is the 1-based first stage, `span` how many stages it groups. */
const PHASES = [
  { name: 'Onboard', start: 1, span: 3 },
  { name: 'Design', start: 4, span: 2 },
  { name: 'Measure', start: 6, span: 3 },
  { name: 'Assure', start: 9, span: 2 },
  { name: 'Trade', start: 11, span: 2 },
  { name: 'Share', start: 13, span: 2 },
];

const STAGES: Stage[] = [
  { label: 'Farmer', icon: 'person_add', route: '/farmers' },
  { label: 'Farm', icon: 'agriculture', route: '/farms' },
  { label: 'Project', icon: 'workspaces', route: '/projects' },
  { label: 'Methodology', icon: 'menu_book', route: '/methodologies' },
  { label: 'MRV', icon: 'monitor_heart', route: '/mrv' },
  { label: 'Field work', icon: 'location_on', route: '/field' },
  { label: 'Laboratory', icon: 'science', route: '/laboratory' },
  { label: 'Calculation', icon: 'calculate', route: '/calculations' },
  { label: 'Verification', icon: 'fact_check', route: '/vvb' },
  { label: 'Registry', icon: 'account_balance', route: '/registry' },
  { label: 'Credits', icon: 'toll', route: '/ledger' },
  { label: 'Marketplace', icon: 'storefront', route: '/marketplace' },
  { label: 'Revenue', icon: 'payments', route: '/finance/revenue' },
  { label: 'Payout', icon: 'volunteer_activism', route: '/finance/payouts' },
];

@Component({
  selector: 'app-dashboard-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatCardModule, MatIconModule, RouterLink, DatePipe, CountUp],
  templateUrl: './dashboard-page.html',
  styles: `
    /* ---------- welcome banner: flat forest ---------- */
    .hero { position: relative; overflow: hidden; border-radius: var(--cp-radius); padding: 28px 32px; margin-bottom: 20px; color: #dbe8df;
      background: var(--cp-forest); }
    .hero-art { position: absolute; right: 0; top: 0; height: 100%; width: min(640px, 70%); pointer-events: none;
      mask-image: linear-gradient(90deg, transparent, #000 35%); }
    .contours path { stroke-dasharray: 3 9; animation: flow 18s linear infinite; }
    .contours path:nth-child(2) { animation-duration: 24s; animation-direction: reverse; }
    .co2 circle { opacity: 0; animation: settle linear infinite; }
    .sprout { transform-box: fill-box; transform-origin: 50% 100%; animation: sprout 1s var(--cp-ease) both; }
    .sprout:nth-child(2) { animation-delay: .15s; } .sprout:nth-child(3) { animation-delay: .3s; }
    .sprout:nth-child(4) { animation-delay: .45s; } .sprout:nth-child(5) { animation-delay: .6s; }
    @keyframes sprout { from { transform: scale(0); opacity: 0; } to { transform: none; opacity: 1; } }
    @keyframes flow { to { stroke-dashoffset: -240; } }
    @keyframes settle { 0% { opacity: 0; transform: translateY(10px); } 15% { opacity: .9; } 80% { opacity: .7; }
      100% { opacity: 0; transform: translateY(196px); } }
    .hero-text { position: relative; max-width: 760px; }
    .hero .eyebrow { color: var(--cp-lime-2); }
    h1 { margin: 10px 0 6px; color: #fff; font: 600 clamp(24px, 2.6vw, 32px)/1.2 var(--cp-font); letter-spacing: -.02em; }
    .tag { margin: 0 0 18px; font: italic 16px/1.4 var(--cp-serif); color: #cfe0d4; }
    .roles { display: flex; flex-wrap: wrap; gap: 8px; }
    .role { display: inline-flex; align-items: center; gap: 6px; height: 30px; padding: 0 12px; border-radius: 6px; font-size: 13px; color: #fff;
      background: rgb(255 255 255 / 9%); border: 1px solid rgb(255 255 255 / 14%); }
    .role small { color: #a9c4b2; margin-left: 2px; }
    .role mat-icon { color: var(--cp-lime-2); }
    .no-roles { margin: 0; color: #cfe0d4; }

    /* ---------- KPI cards: lime top edge, uppercase label, figure, lime rule ---------- */
    .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 20px; }
    .kpi { position: relative; display: flex; flex-direction: column; gap: 8px; padding: 18px 20px; text-decoration: none; color: inherit;
      background: #fff; border-radius: var(--cp-radius); border: 1px solid var(--cp-line); border-top: 3px solid var(--cp-lime);
      box-shadow: var(--cp-shadow); transition: border-color .15s, box-shadow .15s; }
    .kpi:hover { border-color: var(--cp-line-2); border-top-color: var(--cp-forest); box-shadow: var(--cp-shadow-md); }
    .kpi .value { font: 500 32px/1.1 var(--cp-font); color: var(--cp-forest); letter-spacing: -.02em; }
    .kpi .caption { font: 400 13px/1.4 var(--cp-font); color: var(--cp-ink-2); }
    .kpi-icon { position: absolute; right: 16px; top: 16px; font-size: 22px; width: 22px; height: 22px; color: var(--cp-ink-3); }

    /* ---------- lifecycle: phase bands over a connected stepper ---------- */
    .journey { background: #fff; border: 1px solid var(--cp-line); border-radius: var(--cp-radius); padding: 22px 20px 18px; margin-bottom: 20px;
      box-shadow: var(--cp-shadow); }
    .journey-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
    .journey h2 { margin: 0; font: 600 17px var(--cp-font); color: var(--cp-navy); }
    .journey .sub { margin: 4px 0 0; font: italic 14.5px var(--cp-serif); color: var(--cp-maroon); }
    .legend { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--cp-ink-2); }
    .key { width: 10px; height: 10px; border-radius: 50%; background: #eef2ee; border: 2px solid var(--cp-line-2); margin-left: 10px; }
    .key.open { background: #fff; border-color: var(--cp-lime); margin-left: 0; }
    .flow-scroll { overflow-x: auto; margin: 18px -8px 0; padding: 0 8px 4px; }
    .flow { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(14, minmax(72px, 1fr)); row-gap: 14px; }
    .phase { grid-row: 1; padding: 0 6px; }
    .phase span { display: block; padding-top: 8px; border-top: 2px solid var(--cp-line); font: 600 10.5px var(--cp-font); letter-spacing: .14em;
      text-transform: uppercase; color: var(--cp-ink-3); text-align: center; }
    .stop { grid-row: 2; position: relative; animation: cp-rise .45s var(--cp-ease) both; animation-delay: calc(var(--i) * 45ms + 120ms); }
    /* connector: from the previous dot's centre to this one, drawn left to right */
    .stop::before { content: ''; position: absolute; top: 22px; left: calc(-50% + 26px); width: calc(100% - 52px); height: 2px; border-radius: 2px;
      background: var(--cp-line-2); transform-origin: left; animation: draw .4s var(--cp-ease) both; animation-delay: calc(var(--i) * 45ms + 260ms); }
    .stop:nth-child(7)::before { display: none; } /* first stop (after the six phase items) */
    .step { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 0 2px; text-align: center; text-decoration: none;
      color: var(--cp-ink-3); outline: none; }
    .dot { display: grid; place-items: center; width: 46px; height: 46px; box-sizing: border-box; border-radius: 50%; background: #f1f4f0;
      border: 2px solid var(--cp-line); color: #a7b5ad; transition: transform .25s var(--cp-ease), background-color .2s, color .2s, border-color .2s,
      box-shadow .25s; }
    .dot mat-icon { font-size: 21px; width: 21px; height: 21px; }
    .num { margin-top: 2px; font: 600 10.5px var(--cp-font); letter-spacing: .08em; }
    .label { font: 500 12px/1.25 var(--cp-font); }
    .step.open { color: var(--cp-navy); }
    .step.open .dot { background: #fff; border-color: var(--cp-lime); color: var(--cp-forest); }
    .step.open .num { color: var(--cp-lime); }
    .step.open:hover .dot, .step.open:focus-visible .dot { transform: translateY(-3px); background: var(--cp-forest); border-color: var(--cp-forest);
      color: #fff; box-shadow: 0 8px 18px rgb(0 66 37 / 25%); }
    .step.open:hover .label { color: var(--cp-forest); }
    .step.open:focus-visible .dot { outline: 2px solid var(--cp-lime); outline-offset: 3px; }
    @keyframes draw { from { transform: scaleX(0); } to { transform: none; } }

    /* ---------- cards ---------- */
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 20px; align-items: start; }
    .links { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 10px; }
    .tile { display: flex; align-items: center; gap: 10px; height: 52px; box-sizing: border-box; padding: 0 12px; border-radius: 10px;
      text-decoration: none; color: var(--cp-ink); border: 1px solid var(--cp-line); background: #fff; transition: border-color .15s, background-color .15s; }
    .tile:hover { border-color: var(--cp-forest); background: var(--cp-mint-2); }
    .tile span:not(.tile-ico) { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500; font-size: 13.5px; }
    .tile-ico { display: grid; place-items: center; width: 32px; height: 32px; border-radius: 8px; background: var(--cp-lime-soft); color: var(--cp-forest); flex: none; }
    .tile-ico mat-icon { font-size: 18px; width: 18px; height: 18px; }
    .tile .go { font-size: 18px; width: 18px; height: 18px; color: var(--cp-ink-3); }
    .tile:hover .go { color: var(--cp-forest); }
    .activity { list-style: none; padding: 0; margin: 0 0 12px; position: relative; }
    .activity::before { content: ''; position: absolute; left: 5px; top: 10px; bottom: 10px; width: 2px; background: var(--cp-line); }
    .activity li { position: relative; display: flex; gap: 14px; padding: 8px 0; }
    .activity .node { flex: none; width: 12px; height: 12px; border-radius: 50%; background: #fff; border: 2px solid var(--cp-lime); margin-top: 4px; z-index: 1; }
    .activity strong { display: block; font-weight: 500; color: var(--cp-navy); font-size: 13.5px; }
    .activity small { color: var(--cp-ink-2); }
    .more { display: inline-flex; align-items: center; gap: 4px; font-weight: 500; text-decoration: none; }
    .muted { color: var(--cp-ink-2); }
    @media (max-width: 600px) { .hero { padding: 22px; } }
  `,
})
export class DashboardPage implements OnInit {
  protected readonly auth = inject(AuthService);
  private readonly users = inject(UsersApi);
  private readonly orgs = inject(OrganizationsApi);
  private readonly audit = inject(AuditApi);
  private readonly farmers = inject(FarmersApi);
  private readonly farms = inject(FarmsApi);
  private readonly projects = inject(ProjectsApi);

  protected readonly stages = STAGES;
  protected readonly phases = PHASES;
  /** Hero illustration: fixed positions so the banner is identical on every load. */
  protected readonly sprouts = [300, 360, 420, 480, 540];
  protected readonly particles = Array.from({ length: 16 }, (_, i) => ({
    x: 250 + ((i * 97) % 340), r: 1.6 + (i % 3) * .7, d: 7 + (i % 5) * 1.3, delay: -(i * 0.9),
  }));
  protected readonly today = new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  protected readonly kpis = signal<Kpi[]>([]);
  protected readonly recent = signal<AuditLog[] | null>(null);
  protected readonly firstName = computed(() => (this.auth.user()?.full_name ?? '').trim().split(/\s+/)[0] ?? '');
  private readonly visible = computed(() => visibleNavigation(NAVIGATION, (c) => this.auth.has(c)).flatMap((s) => s.items));
  private readonly routes = computed(() => new Set(this.visible().map((i) => i.route)));
  /** One tile per destination (two nav items can share a route, e.g. Farms and My farms). */
  protected readonly shortcuts = computed(() => {
    const seen = new Set<string>();
    return this.visible().filter((i) => {
      if (i.route === '/dashboard' || seen.has(i.route)) return false;
      seen.add(i.route);
      return true;
    });
  });

  ngOnInit(): void {
    const count = (obs: Observable<{ total: number }>): Observable<number | null> => obs.pipe(map((r) => r.total), catchError(() => of(null)));
    const wanted: Record<string, Observable<number | null>> = {};
    if (this.auth.has(P.FARMERS_READ)) {
      wanted['farmers'] = count(this.farmers.list({ page_size: 1 }));
      wanted['activeFarmers'] = count(this.farmers.list({ page_size: 1, status: 'ACTIVE' }));
    }
    if (this.auth.has(P.FARMS_READ)) {
      wanted['farms'] = count(this.farms.list({ page_size: 1 }));
      wanted['verifiedFarms'] = count(this.farms.list({ page_size: 1, status: 'VERIFIED' }));
    }
    if (this.auth.has(P.PROJECTS_READ)) wanted['projects'] = count(this.projects.list({ page_size: 1 }));
    if (this.auth.has(P.USERS_READ)) wanted['users'] = count(this.users.list({ page_size: 1, status: 'ACTIVE' }));
    if (this.auth.has(P.ORGANIZATIONS_READ)) wanted['orgs'] = count(this.orgs.list({ page_size: 1 }));
    if (Object.keys(wanted).length) {
      forkJoin(wanted).subscribe((r) => {
        const k: Kpi[] = [];
        const add = (key: string, label: string, icon: string, link: string, caption: string) => {
          if (key in r) k.push({ label, value: r[key], icon, link, caption });
        };
        add('farmers', 'Farmers', 'groups', '/farmers', 'registered on the platform');
        add('activeFarmers', 'Active farmers', 'how_to_reg', '/farmers', 'KYC verified and consenting');
        add('farms', 'Farms', 'agriculture', '/farms', 'mapped boundaries');
        add('verifiedFarms', 'Verified farms', 'verified', '/farms', 'cleared by GIS review');
        add('projects', 'Projects', 'workspaces', '/projects', 'carbon projects');
        add('users', 'Active users', 'badge', '/admin/users', 'people with access');
        add('orgs', 'Organizations', 'domain', '/admin/organizations', 'developers, labs, VVBs, buyers');
        this.kpis.set(k);
      });
    }
    if (this.auth.has(P.AUDIT_READ)) {
      this.audit.auditLogs({ page_size: 6 }).subscribe({ next: (p) => this.recent.set(p.items), error: () => this.recent.set([]) });
    }
  }

  protected canOpen(route: string): boolean {
    return this.routes().has(route);
  }

  /** FARM_OWNERSHIP_REVIEWED → "Farm ownership reviewed". */
  protected human(action: string): string {
    const t = action.replace(/_/g, ' ').toLowerCase();
    return t.charAt(0).toUpperCase() + t.slice(1);
  }
}
