import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from '../core/api/api.service';
import { CalcCompare, CalcInputs, CalcProject, CalcLineage, CalcOutputs, CalcQaView, CalcRun, Readiness } from './calculation.models';

/** `/calculations` — no method sends a calculated value; the server computes everything from frozen inputs. */
@Injectable({ providedIn: 'root' })
export class CalculationApi {
  private readonly api = inject(ApiService);
  private readonly b = '/calculations';

  projects = (): Observable<CalcProject[]> => this.api.get(`${this.b}/projects`);
  readiness = (projectId: string, periodId: string): Observable<Readiness> =>
    this.api.get(`${this.b}/projects/${projectId}/readiness`, { monitoring_period_id: periodId });
  runs = (projectId: string, periodId?: string): Observable<CalcRun[]> =>
    this.api.get(`${this.b}/runs`, periodId ? { project_id: projectId, monitoring_period_id: periodId } : { project_id: projectId });
  run = (id: string): Observable<CalcRun> => this.api.get(`${this.b}/runs/${id}`);
  create = (projectId: string, periodId: string): Observable<CalcRun> =>
    this.api.post(`${this.b}/runs`, { project_id: projectId, monitoring_period_id: periodId });
  freeze = (id: string): Observable<CalcRun> => this.api.post(`${this.b}/runs/${id}/freeze`);
  execute = (id: string): Observable<CalcRun> => this.api.post(`${this.b}/runs/${id}/execute`);
  submit = (id: string): Observable<CalcRun> => this.api.post(`${this.b}/runs/${id}/submit`);
  cancel = (id: string, reason: string): Observable<CalcRun> => this.api.post(`${this.b}/runs/${id}/cancel`, { reason });
  approve = (id: string, reason: string): Observable<CalcRun> => this.api.post(`${this.b}/runs/${id}/approve`, { reason });
  reject = (id: string, reason: string): Observable<CalcRun> => this.api.post(`${this.b}/runs/${id}/reject`, { reason });
  recalculate = (id: string, reason: string): Observable<CalcRun> => this.api.post(`${this.b}/runs/${id}/recalculate`, { reason });
  inputs = (id: string): Observable<CalcInputs> => this.api.get(`${this.b}/runs/${id}/inputs`);
  outputs = (id: string): Observable<CalcOutputs> => this.api.get(`${this.b}/runs/${id}/outputs`);
  lineage = (id: string): Observable<CalcLineage> => this.api.get(`${this.b}/runs/${id}/lineage`);
  compare = (id: string, other: string): Observable<CalcCompare> => this.api.get(`${this.b}/runs/${id}/compare/${other}`);
  qa = (id: string): Observable<CalcQaView> => this.api.get(`${this.b}/qa/${id}`);
  startQa = (id: string): Observable<CalcQaView> => this.api.post(`${this.b}/qa/${id}/start`);
  completeQa = (id: string, result: 'PASS' | 'FAIL', notes: string): Observable<CalcQaView> =>
    this.api.post(`${this.b}/qa/${id}/complete`, { result, notes });
}
