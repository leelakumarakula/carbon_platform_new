import { P } from '../auth/permissions';

export interface NavItem {
  label: string;
  icon: string;
  route: string;
  /** All are required to see the item. Omit for items every signed-in user can open. */
  permissions?: readonly string[];
}

export interface NavSection {
  title: string;
  items: readonly NavItem[];
}

/**
 * Navigation registry. Each implementation phase adds its module here (farmers, farms,
 * projects, MRV, laboratory, ...); items are shown only to users holding the permissions.
 */
export const NAVIGATION: readonly NavSection[] = [
  {
    title: 'Overview',
    items: [{ label: 'Dashboard', icon: 'dashboard', route: '/dashboard' }],
  },
  {
    title: 'Field operations',
    items: [
      { label: 'Farmers', icon: 'diversity_3', route: '/farmers', permissions: [P.FARMERS_READ] },
      { label: 'Farms', icon: 'agriculture', route: '/farms', permissions: [P.FARMS_READ] },
      { label: 'Field work', icon: 'pin_drop', route: '/field', permissions: [P.SAMPLING_COLLECT] },
    ],
  },
  {
    title: 'Projects',
    items: [
      { label: 'Projects', icon: 'workspaces', route: '/projects', permissions: [P.PROJECTS_READ] },
      { label: 'Methodologies', icon: 'menu_book', route: '/methodologies', permissions: [P.METHODOLOGIES_READ] },
      { label: 'MRV', icon: 'monitoring', route: '/mrv', permissions: [P.MRV_READ] },
      { label: 'Standards & activities', icon: 'library_books', route: '/admin/catalog', permissions: [P.STANDARDS_MANAGE] },
    ],
  },
  {
    title: 'Laboratory',
    items: [{ label: 'Laboratory', icon: 'science', route: '/laboratory', permissions: [P.LAB_LAB_READ] }],
  },
  {
    title: 'My farm',
    items: [
      { label: 'My farmer profile', icon: 'badge', route: '/me/farmer', permissions: [P.FARMERS_SELF] },
      { label: 'My farms', icon: 'agriculture', route: '/farms', permissions: [P.FARMERS_SELF] },
      { label: 'My projects', icon: 'handshake', route: '/me/projects', permissions: [P.FARMERS_SELF] },
    ],
  },
  {
    title: 'Administration',
    items: [
      { label: 'Users', icon: 'group', route: '/admin/users', permissions: [P.USERS_READ] },
      { label: 'Organizations', icon: 'domain', route: '/admin/organizations', permissions: [P.ORGANIZATIONS_READ] },
      { label: 'Roles & permissions', icon: 'admin_panel_settings', route: '/admin/roles', permissions: [P.ROLES_READ] },
      { label: 'Consent types', icon: 'fact_check', route: '/admin/consents', permissions: [P.CONSENTS_CONFIGURE] },
      { label: 'Audit log', icon: 'history', route: '/admin/audit', permissions: [P.AUDIT_READ] },
    ],
  },
  {
    title: 'Security',
    items: [{ label: 'Security center', icon: 'shield', route: '/admin/security', permissions: [P.SECURITY_READ] }],
  },
];

export function visibleNavigation(sections: readonly NavSection[], has: (code: string) => boolean): NavSection[] {
  return sections
    .map((s) => ({ ...s, items: s.items.filter((i) => (i.permissions ?? []).every(has)) }))
    .filter((s) => s.items.length > 0);
}
