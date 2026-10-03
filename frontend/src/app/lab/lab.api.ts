import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from '../core/api/api.service';
import {
  CustodyEvent,
  DocumentRef,
  Engagement,
  EngagementLabView,
  LabDashboardCounts,
  LabResult,
  LaboratoryOrg,
  Lineage,
  QaLabView,
  ResultLabView,
  RuleRef,
  Sample,
  SampleDetail,
  SampleLabView,
  Shipment,
  ShipmentLabView,
  TestLabView,
} from './lab.models';

type Body = Record<string, unknown>;

/** Project-side laboratory API (`/lab`). */
@Injectable({ providedIn: 'root' })
export class LabApi {
  private readonly api = inject(ApiService);
  private readonly b = '/lab';

  laboratories = (pid: string): Observable<LaboratoryOrg[]> => this.api.get(`${this.b}/projects/${pid}/laboratories`);
  laboratoryRules = (pid: string): Observable<RuleRef[]> => this.api.get(`${this.b}/projects/${pid}/laboratory-rules`);
  engagements = (pid: string): Observable<Engagement[]> => this.api.get(`${this.b}/engagements`, { project_id: pid });
  propose = (body: Body): Observable<Engagement> => this.api.post(`${this.b}/engagements`, body);
  endEngagement = (id: string, reason: string): Observable<Engagement> => this.api.post(`${this.b}/engagements/${id}/end`, { reason });

  samples = (q: { project_id?: string; monitoring_period_id?: string; field_collection_id?: string }): Observable<Sample[]> =>
    this.api.get(`${this.b}/samples`, q);
  sample = (id: string): Observable<SampleDetail> => this.api.get(`${this.b}/samples/${id}`);
  register = (body: Body): Observable<Sample> => this.api.post(`${this.b}/samples`, body);
  seal = (id: string, sealNumber: string): Observable<Sample> => this.api.post(`${this.b}/samples/${id}/seal`, { seal_number: sealNumber });
  voidSample = (id: string, reason: string): Observable<Sample> => this.api.post(`${this.b}/samples/${id}/void`, { reason });
  custody = (id: string, body: Body): Observable<CustodyEvent[]> => this.api.post(`${this.b}/samples/${id}/custody`, body);

  shipments = (pid: string): Observable<Shipment[]> => this.api.get(`${this.b}/shipments`, { project_id: pid });
  createShipment = (body: Body): Observable<Shipment> => this.api.post(`${this.b}/shipments`, body);
  addItems = (id: string, sampleIds: string[]): Observable<Shipment> => this.api.post(`${this.b}/shipments/${id}/items`, { sample_ids: sampleIds });
  removeItem = (id: string, sampleId: string): Observable<Shipment> => this.api.post(`${this.b}/shipments/${id}/items/${sampleId}/remove`);
  dispatch = (id: string): Observable<Shipment> => this.api.post(`${this.b}/shipments/${id}/dispatch`, {});
  cancelShipment = (id: string, reason: string): Observable<Shipment> => this.api.post(`${this.b}/shipments/${id}/cancel`, { reason });
  shipmentDocument = (id: string, file: File): Observable<DocumentRef> => this.api.upload(`${this.b}/shipments/${id}/documents`, file, {});

  results = (pid: string, status = 'APPROVED'): Observable<LabResult[]> => this.api.get(`${this.b}/results`, { project_id: pid, status });
  lineage = (id: string): Observable<Lineage> => this.api.get(`${this.b}/results/${id}/lineage`);
}

/** Laboratory-facing API (`/laboratory`) — allow-listed views only. */
@Injectable({ providedIn: 'root' })
export class LaboratoryApi {
  private readonly api = inject(ApiService);
  private readonly b = '/laboratory';

  dashboard = (): Observable<LabDashboardCounts> => this.api.get(`${this.b}/dashboard`);
  engagements = (): Observable<EngagementLabView[]> => this.api.get(`${this.b}/engagements`);
  accept = (id: string): Observable<EngagementLabView> => this.api.post(`${this.b}/engagements/${id}/accept`);
  end = (id: string, reason: string): Observable<EngagementLabView> => this.api.post(`${this.b}/engagements/${id}/end`, { reason });
  inbox = (): Observable<ShipmentLabView[]> => this.api.get(`${this.b}/shipments`);
  receive = (id: string, items: Body[]): Observable<ShipmentLabView> => this.api.post(`${this.b}/shipments/${id}/receive`, { items });
  samples = (): Observable<SampleLabView[]> => this.api.get(`${this.b}/samples`);
  sample = (id: string): Observable<SampleLabView> => this.api.get(`${this.b}/samples/${id}`);
  accession = (id: string, n: string): Observable<SampleLabView> => this.api.post(`${this.b}/samples/${id}/accession`, { accession_number: n });
  tests = (): Observable<TestLabView[]> => this.api.get(`${this.b}/tests`);
  test = (id: string): Observable<TestLabView> => this.api.get(`${this.b}/tests/${id}`);
  start = (id: string, method: string | null): Observable<TestLabView> => this.api.post(`${this.b}/tests/${id}/start`, { method_reported: method });
  createResult = (testId: string, body: Body): Observable<ResultLabView> => this.api.post(`${this.b}/tests/${testId}/results`, body);
  report = (id: string, file: File): Observable<ResultLabView> => this.api.upload(`${this.b}/results/${id}/report`, file, {});
  submit = (id: string): Observable<ResultLabView> => this.api.post(`${this.b}/results/${id}/submit`);
  withdraw = (id: string, reason: string): Observable<ResultLabView> => this.api.post(`${this.b}/results/${id}/withdraw`, { reason });
  retest = (id: string, reason: string): Observable<TestLabView> => this.api.post(`${this.b}/results/${id}/retest`, { reason });
  qaQueue = (): Observable<ResultLabView[]> => this.api.get(`${this.b}/qa`);
  qa = (id: string): Observable<QaLabView> => this.api.get(`${this.b}/qa/${id}`);
  startQa = (id: string): Observable<QaLabView> => this.api.post(`${this.b}/qa/${id}/start`);
  decide = (id: string, body: { decision: string; notes: string; acknowledge_configuration: boolean }): Observable<QaLabView> =>
    this.api.post(`${this.b}/qa/${id}/decision`, body);
}
