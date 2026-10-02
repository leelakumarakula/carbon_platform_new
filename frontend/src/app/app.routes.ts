import { Routes } from '@angular/router';

import { authGuard, guestGuard, passwordChangedGuard, permissionGuard } from './core/auth/guards';
import { P } from './core/auth/permissions';
import { Shell } from './layout/shell';
import { ForbiddenPage, NotFoundPage } from './shared/simple-pages';

export const routes: Routes = [
  { path: 'login', canActivate: [guestGuard], title: 'Sign in', loadComponent: () => import('./auth/login-page').then((m) => m.LoginPage) },
  {
    path: 'change-password',
    canActivate: [authGuard],
    title: 'Change password',
    loadComponent: () => import('./auth/change-password-page').then((m) => m.ChangePasswordPage),
  },
  {
    path: '',
    component: Shell,
    canActivate: [authGuard],
    canActivateChild: [passwordChangedGuard],
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      { path: 'dashboard', title: 'Dashboard', loadComponent: () => import('./dashboard/dashboard-page').then((m) => m.DashboardPage) },
      { path: 'profile', title: 'My profile', loadComponent: () => import('./auth/profile-page').then((m) => m.ProfilePage) },
      {
        path: 'admin',
        children: [
          {
            path: 'users',
            canActivate: [permissionGuard],
            data: { permissions: [P.USERS_READ] },
            children: [
              { path: '', title: 'Users', loadComponent: () => import('./admin/users/users-list-page').then((m) => m.UsersListPage) },
              {
                path: 'new',
                title: 'New user',
                canActivate: [permissionGuard],
                data: { permissions: [P.USERS_MANAGE] },
                loadComponent: () => import('./admin/users/user-create-page').then((m) => m.UserCreatePage),
              },
              { path: ':id', title: 'User', loadComponent: () => import('./admin/users/user-detail-page').then((m) => m.UserDetailPage) },
            ],
          },
          {
            path: 'organizations',
            canActivate: [permissionGuard],
            data: { permissions: [P.ORGANIZATIONS_READ] },
            children: [
              {
                path: '',
                title: 'Organizations',
                loadComponent: () => import('./admin/organizations/organizations-list-page').then((m) => m.OrganizationsListPage),
              },
              {
                path: ':id',
                title: 'Organization',
                loadComponent: () => import('./admin/organizations/organization-detail-page').then((m) => m.OrganizationDetailPage),
              },
            ],
          },
          {
            path: 'roles',
            title: 'Roles & permissions',
            canActivate: [permissionGuard],
            data: { permissions: [P.ROLES_READ] },
            loadComponent: () => import('./admin/roles/roles-page').then((m) => m.RolesPage),
          },
          {
            path: 'audit',
            title: 'Audit log',
            canActivate: [permissionGuard],
            data: { permissions: [P.AUDIT_READ] },
            loadComponent: () => import('./admin/audit/audit-page').then((m) => m.AuditPage),
          },
          {
            path: 'security',
            title: 'Security center',
            canActivate: [permissionGuard],
            data: { permissions: [P.SECURITY_READ] },
            loadComponent: () => import('./admin/security/security-page').then((m) => m.SecurityPage),
          },
        ],
      },
      { path: 'forbidden', title: 'No access', component: ForbiddenPage },
      { path: '**', title: 'Not found', component: NotFoundPage },
    ],
  },
];
