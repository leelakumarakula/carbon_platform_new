import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from '../core/api/api.service';
import { DocumentRef } from '../lab/lab.models';
import { Entry, Holdings, Inventory, Opening, Position, Recipient, Reservation, Retirement, Reversal, Transfer } from './ledger.models';

type Body = Record<string, unknown>;

/** Phase 9B ledger endpoints (`/credits`). Bodies carry movement quantities only — never a balance. */
@Injectable({ providedIn: 'root' })
export class LedgerApi {
  private readonly api = inject(ApiService);
  private readonly b = '/credits';

  inventory = (projectId?: string): Observable<Inventory> => this.api.get(`${this.b}/inventory`, { project_id: projectId });
  positions = (batchId: string, includeConsumed = false): Observable<Position[]> =>
    this.api.get(`${this.b}/batches/${batchId}/positions`, { include_consumed: includeConsumed || null });
  open = (batchId: string): Observable<Opening> => this.api.post(`${this.b}/batches/${batchId}/open`);
  confirmOpening = (id: string): Observable<Opening> => this.api.post(`${this.b}/openings/${id}/confirm`);
  cancelOpening = (id: string, reason: string): Observable<Opening> => this.api.post(`${this.b}/openings/${id}/cancel`, { reason });
  reservations = (batchId?: string): Observable<Reservation[]> => this.api.get(`${this.b}/reservations`, { batch_id: batchId });
  reserve = (body: Body, key?: string): Observable<Reservation> => this.api.post(`${this.b}/reservations`, body, key);
  release = (id: string, reason: string): Observable<Reservation> => this.api.post(`${this.b}/reservations/${id}/release`, { reason });
  transfers = (batchId?: string): Observable<Transfer[]> => this.api.get(`${this.b}/transfers`, { batch_id: batchId });
  requestTransfer = (body: Body, key?: string): Observable<Transfer> => this.api.post(`${this.b}/transfers`, body, key);
  transferDoc = (id: string, file: File): Observable<DocumentRef> => this.api.upload(`${this.b}/transfers/${id}/documents`, file, {});
  completeTransfer = (id: string, body: Body, key?: string): Observable<Transfer> =>
    this.api.post(`${this.b}/transfers/${id}/complete`, body, key);
  cancelTransfer = (id: string, reason: string): Observable<Transfer> => this.api.post(`${this.b}/transfers/${id}/cancel`, { reason });
  rejectTransfer = (id: string, reason: string): Observable<Transfer> => this.api.post(`${this.b}/transfers/${id}/reject`, { reason });
  retirements = (batchId?: string): Observable<Retirement[]> => this.api.get(`${this.b}/retirements`, { batch_id: batchId });
  requestRetirement = (body: Body, key?: string): Observable<Retirement> => this.api.post(`${this.b}/retirements`, body, key);
  retirementDoc = (id: string, file: File): Observable<DocumentRef> => this.api.upload(`${this.b}/retirements/${id}/documents`, file, {});
  retire = (id: string, body: Body, key?: string): Observable<Retirement> => this.api.post(`${this.b}/retirements/${id}/retire`, body, key);
  cancelRetirement = (id: string, reason: string): Observable<Retirement> => this.api.post(`${this.b}/retirements/${id}/cancel`, { reason });
  rejectRetirement = (id: string, reason: string): Observable<Retirement> => this.api.post(`${this.b}/retirements/${id}/reject`, { reason });
  retirementLineage = (id: string): Observable<unknown> => this.api.get(`${this.b}/retirements/${id}/lineage`);
  entry = (id: string): Observable<Entry> => this.api.get(`${this.b}/entries/${id}`);
  reverse = (entryId: string, reason: string): Observable<Reversal> => this.api.post(`${this.b}/entries/${entryId}/reverse`, { reason });
  reversals = (): Observable<Reversal[]> => this.api.get(`${this.b}/reversals`);
  applyReversal = (id: string, note: string): Observable<Reversal> => this.api.post(`${this.b}/reversals/${id}/apply`, { note });
  rejectReversal = (id: string, note: string): Observable<Reversal> => this.api.post(`${this.b}/reversals/${id}/reject`, { note });
  holdings = (): Observable<Holdings> => this.api.get(`${this.b}/holdings`);
  completeOrderTransfer = (id: string, body: Body, key?: string): Observable<unknown> =>
    this.api.post(`/orders/transfers/${id}/complete`, body, key);
  rejectOrderTransfer = (id: string, reason: string): Observable<unknown> => this.api.post(`/orders/transfers/${id}/reject`, { reason });
  recipients = (environment: string): Observable<Recipient[]> => this.api.get(`${this.b}/recipients`, { environment });
}

/** A fresh Idempotency-Key for one user submission (kept across retries of that submission, renewed after success). */
export function newKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `k-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
