import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from '../../core/api/api.service';

/** Phase 12A — background jobs (operations). SQL Server is the record; the UI never names a task to run: the registry is read-only
 *  and retry / cancel act on existing jobs only. */
export interface Job {
  id: string; job_code: string; job_type: string; task_name: string; queue_name: string;
  status: 'QUEUED' | 'CLAIMED' | 'RUNNING' | 'SUCCEEDED' | 'RETRY_WAITING' | 'FAILED' | 'CANCELLED';
  environment: string; trigger_type: string; organization_id: string | null; entity_type: string | null; entity_id: string | null;
  scheduled_at: string | null; available_at: string; claimed_at: string | null; claimed_by: string | null; started_at: string | null;
  completed_at: string | null; failed_at: string | null; cancelled_at: string | null; retry_count: number; max_retries: number;
  error_code: string | null; error_message: string | null; result: Record<string, unknown> | null; published_at: string | null;
  publish_attempts: number; last_publish_error: string | null; reason: string | null; created_by_name: string | null; created_at: string;
  can_cancel: boolean; can_retry: boolean;
}
export interface JobAttempt {
  id: string; attempt_number: number; worker_identity: string; task_name: string; status: string; started_at: string;
  finished_at: string | null; duration_ms: number | null; error_code: string | null; error_message: string | null;
  system_actor_name: string | null;
}
export interface TaskSpec {
  job_type: string; task_name: string; queue: string; description: string; environments: string[]; scheduled_every_seconds: number | null;
  manually_triggerable: boolean; max_retries: number; soft_time_limit: number; time_limit: number; idempotency: string;
}
export interface WorkerHeartbeat { worker_identity: string; hostname: string; queues: string; started_at: string; last_heartbeat_at: string;
  stopped_at: string | null; alive: boolean }
export interface JobsStatus {
  environment: string; database: string; broker: 'NOT_CONFIGURED' | 'REACHABLE' | 'UNREACHABLE'; workers: WorkerHeartbeat[];
  worker_alive: boolean; counts: Record<string, number>; last_scheduled_at: string | null; note: string;
}

export function jobBadge(status: string): string {
  return ({ SUCCEEDED: 'ACTIVE', QUEUED: 'INFO', CLAIMED: 'WARNING', RUNNING: 'WARNING', RETRY_WAITING: 'WARNING', FAILED: 'FAILED',
    CANCELLED: 'ARCHIVED', ABANDONED: 'FAILED', RETRYABLE_ERROR: 'WARNING' } as Record<string, string>)[status] ?? 'INFO';
}

@Injectable({ providedIn: 'root' })
export class JobsApi {
  private readonly api = inject(ApiService);

  list = (status?: string, jobType?: string): Observable<Job[]> => this.api.get('/jobs', { status: status || null, job_type: jobType || null });
  get = (id: string): Observable<Job> => this.api.get(`/jobs/${id}`);
  attempts = (id: string): Observable<JobAttempt[]> => this.api.get(`/jobs/${id}/attempts`);
  registry = (): Observable<TaskSpec[]> => this.api.get('/jobs/registry');
  status = (): Observable<JobsStatus> => this.api.get('/jobs/status');
  cancel = (id: string, reason: string): Observable<Job> => this.api.post(`/jobs/${id}/cancel`, { reason });
  retry = (id: string, reason: string): Observable<Job> => this.api.post(`/jobs/${id}/retry`, { reason });
}
