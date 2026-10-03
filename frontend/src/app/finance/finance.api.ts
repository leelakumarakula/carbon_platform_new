import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from '../core/api/api.service';
import { DocumentRef } from '../lab/lab.models';
import {
  Adjustment, Allocation, Cost, FinanceProject, MyPayouts, Payout, Reconciliation, Revenue, Settlement, ShareVersion, Summary, Verify,
} from './finance.models';

type Body = Record<string, unknown>;

/** Phase 11 endpoints (`/revenue`, `/revenue-share`, `/allocations`, `/costs`, `/settlements`, `/payouts`). No request carries a revenue,
 *  entitlement or payout amount: those are calculated by the server. Every state change sends an Idempotency-Key when given one. */
@Injectable({ providedIn: 'root' })
export class FinanceApi {
  private readonly api = inject(ApiService);

  projects = (): Observable<FinanceProject[]> => this.api.get('/revenue/projects');
  summary = (projectId?: string): Observable<Summary> => this.api.get('/revenue/summary', { project_id: projectId ?? null });
  revenue = (projectId: string): Observable<Revenue[]> => this.api.get('/revenue', { project_id: projectId });

  shareVersions = (projectId: string): Observable<ShareVersion[]> => this.api.get('/revenue-share', { project_id: projectId });
  createShareVersion = (body: Body, key?: string): Observable<ShareVersion> => this.api.post('/revenue-share', body, key);
  shareAction = (id: string, action: 'submit' | 'approve' | 'return', body: Body = {}, key?: string): Observable<ShareVersion> =>
    this.api.post(`/revenue-share/${id}/${action}`, body, key);

  allocations = (projectId: string): Observable<Allocation[]> => this.api.get('/allocations', { project_id: projectId });
  createAllocation = (body: Body, key?: string): Observable<Allocation> => this.api.post('/allocations', body, key);
  allocationAction = (id: string, action: 'submit' | 'approve' | 'return', body: Body = {}, key?: string): Observable<Allocation> =>
    this.api.post(`/allocations/${id}/${action}`, body, key);

  costs = (projectId: string): Observable<Cost[]> => this.api.get('/costs', { project_id: projectId });
  createCost = (body: Body, key?: string): Observable<Cost> => this.api.post('/costs', body, key);
  costDocument = (id: string, file: File): Observable<DocumentRef> => this.api.upload(`/costs/${id}/documents`, file, {});
  approveCost = (id: string, key?: string): Observable<Cost> => this.api.post(`/costs/${id}/approve`, {}, key);
  rejectCost = (id: string, reason: string, key?: string): Observable<Cost> => this.api.post(`/costs/${id}/reject`, { reason }, key);

  settlements = (projectId?: string): Observable<Settlement[]> => this.api.get('/settlements', { project_id: projectId ?? null });
  settlement = (id: string): Observable<Settlement> => this.api.get(`/settlements/${id}`);
  createSettlement = (body: Body, key?: string): Observable<Settlement> => this.api.post('/settlements', body, key);
  calculate = (id: string, key?: string): Observable<Settlement> => this.api.post(`/settlements/${id}/calculate`, {}, key);
  verify = (id: string): Observable<Verify> => this.api.get(`/settlements/${id}/verify`);
  settlementAction = (id: string, action: 'submit' | 'approve' | 'reject' | 'cancel', body: Body = {}, key?: string): Observable<Settlement> =>
    this.api.post(`/settlements/${id}/${action}`, body, key);

  payouts = (runId?: string): Observable<Payout[]> => this.api.get('/payouts', { settlement_run_id: runId ?? null });
  createPayouts = (runId: string): Observable<Payout[]> => this.api.post(`/payouts/from-settlement/${runId}`, {});
  payoutAction = (id: string, action: 'submit' | 'approve' | 'reject' | 'cancel' | 'release-hold' | 'reissue' | 'initiate' | 'fail',
                  body: Body = {}, key?: string): Observable<Payout> => this.api.post(`/payouts/${id}/${action}`, body, key);
  payoutDocument = (id: string, file: File, category: 'PAYOUT_EVIDENCE' | 'RECONCILIATION_EVIDENCE'): Observable<DocumentRef> =>
    this.api.upload(`/payouts/${id}/documents`, file, { category });
  confirmPaid = (id: string, body: Body, key?: string): Observable<Payout> => this.api.post(`/payouts/${id}/confirm-paid`, body, key);
  reconcile = (id: string, body: Body, key?: string): Observable<Reconciliation> => this.api.post(`/payouts/${id}/reconcile`, body, key);
  adjustments = (): Observable<Adjustment[]> => this.api.get('/payouts/adjustments');
  closeAdjustment = (id: string, resolution: string, key?: string): Observable<Adjustment> =>
    this.api.post(`/payouts/adjustments/${id}/close`, { resolution }, key);
  myPayouts = (): Observable<MyPayouts> => this.api.get('/payouts/me');
}
