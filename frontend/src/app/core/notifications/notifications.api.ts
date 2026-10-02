import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Page } from '../api/api.models';
import { ApiService } from '../api/api.service';

export interface AppNotification {
  id: string;
  event_type: string;
  title: string;
  body: string | null;
  link: string | null;
  read_at: string | null;
  created_at: string;
}

@Injectable({ providedIn: 'root' })
export class NotificationsApi {
  private readonly api = inject(ApiService);
  list = (unreadOnly = false): Observable<Page<AppNotification>> => this.api.get('/notifications', { unread_only: unreadOnly, page_size: 20 });
  unreadCount = (): Observable<{ unread: number }> => this.api.get('/notifications/unread-count');
  markRead = (id: string): Observable<{ marked: number }> => this.api.post(`/notifications/${id}/read`);
  markAll = (): Observable<{ marked: number }> => this.api.post('/notifications/read-all');
}
