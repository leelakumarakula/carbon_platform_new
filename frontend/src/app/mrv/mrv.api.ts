import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from '../core/api/api.service';
import {
  Collector,
  Dataset,
  Design,
  Evidence,
  FieldCollection,
  MonitoringRecord,
  MrvHistoryEntry,
  MrvProjectSummary,
  Period,
  Plan,
  QaView,
  Relocation,
  Requirements,
  SamplingPoint,
  Stratum,
} from './mrv.models';

type Body = Record<string, unknown>;

@Injectable({ providedIn: 'root' })
export class MrvApi {
  private readonly api = inject(ApiService);
  private readonly b = '/mrv';

  projects = (): Observable<MrvProjectSummary[]> => this.api.get(`${this.b}/projects`);
  requirements = (pid: string): Observable<Requirements> => this.api.get(`${this.b}/projects/${pid}/requirements`);
  history = (pid: string): Observable<MrvHistoryEntry[]> => this.api.get(`${this.b}/projects/${pid}/history`);
  collectors = (pid: string): Observable<Collector[]> => this.api.get(`${this.b}/projects/${pid}/collectors`);

  plans = (pid: string): Observable<Plan[]> => this.api.get(`${this.b}/plans`, { project_id: pid });
  plan = (id: string): Observable<Plan> => this.api.get(`${this.b}/plans/${id}`);
  createPlan = (body: Body): Observable<Plan> => this.api.post(`${this.b}/plans`, body);
  updatePlan = (id: string, body: Body): Observable<Plan> => this.api.patch(`${this.b}/plans/${id}`, body);
  addMeasurement = (id: string, body: Body): Observable<Plan> => this.api.post(`${this.b}/plans/${id}/measurements`, body);
  planAction = (id: string, action: 'submit' | 'approve' | 'return' | 'withdraw', reason: string, acknowledge = false): Observable<Plan> =>
    this.api.post(`${this.b}/plans/${id}/${action}`, { reason, acknowledge_configuration_gaps: acknowledge });

  periods = (pid: string): Observable<Period[]> => this.api.get(`${this.b}/monitoring-periods`, { project_id: pid });
  period = (id: string): Observable<Period> => this.api.get(`${this.b}/monitoring-periods/${id}`);
  createPeriod = (body: Body): Observable<Period> => this.api.post(`${this.b}/monitoring-periods`, body);
  periodAction = (id: string, action: string, reason: string): Observable<Period> =>
    this.api.post(`${this.b}/monitoring-periods/${id}/${action}`, { reason });

  strata = (pid: string, history = false): Observable<Stratum[]> =>
    this.api.get(`${this.b}/projects/${pid}/strata`, { include_history: history || null });
  createStratum = (pid: string, body: Body): Observable<Stratum> => this.api.post(`${this.b}/projects/${pid}/strata`, body);
  updateStratum = (id: string, body: Body): Observable<Stratum> => this.api.patch(`${this.b}/strata/${id}`, body);
  approveStratum = (id: string, reason: string): Observable<Stratum> => this.api.post(`${this.b}/strata/${id}/approve`, { reason });

  designs = (pid: string, periodId?: string | null): Observable<Design[]> =>
    this.api.get(`${this.b}/sampling-designs`, { project_id: pid, monitoring_period_id: periodId ?? null });
  createDesign = (body: Body): Observable<Design> => this.api.post(`${this.b}/sampling-designs`, body);
  approveDesign = (id: string, vid: string, reason: string): Observable<unknown> =>
    this.api.post(`${this.b}/sampling-designs/${id}/versions/${vid}/approve`, { reason });
  generatePoints = (id: string): Observable<{ created: number; per_stratum: Record<string, number>; points: SamplingPoint[] }> =>
    this.api.post(`${this.b}/sampling-designs/${id}/generate-points`);

