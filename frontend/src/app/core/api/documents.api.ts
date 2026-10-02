import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map, tap } from 'rxjs';

import { DocumentInfo } from '../../farmer/farmer.models';
import { API_BASE, ApiService } from './api.service';

/** Document metadata, new versions and authenticated downloads (spec §32). */
@Injectable({ providedIn: 'root' })
export class DocumentsApi {
  private readonly api = inject(ApiService);
  private readonly http = inject(HttpClient);

  get = (id: string): Observable<DocumentInfo> => this.api.get(`/evidence/documents/${id}`);
  addVersion = (id: string, file: File): Observable<DocumentInfo> => this.api.upload(`/evidence/documents/${id}/versions`, file, {});

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
