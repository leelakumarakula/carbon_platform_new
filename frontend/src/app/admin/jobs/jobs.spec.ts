import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Me } from '../../core/auth/auth.models';
import { AuthService } from '../../core/auth/auth.service';
import { NAVIGATION, visibleNavigation } from '../../core/navigation/nav.config';
import { Job, JobsStatus, jobBadge } from './jobs.api';
import { JobsPage } from './jobs-page';

function signIn(permissions: string[], environment = 'LIVE'): void {
  TestBed.inject(AuthService).me.set({ user: { id: 'u1', email: 'x@test.example', full_name: 'X', environment, must_change_password: false },
    permissions } as unknown as Me);
}

function job(over: Partial<Job> = {}): Job {
  return { id: 'j1', job_code: 'JOB-2026-000001', job_type: 'EXPIRY_CREDIT_RESERVATIONS', task_name: 'maintenance.expire_credit_reservations',
    queue_name: 'maintenance', status: 'QUEUED', environment: 'LIVE', trigger_type: 'SCHEDULE', organization_id: null, entity_type: null,
    entity_id: null, scheduled_at: null, available_at: '2026-10-03T00:00:00Z', claimed_at: null, claimed_by: null, started_at: null,
    completed_at: null, failed_at: null, cancelled_at: null, retry_count: 0, max_retries: 3, error_code: null, error_message: null,
    result: null, published_at: null, publish_attempts: 1, last_publish_error: 'BROKER_NOT_CONFIGURED', reason: null,
    created_by_name: 'SYSTEM — background jobs (LIVE)', created_at: '2026-10-03T00:00:00Z', can_cancel: true, can_retry: false, ...over };
}

const STATUS: JobsStatus = { environment: 'LIVE', database: 'ok', broker: 'NOT_CONFIGURED', workers: [], worker_alive: false,
  counts: { QUEUED: 1, FAILED: 1 }, last_scheduled_at: null, note: 'No worker heartbeat' };

describe('Background jobs', () => {
  it('appears in Administration for jobs.read only', () => {
    const labels = (perms: string[]) => visibleNavigation(NAVIGATION, (c) => perms.includes(c)).flatMap((s) => s.items.map((i) => i.label));
    expect(labels(['jobs.read'])).toContain('Background jobs');
    for (const perms of [['users.read'], ['payouts.read', 'payouts.execute'], ['farmers.self'], ['credits.manage']]) {
      expect(labels(perms)).not.toContain('Background jobs');
    }
    expect(jobBadge('FAILED')).toBe('FAILED');
    expect(jobBadge('SUCCEEDED')).toBe('ACTIVE');
  });

  describe('page', () => {
    let http: HttpTestingController;
    beforeEach(() => {
      TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
      http = TestBed.inject(HttpTestingController);
    });

    it('shows broker and worker status separately, offers only cancel / retry, and never a "run task" control', async () => {
      signIn(['jobs.read', 'jobs.manage']);
      const f = TestBed.createComponent(JobsPage);
      f.detectChanges();
      http.expectOne('/api/v1/jobs/registry').flush([{ job_type: 'EXPIRY_CREDIT_RESERVATIONS', task_name: 'maintenance.expire_credit_reservations',
        queue: 'maintenance', description: 'Expire due reservations', environments: ['DEMO', 'LIVE'], scheduled_every_seconds: 600,
        manually_triggerable: true, max_retries: 3, soft_time_limit: 270, time_limit: 300, idempotency: 'locked re-check' }]);
      http.expectOne('/api/v1/jobs/status').flush(STATUS);
      http.expectOne((r) => r.url === '/api/v1/jobs').flush([job(), job({ id: 'j2', job_code: 'JOB-2026-000002', status: 'FAILED',
        error_code: 'DATABASE_UNAVAILABLE', error_message: 'database error (Error)', can_cancel: false, can_retry: true })]);
      await f.whenStable();
      f.detectChanges();
      const el = f.nativeElement as HTMLElement;
      expect(el.querySelector('[data-testid="jobs-broker"]')?.textContent).toContain('Not configured');
      expect(el.querySelector('[data-testid="jobs-worker"]')?.textContent).toContain('No heartbeat');
      const text = el.querySelector('[data-testid="jobs"]')?.textContent ?? '';
      expect(text).toContain('Cancel');
      expect(text).toContain('Retry');
      expect(text).toContain('JOB-2026-000001');
      const buttons = Array.from(el.querySelectorAll('button')).map((b) => (b.textContent ?? '').trim().toLowerCase());
      expect(buttons.some((b) => b.includes('run') || b.includes('trigger') || b.includes('execute'))).toBe(false);
      expect(el.querySelector('[data-testid="job-registry"]')?.textContent).toContain('every 10 min');
    });

    it('a reader without jobs.manage sees no actions; DEMO shows the honest note', async () => {
      signIn(['jobs.read'], 'DEMO');
      const f = TestBed.createComponent(JobsPage);
      f.detectChanges();
      http.expectOne('/api/v1/jobs/registry').flush([]);
      http.expectOne('/api/v1/jobs/status').flush({ ...STATUS, environment: 'DEMO', note: 'DEMO — background jobs act only on DEMO records.' });
      http.expectOne((r) => r.url === '/api/v1/jobs').flush([job({ environment: 'DEMO', can_cancel: false })]);
      await f.whenStable();
      f.detectChanges();
      const el = f.nativeElement as HTMLElement;
      expect(el.querySelector('[data-testid="jobs-demo-note"]')?.textContent).toContain('DEMO');
      expect(el.querySelector('[data-testid="jobs"]')?.textContent).not.toContain('Cancel');
    });
  });
});
