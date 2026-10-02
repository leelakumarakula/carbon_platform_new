import { Me } from '../app/core/auth/auth.models';

/** Test helper: a signed-in user's /auth/me payload. */
export function makeMe(permissions: string[] = [], overrides: Partial<Me['user']> = {}): Me {
  return {
    permissions,
    platform_permissions: permissions,
    user: {
      id: 'u1', email: 'a@test.example', full_name: 'Ada Admin', phone: null, status: 'ACTIVE', must_change_password: false,
      mfa_enabled: false, is_locked: false, locked_until: null, last_login_at: null, environment: 'LIVE',
      created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', roles: [], organizations: [], ...overrides,
    },
  };
}
