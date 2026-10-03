import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map, tap } from 'rxjs';

import { DocumentInfo } from '../../farmer/farmer.models';
import { API_BASE, ApiService } from './api.service';

/** One row of the append-only antivirus scan history (Phase 12B). */
export interface DocumentScan {
  id: string; document_id: string; document_version_id: string; checksum_sha256: string;
  result: 'CLEAN' | 'INFECTED' | 'NOT_SCANNED' | 'ERROR'; provider: string; engine_version: string | null; threat_name: string | null;
  error_code: string | null; detail: string | null; trigger_type: 'UPLOAD' | 'RESCAN' | 'RELEASE'; background_job_id: string | null;
  actor_id: string | null; duration_ms: number | null; scanned_at: string;
}
export interface SecurityDocument extends DocumentInfo { organization_id: string; latest_scan: DocumentScan | null }

/** Document metadata, new versions and authenticated downloads (spec §32). */
@Injectable({ providedIn: 'root' })
export class DocumentsApi {
  private readonly api = inject(ApiService);
  private readonly http = inject(HttpClient);

  get = (id: string): Observable<DocumentInfo> => this.api.get(`/evidence/documents/${id}`);
  addVersion = (id: string, file: File): Observable<DocumentInfo> => this.api.upload(`/evidence/documents/${id}/versions`, file, {});

  // Phase 12B security operations (security.read / security.manage). None of them returns file content.
  quarantined = (): Observable<SecurityDocument[]> => this.api.get('/evidence/documents/quarantined');
  scans = (id: string): Observable<DocumentScan[]> => this.api.get(`/evidence/documents/${id}/scans`);
  quarantine = (id: string, reason: string): Observable<SecurityDocument> => this.api.post(`/evidence/documents/${id}/quarantine`, { reason });
  rescan = (id: string): Observable<{ job_id: string }> => this.api.post(`/evidence/documents/${id}/rescan`);
  release = (id: string, reason: string): Observable<SecurityDocument> => this.api.post(`/evidence/documents/${id}/release`, { reason });

  /** Downloads through HttpClient (so the bearer token is sent) and hands the file to the browser. */
  download(id: string, fileName: string, version?: number): Observable<void> {
    const params = version ? new HttpParams().set('version', version) : undefined;
    return this.http.get(`${API_BASE}/evidence/documents/${id}/download`, { params, responseType: 'blob' }).pipe(
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
}
