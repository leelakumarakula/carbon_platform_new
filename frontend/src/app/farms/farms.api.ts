import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Page, PageQuery } from '../core/api/api.models';
import { ApiService } from '../core/api/api.service';
import {
  Boundary,
  Evidence,
  Farm,
  FarmStatus,
  FarmSummary,
  GeoGeometry,
  GeometryReport,
  HistoryKind,
  HistoryRecord,
  Overlap,
  Ownership,
} from './farm.models';

export interface FarmQuery extends PageQuery {
  search?: string | null;
  status?: FarmStatus | null;
  farmer_id?: string | null;
  organization_id?: string | null;
  environment?: 'LIVE' | 'DEMO' | null;
  has_open_overlaps?: boolean | null;
}

export interface BoundarySaved {
  farm: Farm;
  warnings: string[];
}

@Injectable({ providedIn: 'root' })
export class FarmsApi {
  private readonly api = inject(ApiService);
  private readonly base = '/farms';

  list = (q: FarmQuery): Observable<Page<FarmSummary>> => this.api.get(this.base, { ...q });
  get = (id: string): Observable<Farm> => this.api.get(`${this.base}/${id}`);
  create = (body: Record<string, unknown>): Observable<Farm> => this.api.post(this.base, body);
  update = (id: string, body: Record<string, unknown>): Observable<Farm> => this.api.patch(`${this.base}/${id}`, body);
  validateGeometry = (body: { geojson?: GeoGeometry | object; kml?: string }): Observable<GeometryReport> =>
    this.api.post(`${this.base}/geometry/validate`, body);
  saveBoundary = (id: string, body: { geojson?: GeoGeometry | object; kml?: string; source: string }): Observable<BoundarySaved> =>
    this.api.post(`${this.base}/${id}/boundary`, body);
  uploadBoundary = (id: string, file: File): Observable<BoundarySaved> => this.api.upload(`${this.base}/${id}/boundary/upload`, file, {});
  boundaries = (id: string): Observable<Boundary[]> => this.api.get(`${this.base}/${id}/boundaries`);
  overlaps = (id: string): Observable<Overlap[]> => this.api.get(`${this.base}/${id}/overlaps`);
  resolveOverlap = (id: string, checkId: string, resolution: 'CLEARED' | 'CONFIRMED_CONFLICT', notes: string): Observable<Overlap> =>
    this.api.post(`${this.base}/${id}/overlaps/${checkId}/resolve`, { resolution, notes });
  ownership = (id: string): Observable<Ownership[]> => this.api.get(`${this.base}/${id}/ownership`);
  addOwnership = (id: string, body: Record<string, unknown>): Observable<Ownership> => this.api.post(`${this.base}/${id}/ownership`, body);
  endOwnership = (id: string, oid: string, validTo: string, reason: string): Observable<Ownership> =>
    this.api.post(`${this.base}/${id}/ownership/${oid}/end`, { valid_to: validTo, reason });
  reviewOwnership = (id: string, oid: string, status: string, notes: string): Observable<Ownership> =>
    this.api.post(`${this.base}/${id}/ownership/${oid}/review`, { status, notes });
  history = (id: string, kind: HistoryKind): Observable<HistoryRecord[]> => this.api.get(`${this.base}/${id}/history/${kind}`);
  historyVersions = (id: string, kind: HistoryKind, rid: string): Observable<HistoryRecord[]> =>
    this.api.get(`${this.base}/${id}/history/${kind}/${rid}/versions`);
  addHistory = (id: string, kind: HistoryKind, body: Record<string, unknown>): Observable<HistoryRecord> =>
    this.api.post(`${this.base}/${id}/history/${kind}`, body);
  amendHistory = (id: string, kind: HistoryKind, rid: string, data: Record<string, unknown>, reason: string): Observable<HistoryRecord> =>
    this.api.post(`${this.base}/${id}/history/${kind}/${rid}/amend`, { data, reason });
  retractHistory = (id: string, kind: HistoryKind, rid: string, reason: string): Observable<HistoryRecord> =>
    this.api.post(`${this.base}/${id}/history/${kind}/${rid}/retract`, { reason });
  reviewHistory = (id: string, kind: HistoryKind, rid: string, status: string, notes: string): Observable<HistoryRecord> =>
    this.api.post(`${this.base}/${id}/history/${kind}/${rid}/review`, { status, notes });
  evidence = (id: string): Observable<Evidence[]> => this.api.get(`${this.base}/${id}/evidence`);
  addEvidence = (id: string, body: Record<string, unknown>): Observable<Evidence> => this.api.post(`${this.base}/${id}/evidence`, body);
  reviewEvidence = (id: string, eid: string, status: string, notes: string): Observable<Evidence> =>
    this.api.post(`${this.base}/${id}/evidence/${eid}/review`, { status, notes });
  uploadDocument = (id: string, file: File, category: string, title: string): Observable<{ id: string }> =>
    this.api.upload(`${this.base}/${id}/documents`, file, { category, title });
  transition = (id: string, endpoint: string, reason: string): Observable<Farm> => this.api.post(`${this.base}/${id}/${endpoint}`, { reason });
}