  points = (q: { project_id?: string; monitoring_period_id?: string; mine?: boolean }): Observable<SamplingPoint[]> =>
    this.api.get(`${this.b}/sampling-points`, q);
  point = (id: string): Observable<SamplingPoint> => this.api.get(`${this.b}/sampling-points/${id}`);
  bulkAssign = (body: { point_ids: string[]; collector_id: string; planned_date?: string | null; instructions?: string | null }):
    Observable<SamplingPoint[]> => this.api.post(`${this.b}/sampling-points/assign`, body);
  skip = (id: string, reason: string): Observable<SamplingPoint> => this.api.post(`${this.b}/sampling-points/${id}/skip`, { reason });
  relocations = (id: string): Observable<Relocation[]> => this.api.get(`${this.b}/sampling-points/${id}/relocations`);
  requestRelocation = (id: string, body: { latitude: number; longitude: number; reason: string }): Observable<Relocation> =>
    this.api.post(`${this.b}/sampling-points/${id}/relocations`, body);
  decideRelocation = (rid: string, decision: 'APPROVED' | 'REJECTED', notes: string): Observable<Relocation> =>
    this.api.post(`${this.b}/relocations/${rid}/decision`, { decision, notes });

  collections = (q: { project_id?: string; monitoring_period_id?: string; mine?: boolean }): Observable<FieldCollection[]> =>
    this.api.get(`${this.b}/field-collections`, q);
  collection = (id: string): Observable<FieldCollection> => this.api.get(`${this.b}/field-collections/${id}`);
  startCollection = (pointId: string): Observable<FieldCollection> => this.api.post(`${this.b}/field-collections`, { sampling_point_id: pointId });
  updateCollection = (id: string, body: Body): Observable<FieldCollection> => this.api.patch(`${this.b}/field-collections/${id}`, body);
  submitCollection = (id: string): Observable<FieldCollection> => this.api.post(`${this.b}/field-collections/${id}/submit`);
  reviewCollection = (id: string, decision: 'ACCEPTED' | 'RETURNED', notes: string): Observable<FieldCollection> =>
    this.api.post(`${this.b}/field-collections/${id}/review`, { decision, notes });

  records = (periodId: string, history = false): Observable<MonitoringRecord[]> =>
    this.api.get(`${this.b}/monitoring-records`, { monitoring_period_id: periodId, include_history: history || null });
  addRecord = (body: Body): Observable<MonitoringRecord> => this.api.post(`${this.b}/monitoring-records`, body);
  amendRecord = (recordId: string, body: Body): Observable<MonitoringRecord> => this.api.post(`${this.b}/monitoring-records/${recordId}/amend`, body);

  evidence = (q: { project_id: string; monitoring_period_id?: string | null; entity_type?: string; entity_id?: string }): Observable<Evidence[]> =>
    this.api.get(`${this.b}/evidence`, q);
  addEvidence = (file: File | null, fields: Record<string, string>): Observable<Evidence> => {
    if (file) return this.api.upload(`${this.b}/evidence`, file, fields);
    const form = new FormData();
    for (const [k, v] of Object.entries(fields)) form.append(k, v);
    return this.api.post(`${this.b}/evidence`, form);
  };

  datasets = (pid: string): Observable<Dataset[]> => this.api.get(`${this.b}/datasets`, { project_id: pid });
  dataset = (id: string): Observable<Dataset> => this.api.get(`${this.b}/datasets/${id}`);
  createDataset = (periodId: string, notes?: string | null): Observable<Dataset> =>
    this.api.post(`${this.b}/datasets`, { monitoring_period_id: periodId, notes: notes ?? null });
  datasetAction = (id: string, action: 'submit' | 'approve' | 'reject', reason: string): Observable<Dataset> =>
    this.api.post(`${this.b}/datasets/${id}/${action}`, { reason });
  snapshot = (id: string): Observable<{ snapshot_sha256: string; snapshot: Record<string, unknown> }> =>
    this.api.get(`${this.b}/datasets/${id}/snapshot`);
  qa = (id: string): Observable<QaView> => this.api.get(`${this.b}/qa/${id}`);
  startQa = (id: string): Observable<unknown> => this.api.post(`${this.b}/qa/${id}/start`);
  completeQa = (id: string, result: 'PASS' | 'FAIL' | 'REQUIRES_CORRECTION', notes: string): Observable<unknown> =>
    this.api.post(`${this.b}/qa/${id}/complete`, { result, notes });
}
