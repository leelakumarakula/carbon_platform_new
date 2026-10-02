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
    title: 'Administration',
    items: [
      { label: 'Users', icon: 'group', route: '/admin/users', permissions: [P.USERS_READ] },
      { label: 'Organizations', icon: 'domain', route: '/admin/organizations', permissions: [P.ORGANIZATIONS_READ] },
      { label: 'Roles & permissions', icon: 'admin_panel_settings', route: '/admin/roles', permissions: [P.ROLES_READ] },
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
