import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from '../core/api/api.service';
import { DocumentRef } from '../lab/lab.models';
import { BuyerProfile, BuyerProfileView, LineageStep, Listing, Listings, Order, Orders, Payment, Refund } from './marketplace.models';

type Body = Record<string, unknown>;

/** Phase 10 endpoints (`/marketplace`, `/orders`, `/payments`, `/refunds`). Every POST that creates or changes state sends an
 *  Idempotency-Key when the caller provides one; bodies never carry a balance, fee or tax. */
@Injectable({ providedIn: 'root' })
export class MarketplaceApi {
  private readonly api = inject(ApiService);

  // buyer profile & KYC
  profile = (): Observable<BuyerProfileView> => this.api.get('/marketplace/buyer-profile');
  saveProfile = (body: Body, key?: string): Observable<BuyerProfile> => this.api.post('/marketplace/buyer-profile', body, key);
  kycDocument = (file: File): Observable<DocumentRef> => this.api.upload('/marketplace/buyer-profile/documents', file, {});
  submitKyc = (key?: string): Observable<BuyerProfile> => this.api.post('/marketplace/buyer-profile/submit-kyc', {}, key);
  kycQueue = (status?: string): Observable<BuyerProfile[]> => this.api.get('/marketplace/buyer-profiles', { status });
  review = (id: string, action: 'verify' | 'return' | 'suspend', body: Body, key?: string): Observable<BuyerProfile> =>
    this.api.post(`/marketplace/buyer-profiles/${id}/${action}`, body, key);

  // listings
  listings = (mine = false, status?: string): Observable<Listings> => this.api.get('/marketplace/listings', { mine: mine || null, status });
  listing = (id: string): Observable<Listing> => this.api.get(`/marketplace/listings/${id}`);
  createListing = (body: Body, key?: string): Observable<Listing> => this.api.post('/marketplace/listings', body, key);
  listingDocument = (id: string, file: File): Observable<DocumentRef> => this.api.upload(`/marketplace/listings/${id}/documents`, file, {});
  listingAction = (id: string, action: 'submit' | 'approve' | 'pause' | 'resume' | 'close', body: Body = {}, key?: string): Observable<Listing> =>
    this.api.post(`/marketplace/listings/${id}/${action}`, body, key);

  // orders
  orders = (status?: string): Observable<Orders> => this.api.get('/orders', { status });
  order = (id: string): Observable<Order> => this.api.get(`/orders/${id}`);
  place = (body: Body, key?: string): Observable<Order> => this.api.post('/orders', body, key);
  cancel = (id: string, reason: string, key?: string): Observable<Order> => this.api.post(`/orders/${id}/cancel`, { reason }, key);
  orderDocument = (id: string, file: File): Observable<DocumentRef> => this.api.upload(`/orders/${id}/documents`, file, {});
  retry = (id: string, reason: string, key?: string): Observable<Order> => this.api.post(`/orders/${id}/retry-transfer`, { reason }, key);
  confirmation = (id: string): Observable<DocumentRef> => this.api.post(`/orders/${id}/confirmation`);
  lineage = (id: string): Observable<{ chain: LineageStep[] }> => this.api.get(`/orders/${id}/lineage`);
  completeTransfer = (transferId: string, body: Body = {}, key?: string): Observable<Order> =>
    this.api.post(`/orders/transfers/${transferId}/complete`, body, key);
  rejectTransfer = (transferId: string, reason: string, key?: string): Observable<Order> =>
    this.api.post(`/orders/transfers/${transferId}/reject`, { reason }, key);

  // payments & refunds
  payments = (status?: string): Observable<Payment[]> => this.api.get('/payments', { status });
  recordPayment = (body: Body, key?: string): Observable<Payment> => this.api.post('/payments', body, key);
  confirmPayment = (id: string, key?: string): Observable<Payment> => this.api.post(`/payments/${id}/confirm`, {}, key);
  rejectPayment = (id: string, reason: string, key?: string): Observable<Payment> => this.api.post(`/payments/${id}/reject`, { reason }, key);
  requestRefund = (paymentId: string, reason: string, key?: string): Observable<Refund> =>
    this.api.post(`/payments/${paymentId}/refunds`, { reason }, key);
  refunds = (): Observable<Refund[]> => this.api.get('/refunds');
  refundDocument = (id: string, file: File): Observable<DocumentRef> => this.api.upload(`/refunds/${id}/documents`, file, {});
  approveRefund = (id: string, key?: string): Observable<Refund> => this.api.post(`/refunds/${id}/approve`, {}, key);
  completeRefund = (id: string, body: Body, key?: string): Observable<Refund> => this.api.post(`/refunds/${id}/complete`, body, key);
  rejectRefund = (id: string, reason: string, key?: string): Observable<Refund> => this.api.post(`/refunds/${id}/reject`, { reason }, key);
}
