import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map, tap } from 'rxjs';

import { API_BASE, ApiService } from '../core/api/api.service';
import { DocumentRef } from '../lab/lab.models';
import { Assignment, CorrectiveAction, Decision, Lineage, Package, PeriodVerification, Submission, VDocument, VFinding, VvbOrg } from './verification.models';

type Body = Record<string, unknown>;

/** Downloads through HttpClient (bearer token) and hands the file to the browser. */
function saveBlob(http: HttpClient, path: string, fileName: string): Observable<void> {
  return http.get(`${API_BASE}${path}`, { responseType: 'blob' }).pipe(
    tap((blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      a.rel = 'noopener';
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }),
    map(() => undefined),
  );
}

/** Project side (`/verification`): propose / withdraw / terminate assignments, submit the READY package, respond. Never decides. */
@Injectable({ providedIn: 'root' })
export class VerificationApi {
  private readonly api = inject(ApiService);
  private readonly http = inject(HttpClient);
  private readonly b = '/verification';

  vvbOrgs = (projectId: string): Observable<VvbOrg[]> => this.api.get(`${this.b}/projects/${projectId}/vvb-organizations`);
  period = (projectId: string, periodId: string): Observable<PeriodVerification> => this.api.get(`${this.b}/projects/${projectId}/periods/${periodId}`);
  propose = (projectId: string, body: Body): Observable<Assignment> => this.api.post(`${this.b}/projects/${projectId}/assignments`, body);
  withdraw = (id: string, reason: string): Observable<Assignment> => this.api.post(`${this.b}/assignments/${id}/withdraw`, { reason });
  terminate = (id: string, reason: string): Observable<Assignment> => this.api.post(`${this.b}/assignments/${id}/terminate`, { reason });
  submit = (id: string): Observable<Submission> => this.api.post(`${this.b}/assignments/${id}/submit`);
  findings = (submissionId: string): Observable<VFinding[]> => this.api.get(`${this.b}/submissions/${submissionId}/findings`);
  evidence = (submissionId: string, file: File): Observable<DocumentRef> => this.api.upload(`${this.b}/submissions/${submissionId}/evidence`, file, {});
  respond = (findingId: string, response: string, documentId?: string | null): Observable<VFinding> =>
    this.api.post(`${this.b}/findings/${findingId}/respond`, { response, document_id: documentId ?? null });
  respondCa = (id: string, response: string, documentId?: string | null): Observable<CorrectiveAction> =>
    this.api.post(`${this.b}/corrective-actions/${id}/respond`, { response, document_id: documentId ?? null });
  lineage = (decisionId: string): Observable<Lineage> => this.api.get(`${this.b}/decisions/${decisionId}/lineage`);
  report = (d: Decision): Observable<void> => saveBlob(this.http, `${this.b}/decisions/${d.id}/report`, `${d.decision_code}.pdf`);
}

/** VVB workspace (`/vvb`): an allow-list API scoped to the assignments of the caller's VVB organization. */
@Injectable({ providedIn: 'root' })
export class VvbApi {
  private readonly api = inject(ApiService);
  private readonly http = inject(HttpClient);
  private readonly b = '/vvb';

  assignments = (): Observable<Assignment[]> => this.api.get(`${this.b}/assignments`);
  assignment = (id: string): Observable<Assignment> => this.api.get(`${this.b}/assignments/${id}`);
  accept = (id: string, coi: string): Observable<Assignment> => this.api.post(`${this.b}/assignments/${id}/accept`, { coi_declaration: coi });
  decline = (id: string, reason: string): Observable<Assignment> => this.api.post(`${this.b}/assignments/${id}/decline`, { reason });
  terminate = (id: string, reason: string): Observable<Assignment> => this.api.post(`${this.b}/assignments/${id}/terminate`, { reason });
  package = (submissionId: string): Observable<Package> => this.api.get(`${this.b}/submissions/${submissionId}/package`);
  documents = (submissionId: string): Observable<VDocument[]> => this.api.get(`${this.b}/submissions/${submissionId}/documents`);
  download = (submissionId: string, d: VDocument): Observable<void> =>
    saveBlob(this.http, `${this.b}/submissions/${submissionId}/documents/${d.document_id}`, d.file_name ?? 'document');
  findings = (submissionId: string): Observable<VFinding[]> => this.api.get(`${this.b}/submissions/${submissionId}/findings`);
  raise = (submissionId: string, body: Body): Observable<VFinding> => this.api.post(`${this.b}/submissions/${submissionId}/findings`, body);
  close = (id: string, note: string): Observable<VFinding> => this.api.post(`${this.b}/findings/${id}/close`, { note });
  returnResponse = (id: string, reason: string): Observable<VFinding> => this.api.post(`${this.b}/findings/${id}/return`, { reason });
  reopen = (id: string, reason: string): Observable<VFinding> => this.api.post(`${this.b}/findings/${id}/reopen`, { reason });
  requestCa = (findingId: string, body: Body): Observable<CorrectiveAction> => this.api.post(`${this.b}/findings/${findingId}/corrective-actions`, body);
  acceptCa = (id: string, note: string): Observable<CorrectiveAction> => this.api.post(`${this.b}/corrective-actions/${id}/accept`, { note });
  rejectCa = (id: string, note: string): Observable<CorrectiveAction> => this.api.post(`${this.b}/corrective-actions/${id}/reject`, { note });
  cancelCa = (id: string, reason: string): Observable<CorrectiveAction> => this.api.post(`${this.b}/corrective-actions/${id}/cancel`, { reason });
  decide = (submissionId: string, file: File, fields: Record<string, string>): Observable<Decision> =>
    this.api.upload(`${this.b}/submissions/${submissionId}/decision`, file, fields);
  report = (d: Decision): Observable<void> => saveBlob(this.http, `${this.b}/decisions/${d.id}/report`, `${d.decision_code}.pdf`);
}
