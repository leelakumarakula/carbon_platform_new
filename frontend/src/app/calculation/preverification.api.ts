import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from '../core/api/api.service';
import { DocumentRef } from '../lab/lab.models';
import { CalcReport, Finding, Manifest, ReadinessReview, ReadinessState, ReportVerify } from './preverification.models';

type Body = Record<string, unknown>;

/** Phase 8A `/calculations` endpoints: findings, reports, internal readiness (no verification endpoint exists). */
@Injectable({ providedIn: 'root' })
export class PreverificationApi {
  private readonly api = inject(ApiService);
  private readonly b = '/calculations';

  findings = (projectId: string, runId?: string): Observable<Finding[]> =>
    this.api.get(`${this.b}/findings`, runId ? { project_id: projectId, run_id: runId } : { project_id: projectId });
  raise = (runId: string, body: Body): Observable<Finding> => this.api.post(`${this.b}/runs/${runId}/findings`, body);
  respond = (id: string, response: string): Observable<Finding> => this.api.post(`${this.b}/findings/${id}/respond`, { response });
  resolve = (id: string, note: string): Observable<Finding> => this.api.post(`${this.b}/findings/${id}/resolve`, { note });
  returnResponse = (id: string, reason: string): Observable<Finding> => this.api.post(`${this.b}/findings/${id}/return`, { reason });
  reopen = (id: string, reason: string): Observable<Finding> => this.api.post(`${this.b}/findings/${id}/reopen`, { reason });
  withdraw = (id: string, reason: string): Observable<Finding> => this.api.post(`${this.b}/findings/${id}/withdraw`, { reason });
  evidence = (runId: string, file: File): Observable<DocumentRef> => this.api.upload(`${this.b}/runs/${runId}/evidence`, file, {});

  reports = (runId: string): Observable<CalcReport[]> => this.api.get(`${this.b}/runs/${runId}/reports`);
  generate = (runId: string): Observable<CalcReport> => this.api.post(`${this.b}/runs/${runId}/reports`);
  verify = (id: string): Observable<ReportVerify> => this.api.get(`${this.b}/reports/${id}/verify`);

  readiness = (projectId: string, periodId: string): Observable<ReadinessState> =>
    this.api.get(`${this.b}/projects/${projectId}/verification-readiness`, { monitoring_period_id: periodId });
  createReadiness = (projectId: string, periodId: string): Observable<ReadinessReview> =>
    this.api.post(`${this.b}/projects/${projectId}/verification-readiness`, { monitoring_period_id: periodId });
  submitReadiness = (id: string): Observable<ReadinessReview> => this.api.post(`${this.b}/readiness/${id}/submit`);
  approveReadiness = (id: string, notes: string): Observable<ReadinessReview> => this.api.post(`${this.b}/readiness/${id}/approve`, { notes });
  rejectReadiness = (id: string, notes: string): Observable<ReadinessReview> => this.api.post(`${this.b}/readiness/${id}/reject`, { notes });
  withdrawReadiness = (id: string, reason: string): Observable<ReadinessReview> => this.api.post(`${this.b}/readiness/${id}/withdraw`, { reason });
  manifest = (id: string): Observable<Manifest> => this.api.get(`${this.b}/readiness/${id}/package`);
}
