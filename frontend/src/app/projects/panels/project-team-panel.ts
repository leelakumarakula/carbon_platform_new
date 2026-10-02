import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormControl, FormGroup, FormGroupDirective, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { CandidateUser, PROJECT_ROLES, Participant, Project } from '../project.models';
import { ProjectsApi } from '../projects.api';

/** Project team. A project role is only a record of who works on the project: the user must already hold that role
 *  (RBAC stays the single permission system). */
@Component({
  selector: 'app-project-team-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, ReactiveFormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule, StatusBadge],
  template: `
    <div class="tab-body">
      @for (m of members(); track m.id) {
        <div class="line" [class.removed]="m.status === 'REMOVED'">
          <div class="grow"><strong>{{ m.user_name }}</strong> <span class="muted small">{{ m.user_email }}</span>
            <div class="muted small">{{ label(m.project_role) }} · since {{ m.start_date ?? (m.added_at | date: 'mediumDate') }}
              @if (m.end_date) { · until {{ m.end_date }} } @if (m.notes) { · {{ m.notes }} }
              @if (m.removal_reason) { · removed: {{ m.removal_reason }} }</div>
          </div>
          <app-status-badge [status]="m.status === 'ACTIVE' ? 'ACTIVE' : 'REVOKED'" [text]="label(m.status)" />
          @if (canEdit() && m.status === 'ACTIVE') { <button mat-button type="button" (click)="remove(m)" [disabled]="busy()">Remove</button> }
        </div>
      } @empty { <p class="muted">No team members yet.</p> }
      @if (canEdit()) {
        <form [formGroup]="form" #fd="ngForm" (ngSubmit)="add(fd)" class="add">
          <mat-form-field subscriptSizing="dynamic" class="wide">
            <mat-label>Person</mat-label>
            <mat-select formControlName="user_id">
              @for (c of candidates(); track c.user_id) { <mat-option [value]="c.user_id">{{ c.full_name }} · {{ c.email }}</mat-option> }
            </mat-select>
          </mat-form-field>
          <mat-form-field subscriptSizing="dynamic">
            <mat-label>Project role</mat-label>
            <mat-select formControlName="project_role">
              @for (r of rolesFor(); track r) { <mat-option [value]="r">{{ label(r) }}</mat-option> }
            </mat-select>
          </mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Notes</mat-label><input matInput formControlName="notes" /></mat-form-field>
          <button mat-flat-button type="submit" [disabled]="busy() || form.invalid">Add to team</button>
        </form>
        <p class="muted small">Only roles the person already holds for this organization are offered. Grant roles in Administration → Users.</p>
      }
    </div>
  `,
  styles: `
    .line { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); flex-wrap: wrap; }
    .removed { opacity: .6; } .grow { flex: 1; min-width: 240px; }
    .add { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 16px; } .wide { min-width: 280px; flex: 1; }
  `,
})
export class ProjectTeamPanel implements OnInit {
  readonly project = input.required<Project>();
  private readonly api = inject(ProjectsApi);
  private readonly notify = inject(NotifyService);
  private readonly dialog = inject(MatDialog);
  protected readonly label = label;
  protected readonly members = signal<Participant[]>([]);
  protected readonly candidates = signal<CandidateUser[]>([]);
  protected readonly busy = signal(false);
  protected readonly selectedUser = signal('');
  protected readonly canEdit = computed(() => this.project().can_manage && this.project().status !== 'CLOSED');
  protected readonly rolesFor = computed(() => {
    const c = this.candidates().find((x) => x.user_id === this.selectedUser());
    return PROJECT_ROLES.filter((r) => c?.roles.includes(r));
  });
  protected readonly form = new FormGroup({
    user_id: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    project_role: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    notes: new FormControl('', { nonNullable: true }),
  });

  ngOnInit(): void {
    this.form.controls.user_id.valueChanges.subscribe((v) => {
      this.selectedUser.set(v);
      const roles = this.rolesFor();
      this.form.controls.project_role.setValue(roles.length === 1 ? roles[0] : '');
    });
    this.load();
  }

  load(): void {
    this.api.participants(this.project().id).subscribe((m) => this.members.set(m));
    if (this.canEdit()) this.api.candidates(this.project().id).subscribe((c) => this.candidates.set(c));
  }

  add(fd?: FormGroupDirective): void {
    const v = this.form.getRawValue();
    runAction(this.api.addParticipant(this.project().id, { user_id: v.user_id, project_role: v.project_role, notes: v.notes.trim() || null }),
      this.busy, this.notify, 'Team member added.', () => {
        (fd ?? this.form).reset();
        this.load();
      });
  }

  remove(m: Participant): void {
    askReason(this.dialog, { title: `Remove ${m.user_name} (${label(m.project_role)})?`, confirmLabel: 'Remove', danger: true }).subscribe((r) => {
      if (r) runAction(this.api.updateParticipant(this.project().id, m.id, { status: 'REMOVED', reason: r.reason }), this.busy, this.notify,
        'Team member removed.', () => this.load());
    });
  }
}
