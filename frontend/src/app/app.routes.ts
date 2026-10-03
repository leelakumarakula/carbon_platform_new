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
        path: 'farmers',
        canActivate: [permissionGuard],
        data: { anyPermissions: [P.FARMERS_READ, P.FARMERS_SELF] },
        children: [
          { path: '', title: 'Farmers', loadComponent: () => import('./farmer/farmers-list-page').then((m) => m.FarmersListPage) },
          {
            path: 'new',
            title: 'Register farmer',
            canActivate: [permissionGuard],
            data: { permissions: [P.FARMERS_MANAGE] },
            loadComponent: () => import('./farmer/farmer-create-page').then((m) => m.FarmerCreatePage),
          },
          { path: ':id', title: 'Farmer', loadComponent: () => import('./farmer/farmer-detail-page').then((m) => m.FarmerDetailPage) },
        ],
      },
      {
        path: 'me/farmer',
        title: 'My farmer profile',
        canActivate: [permissionGuard],
        data: { permissions: [P.FARMERS_SELF] },
        loadComponent: () => import('./farmer/my-farmer-page').then((m) => m.MyFarmerPage),
      },
      {
        path: 'farms',
        canActivate: [permissionGuard],
        data: { anyPermissions: [P.FARMS_READ, P.FARMERS_SELF] },
        children: [
          { path: '', title: 'Farms', loadComponent: () => import('./farms/farms-list-page').then((m) => m.FarmsListPage) },
          {
            path: 'new',
            title: 'Add farm',
            canActivate: [permissionGuard],
            data: { anyPermissions: [P.FARMS_MANAGE, P.FARMERS_SELF] },
            loadComponent: () => import('./farms/farm-create-page').then((m) => m.FarmCreatePage),
          },
          { path: ':id', title: 'Farm', loadComponent: () => import('./farms/farm-detail-page').then((m) => m.FarmDetailPage) },
        ],
      },
      {
        path: 'projects',
        canActivate: [permissionGuard],
        data: { permissions: [P.PROJECTS_READ] },
        children: [
          { path: '', title: 'Projects', loadComponent: () => import('./projects/projects-list-page').then((m) => m.ProjectsListPage) },
          {
            path: 'new',
            title: 'New project',
            canActivate: [permissionGuard],
            data: { permissions: [P.PROJECTS_MANAGE] },
            loadComponent: () => import('./projects/project-create-page').then((m) => m.ProjectCreatePage),
          },
          { path: ':id', title: 'Project', loadComponent: () => import('./projects/project-detail-page').then((m) => m.ProjectDetailPage) },
        ],
      },
      {
        path: 'methodologies',
        canActivate: [permissionGuard],
        data: { permissions: [P.METHODOLOGIES_READ] },
        children: [
          { path: '', title: 'Methodologies', loadComponent: () => import('./methodologies/methodologies-page').then((m) => m.MethodologiesPage) },
          {
            path: 'versions/:id',
            title: 'Methodology version',
            loadComponent: () => import('./methodologies/methodology-version-page').then((m) => m.MethodologyVersionPage),
          },
        ],
      },
      {
        path: 'mrv',
        canActivate: [permissionGuard],
        data: { permissions: [P.MRV_READ] },
        children: [
          { path: '', title: 'MRV', loadComponent: () => import('./mrv/mrv-dashboard-page').then((m) => m.MrvDashboardPage) },
          { path: 'projects/:id', title: 'MRV workspace', loadComponent: () => import('./mrv/mrv-project-page').then((m) => m.MrvProjectPage) },
          {
            path: 'projects/:id/plans/new',
            title: 'New MRV plan',
            canActivate: [permissionGuard],
            data: { permissions: [P.MRV_MANAGE] },
            loadComponent: () => import('./mrv/mrv-plan-create-page').then((m) => m.MrvPlanCreatePage),
          },
          { path: 'plans/:id', title: 'MRV plan', loadComponent: () => import('./mrv/mrv-plan-detail-page').then((m) => m.MrvPlanDetailPage) },
          { path: 'datasets/:id', title: 'MRV dataset', loadComponent: () => import('./mrv/mrv-dataset-page').then((m) => m.MrvDatasetPage) },
          {
            path: 'samples/:id',
            title: 'Sample',
            canActivate: [permissionGuard],
            data: { permissions: [P.LAB_READ] },
            loadComponent: () => import('./lab/sample-detail-page').then((m) => m.SampleDetailPage),
          },
          {
            path: 'lab-results/:id',
            title: 'Laboratory result',
            canActivate: [permissionGuard],
            data: { permissions: [P.LAB_READ] },
            loadComponent: () => import('./lab/lab-result-lineage-page').then((m) => m.LabResultLineagePage),
          },
        ],
      },
      {
        path: 'calculations',
        title: 'Calculations',
        canActivate: [permissionGuard],
        data: { permissions: [P.CALCULATION_READ] },
        loadComponent: () => import('./calculation/calculations-page').then((m) => m.CalculationsPage),
      },
      {
        path: 'calculations/runs/:id',
        title: 'Calculation run',
        canActivate: [permissionGuard],
        data: { permissions: [P.CALCULATION_READ] },
        loadComponent: () => import('./calculation/calculation-run-page').then((m) => m.CalculationRunPage),
      },
      {
        path: 'registry',
        title: 'Registry',
        canActivate: [permissionGuard],
        data: { permissions: [P.REGISTRY_READ] },
        loadComponent: () => import('./registry/registry-page').then((m) => m.RegistryPage),
      },
      {
        path: 'credits',
        title: 'Issued credits',
        canActivate: [permissionGuard],
        data: { permissions: [P.CREDITS_READ] },
        loadComponent: () => import('./registry/credits-page').then((m) => m.CreditsPage),
      },
      {
        path: 'vvb',
        canActivate: [permissionGuard],
        data: { permissions: [P.VERIFICATION_VVB_READ] },
        children: [
          { path: '', title: 'VVB workspace', loadComponent: () => import('./verification/vvb-workspace-page').then((m) => m.VvbWorkspacePage) },
          {
            path: 'assignments/:id',
            title: 'VVB assignment',
            loadComponent: () => import('./verification/vvb-assignment-page').then((m) => m.VvbAssignmentPage),
          },
        ],
      },
      {
        path: 'laboratory',
        canActivate: [permissionGuard],
        data: { permissions: [P.LAB_LAB_READ] },
        children: [
          { path: '', title: 'Laboratory', loadComponent: () => import('./lab/laboratory-page').then((m) => m.LaboratoryPage) },
          { path: 'tests/:id', title: 'Laboratory test', loadComponent: () => import('./lab/lab-test-page').then((m) => m.LabTestPage) },
          {
            path: 'qa/:id',
            title: 'Laboratory QA',
            canActivate: [permissionGuard],
            data: { permissions: [P.LAB_QA] },
            loadComponent: () => import('./lab/lab-qa-page').then((m) => m.LabQaPage),
          },
        ],
      },
      {
        path: 'field',
        canActivate: [permissionGuard],
        data: { permissions: [P.SAMPLING_COLLECT] },
        children: [
          { path: '', title: 'Field work', loadComponent: () => import('./mrv/field-dashboard-page').then((m) => m.FieldDashboardPage) },
          {
            path: 'collections/:id',
            title: 'Field collection',
            loadComponent: () => import('./mrv/field-collection-page').then((m) => m.FieldCollectionPage),
          },
        ],
      },
      {
        path: 'me/projects',
        title: 'My project participation',
        canActivate: [permissionGuard],
        data: { permissions: [P.FARMERS_SELF] },
        loadComponent: () => import('./projects/my-participation-page').then((m) => m.MyParticipationPage),
      },
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
            path: 'catalog',
            title: 'Standards & activities',
            canActivate: [permissionGuard],
            data: { permissions: [P.STANDARDS_MANAGE] },
            loadComponent: () => import('./admin/catalog/catalog-page').then((m) => m.CatalogPage),
          },
          {
            path: 'consents',
            title: 'Consent types',
            canActivate: [permissionGuard],
            data: { permissions: [P.CONSENTS_CONFIGURE] },
            loadComponent: () => import('./admin/consents/consent-definitions-page').then((m) => m.ConsentDefinitionsPage),
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
