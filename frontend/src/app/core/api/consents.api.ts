import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from './api.service';

/** Versioned consent definition (decision D3). Published by administrators; never edited after publication. */
export interface ConsentDefinition {
  id: string;
  consent_type: string;
  version: number;
  title: string;
  description: string | null;
  text_version: string | null;
  required_for_activation: boolean;
  status: 'ACTIVE' | 'RETIRED';
  created_at: string;
  retired_at: string | null;
}

export interface ConsentDefinitionIn {
  consent_type: string;
  title: string;
  description?: string | null;
  text_version?: string | null;
  required_for_activation: boolean;
}

@Injectable({ providedIn: 'root' })
export class ConsentsApi {
  private readonly api = inject(ApiService);
  active = (): Observable<ConsentDefinition[]> => this.api.get('/consent-definitions');
  all = (): Observable<ConsentDefinition[]> => this.api.get('/admin/consent-definitions');
  publish = (body: ConsentDefinitionIn): Observable<ConsentDefinition> => this.api.post('/admin/consent-definitions', body);
  retire = (id: string, reason: string): Observable<ConsentDefinition> => this.api.post(`/admin/consent-definitions/${id}/retire`, { reason });
}
