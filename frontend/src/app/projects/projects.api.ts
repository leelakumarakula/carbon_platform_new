import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Page, PageQuery } from '../core/api/api.models';
import { ApiService } from '../core/api/api.service';
import {
  Baselines,
  BoundaryView,
  CandidateUser,
  CarbonRight,
  CarbonRightInput,
  CatalogActivity,
  CatalogStandard,
  CreditingPeriod,
  EligibleFarm,
  MyParticipation,
  Participant,
  Project,
  ProjectActivities,
  ProjectDocuments,
  ProjectFarm,
  ProjectStandards,
  ProjectStatus,
  ProjectSummary,
  StatusHistoryEntry,
} from './project.models';

export interface ProjectQuery extends PageQuery {
  search?: string | null;
  status?: ProjectStatus | null;
  organization_id?: string | null;
  environment?: 'LIVE' | 'DEMO' | null;
}

export interface ProjectInput {
  organization_id?: string;
  name?: string;
  description?: string | null;
  project_type?: string;
  country?: string;
  region?: string | null;
  start_date?: string | null;
}

@Injectable({ providedIn: 'root' })
export class ProjectsApi {
  private readonly api = inject(ApiService);
  private readonly base = '/projects';

  list = (q: ProjectQuery): Observable<Page<ProjectSummary>> => this.api.get(this.base, { ...q });
  get = (id: string): Observable<Project> => this.api.get(`${this.base}/${id}`);
  create = (body: ProjectInput): Observable<Project> => this.api.post(this.base, body);
  update = (id: string, body: ProjectInput): Observable<Project> => this.api.patch(`${this.base}/${id}`, body);
  transition = (id: string, endpoint: string, reason: string): Observable<Project> => this.api.post(`${this.base}/${id}/${endpoint}`, { reason });
  myParticipation = (): Observable<MyParticipation[]> => this.api.get(`${this.base}/my-participation`);

  farms = (id: string, includeRemoved = false): Observable<ProjectFarm[]> =>
    this.api.get(`${this.base}/${id}/farms`, { include_removed: includeRemoved || null });
  eligibleFarms = (id: string): Observable<EligibleFarm[]> => this.api.get(`${this.base}/${id}/farms/eligible`);
  addFarm = (id: string, body: { farm_id: string; participation_start: string; participation_end?: string | null;
    carbon_rights: CarbonRightInput; acknowledge_conflicts?: boolean; conflict_notes?: string | null }): Observable<ProjectFarm> =>
    this.api.post(`${this.base}/${id}/farms`, body);
  removeFarm = (id: string, farmId: string, reason: string): Observable<ProjectFarm> =>
    this.api.delete(`${this.base}/${id}/farms/${farmId}`, undefined, { reason });

  participants = (id: string): Observable<Participant[]> => this.api.get(`${this.base}/${id}/participants`);
  candidates = (id: string): Observable<CandidateUser[]> => this.api.get(`${this.base}/${id}/participants/candidates`);
  addParticipant = (id: string, body: { user_id: string; project_role: string; start_date?: string | null; notes?: string | null }):
    Observable<Participant> => this.api.post(`${this.base}/${id}/participants`, body);
  updateParticipant = (id: string, pid: string, body: Record<string, unknown>): Observable<Participant> =>
    this.api.patch(`${this.base}/${id}/participants/${pid}`, body);

  boundary = (id: string): Observable<BoundaryView> => this.api.get(`${this.base}/${id}/boundary`);
  recomputeBoundary = (id: string): Observable<BoundaryView> => this.api.post(`${this.base}/${id}/boundary/recompute`);
  reviewBoundary = (id: string, decision: 'ACCEPTED' | 'ISSUES', notes: string): Observable<BoundaryView> =>
    this.api.post(`${this.base}/${id}/boundary/review`, { decision, notes });

  standards = (id: string): Observable<ProjectStandards> => this.api.get(`${this.base}/${id}/standards`);
  selectStandard = (id: string, standardId: string, reason?: string | null): Observable<Project> =>
    this.api.post(`${this.base}/${id}/standard`, { standard_id: standardId, reason: reason || null });
  activities = (id: string): Observable<ProjectActivities> => this.api.get(`${this.base}/${id}/activities`);
  selectActivity = (id: string, activityId: string, reason?: string | null): Observable<Project> =>
    this.api.post(`${this.base}/${id}/activity`, { activity_id: activityId, reason: reason || null });

  creditingPeriods = (id: string): Observable<CreditingPeriod[]> => this.api.get(`${this.base}/${id}/crediting-period`);
  addCreditingPeriod = (id: string, body: { start_date: string; end_date: string; notes?: string | null; replaces_id?: string | null;
    reason?: string | null }): Observable<CreditingPeriod> => this.api.post(`${this.base}/${id}/crediting-period`, body);
  baseline = (id: string): Observable<Baselines> => this.api.get(`${this.base}/${id}/baseline`);
  updateBaseline = (id: string, body: Record<string, unknown>): Observable<Baselines> => this.api.patch(`${this.base}/${id}/baseline`, body);

  carbonRights = (id: string): Observable<CarbonRight[]> => this.api.get(`${this.base}/${id}/carbon-rights`);
  addCarbonRight = (id: string, body: CarbonRightInput & { project_farm_id: string }): Observable<CarbonRight> =>
    this.api.post(`${this.base}/${id}/carbon-rights`, body);
  reviewCarbonRight = (id: string, rid: string, status: 'VERIFIED' | 'REJECTED', notes: string): Observable<CarbonRight> =>
    this.api.post(`${this.base}/${id}/carbon-rights/${rid}/review`, { status, notes });
  endCarbonRight = (id: string, rid: string, status: 'ENDED' | 'VOID', reason: string): Observable<CarbonRight> =>
    this.api.post(`${this.base}/${id}/carbon-rights/${rid}/end`, { status, reason });

  documents = (id: string): Observable<ProjectDocuments> => this.api.get(`${this.base}/${id}/documents`);
  uploadDocument = (id: string, file: File, category: string, title: string): Observable<{ id: string }> =>
    this.api.upload(`${this.base}/${id}/documents`, file, { category, title });
  statusHistory = (id: string): Observable<StatusHistoryEntry[]> => this.api.get(`${this.base}/${id}/status-history`);
}

@Injectable({ providedIn: 'root' })
export class CatalogApi {
  private readonly api = inject(ApiService);
  standards = (environment?: string | null): Observable<CatalogStandard[]> => this.api.get('/standards', { environment: environment ?? null });
  activities = (environment?: string | null): Observable<CatalogActivity[]> => this.api.get('/activities', { environment: environment ?? null });
  createStandard = (body: Record<string, unknown>): Observable<CatalogStandard> => this.api.post('/standards', body);
  updateStandard = (id: string, body: Record<string, unknown>): Observable<CatalogStandard> => this.api.patch(`/standards/${id}`, body);
  createActivity = (body: Record<string, unknown>): Observable<CatalogActivity> => this.api.post('/activities', body);
  updateActivity = (id: string, body: Record<string, unknown>): Observable<CatalogActivity> => this.api.patch(`/activities/${id}`, body);
  linkActivity = (id: string, standardId: string): Observable<CatalogActivity> => this.api.post(`/activities/${id}/standards`, { standard_id: standardId });
}
