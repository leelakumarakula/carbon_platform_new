import { P } from '../auth/permissions';

export interface NavItem {
  label: string;
  icon: string;
  route: string;
  /** All are required to see the item. Omit for items every signed-in user can open. */
  permissions?: readonly string[];
  /** At least one is required (in addition to `permissions`). */
  anyPermissions?: readonly string[];
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
      { label: 'Calculations', icon: 'calculate', route: '/calculations', permissions: [P.CALCULATION_READ] },
      { label: 'Standards & activities', icon: 'library_books', route: '/admin/catalog', permissions: [P.STANDARDS_MANAGE] },
    ],
  },
  {
    title: 'Verification',
    items: [{ label: 'VVB workspace', icon: 'verified', route: '/vvb', permissions: [P.VERIFICATION_VVB_READ] }],
  },
  {
    title: 'Registry',
    items: [
      { label: 'Registry', icon: 'account_balance', route: '/registry', permissions: [P.REGISTRY_READ] },
      { label: 'Issued credits', icon: 'workspace_premium', route: '/credits', permissions: [P.CREDITS_READ] },
      { label: 'Credit ledger', icon: 'account_tree', route: '/ledger', permissions: [P.CREDITS_READ] },
    ],
  },
  {
    title: 'Credits',
    items: [{ label: 'My credits', icon: 'wallet', route: '/holdings', permissions: [P.CREDITS_HOLDER_READ] }],
  },
  {
    title: 'Marketplace',
    items: [
      { label: 'Marketplace', icon: 'storefront', route: '/marketplace', permissions: [P.MARKETPLACE_READ] },
      { label: 'Listings', icon: 'sell', route: '/marketplace/listings', anyPermissions: [P.LISTINGS_MANAGE, P.LISTINGS_APPROVE] },
      { label: 'Orders', icon: 'receipt_long', route: '/orders', anyPermissions: [P.ORDERS_READ, P.ORDERS_PLACE] },
      { label: 'Payments', icon: 'payments', route: '/payments', anyPermissions: [P.PAYMENTS_CONFIRM, P.REFUNDS_REQUEST, P.REFUNDS_APPROVE] },
      { label: 'Buyer profile', icon: 'verified_user', route: '/marketplace/profile', permissions: [P.BUYERS_KYC_SUBMIT] },
      { label: 'KYC review', icon: 'fact_check', route: '/marketplace/kyc-review', permissions: [P.BUYERS_KYC_VERIFY] },
    ],
  },
  {
    title: 'Finance',
    items: [
      { label: 'Revenue & costs', icon: 'account_balance', route: '/finance/revenue',
        anyPermissions: [P.REVENUE_READ, P.COSTS_MANAGE, P.COSTS_APPROVE] },
      { label: 'Revenue sharing', icon: 'pie_chart', route: '/finance/sharing', anyPermissions: [P.SHARING_MANAGE, P.SHARING_APPROVE] },
      { label: 'Settlements', icon: 'calculate', route: '/finance/settlements',
        anyPermissions: [P.SETTLEMENT_READ, P.SETTLEMENT_CALCULATE, P.SETTLEMENT_APPROVE] },
      { label: 'Payouts', icon: 'savings', route: '/finance/payouts',
        anyPermissions: [P.PAYOUTS_READ, P.PAYOUTS_CALCULATE, P.PAYOUTS_APPROVE, P.PAYOUTS_EXECUTE, P.PAYOUTS_RECONCILE] },
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
      { label: 'My payouts', icon: 'savings', route: '/me/payouts', permissions: [P.FARMERS_SELF] },
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
      { label: 'Background jobs', icon: 'pending_actions', route: '/admin/jobs', permissions: [P.JOBS_READ] },
    ],
  },
  {
    title: 'Security',
    items: [
      { label: 'Security center', icon: 'shield', route: '/admin/security', permissions: [P.SECURITY_READ] },
      { label: 'Document quarantine', icon: 'gpp_bad', route: '/admin/quarantine', permissions: [P.SECURITY_READ] },
    ],
  },
];

export function visibleNavigation(sections: readonly NavSection[], has: (code: string) => boolean): NavSection[] {
  return sections
    .map((s) => ({ ...s, items: s.items.filter((i) => (i.permissions ?? []).every(has) && (!i.anyPermissions?.length || i.anyPermissions.some(has))) }))
    .filter((s) => s.items.length > 0);
}
