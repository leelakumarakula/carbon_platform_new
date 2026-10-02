import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from '../core/api/api.service';
import { Change, Evaluation, Methodology, ProjectMethodologyView, Review, Rule, RuleKind, VersionDetail } from './methodology.models';

@Injectable({ providedIn: 'root' })
export class MethodologiesApi {
  private readonly api = inject(ApiService);
  private readonly base = '/methodologies';

  list = (environment?: string | null): Observable<Methodology[]> => this.api.get(this.base, { environment: environment ?? null });
  get = (id: string): Observable<Methodology> => this.api.get(`${this.base}/${id}`);
  create = (body: Record<string, unknown>): Observable<Methodology> => this.api.post(this.base, body);
  history = (id: string): Observable<Change[]> => this.api.get(`${this.base}/${id}/history`);
  createVersion = (id: string, body: Record<string, unknown>): Observable<VersionDetail> => this.api.post(`${this.base}/${id}/versions`, body);
  version = (vid: string): Observable<VersionDetail> => this.api.get(`${this.base}/versions/${vid}`);
  updateVersion = (vid: string, body: Record<string, unknown>): Observable<VersionDetail> => this.api.patch(`${this.base}/versions/${vid}`, body);
  addRule = (vid: string, kind: RuleKind, body: Record<string, unknown>): Observable<Rule> =>
    this.api.post(`${this.base}/versions/${vid}/rules/${kind}`, body);
  deleteRule = (vid: string, kind: RuleKind, rid: string, reason: string): Observable<void> =>
    this.api.delete(`${this.base}/versions/${vid}/rules/${kind}/${rid}`, undefined, { reason });
  versionAction = (vid: string, action: 'submit' | 'approve' | 'return' | 'retire' | 'withdraw', reason: string,
                   supersedes?: string | null): Observable<VersionDetail> =>
    this.api.post(`${this.base}/versions/${vid}/${action}`, { reason, supersedes_version_id: supersedes ?? null });

  projectView = (pid: string): Observable<ProjectMethodologyView> => this.api.get(`/projects/${pid}/methodology`);
  evaluate = (pid: string, declared: Record<string, unknown>): Observable<Evaluation> =>
    this.api.post(`/projects/${pid}/methodology/candidates`, { declared_facts: declared });
  evaluations = (pid: string): Observable<Evaluation[]> => this.api.get(`/projects/${pid}/methodology/evaluations`);
  review = (pid: string, body: { evaluation_result_id: string; recommendation: string; notes: string; evidence_acknowledged: boolean }):
    Observable<Review> => this.api.post(`/projects/${pid}/methodology/reviews`, body);
  confirm = (pid: string, resultId: string, notes: string): Observable<ProjectMethodologyView> =>
    this.api.post(`/projects/${pid}/methodology/confirm`, { evaluation_result_id: resultId, notes });
  unlock = (pid: string, reason: string): Observable<ProjectMethodologyView> => this.api.post(`/projects/${pid}/methodology/unlock`, { reason });
}
