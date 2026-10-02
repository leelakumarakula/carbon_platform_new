import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Page, PageQuery } from '../core/api/api.models';
import { ApiService } from '../core/api/api.service';
import { Farmer, FarmerInput, FarmerStatus, FarmerSummary } from './farmer.models';

export interface FarmerQuery extends PageQuery {
  search?: string | null;
  status?: FarmerStatus | null;
  organization_id?: string | null;
  environment?: 'LIVE' | 'DEMO' | null;
}

@Injectable({ providedIn: 'root' })
export class FarmersApi {
  private readonly api = inject(ApiService);
  private readonly base = '/farmers';

  list = (q: FarmerQuery): Observable<Page<FarmerSummary>> => this.api.get(this.base, { ...q });
  get = (id: string): Observable<Farmer> => this.api.get(`${this.base}/${id}`);
  me = (): Observable<Farmer> => this.api.get(`${this.base}/me`);
  create = (body: FarmerInput): Observable<Farmer> => this.api.post(this.base, body);
  update = (id: string, body: FarmerInput): Observable<Farmer> => this.api.patch(`${this.base}/${id}`, body);
  changeStatus = (id: string, status: string, reason: string): Observable<Farmer> =>
    this.api.post(`${this.base}/${id}/status`, { status, reason });
  submitKyc = (id: string, body: { id_type: string; id_number: string; document_id: string }): Observable<Farmer> =>
    this.api.post(`${this.base}/${id}/kyc`, body);
  decideKyc = (id: string, body: { decision: 'VERIFIED' | 'RETURNED'; notes: string; acknowledge_possible_duplicate: boolean }): Observable<Farmer> =>
    this.api.post(`${this.base}/${id}/kyc/decision`, body);
  addContact = (id: string, body: { contact_type: string; value: string; label?: string | null; is_primary: boolean }): Observable<Farmer> =>
    this.api.post(`${this.base}/${id}/contacts`, body);
  deactivateContact = (id: string, contactId: string, reason: string): Observable<Farmer> =>
    this.api.post(`${this.base}/${id}/contacts/${contactId}/deactivate`, { reason });
  grantConsent = (id: string, body: { consent_type: string; consent_text_version: string; language?: string | null;
    capture_method: string; document_id?: string | null }): Observable<Farmer> => this.api.post(`${this.base}/${id}/consents`, body);
  withdrawConsent = (id: string, consentId: string, reason: string): Observable<Farmer> =>
    this.api.post(`${this.base}/${id}/consents/${consentId}/withdraw`, { reason });
  createAgreement = (id: string, body: { agreement_type: string; template_version: string; terms_summary?: string | null;
    effective_from?: string | null; effective_to?: string | null }): Observable<Farmer> => this.api.post(`${this.base}/${id}/agreements`, body);
  signAgreement = (id: string, agreementId: string, body: { signed_document_id: string; signature_method: string }): Observable<Farmer> =>
    this.api.post(`${this.base}/${id}/agreements/${agreementId}/sign`, body);
  agreementStatus = (id: string, agreementId: string, status: string, reason: string): Observable<Farmer> =>
    this.api.post(`${this.base}/${id}/agreements/${agreementId}/status`, { status, reason });
  addBankAccount = (id: string, body: { account_holder_name: string; bank_name: string; branch_name?: string | null; routing_code: string;
    account_number: string; is_primary: boolean; proof_document_id?: string | null }): Observable<Farmer> =>
    this.api.post(`${this.base}/${id}/bank-accounts`, body);
  decideBankAccount = (id: string, accountId: string, decision: 'VERIFIED' | 'REJECTED', notes: string): Observable<Farmer> =>
    this.api.post(`${this.base}/${id}/bank-accounts/${accountId}/decision`, { decision, notes });
  deactivateBankAccount = (id: string, accountId: string, reason: string): Observable<Farmer> =>
    this.api.post(`${this.base}/${id}/bank-accounts/${accountId}/deactivate`, { reason });
  uploadDocument = (id: string, file: File, category: string, title: string): Observable<{ id: string }> =>
    this.api.upload(`${this.base}/${id}/documents`, file, { category, title });
  linkUser = (id: string, userId: string): Observable<Farmer> => this.api.post(`${this.base}/${id}/link-user`, { user_id: userId });
}
