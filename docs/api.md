# API

Base path `/api/v1`. Interactive docs at `/docs` (OpenAPI at `/api/v1/openapi.json`).

## Conventions

- **Auth**: `Authorization: Bearer <access token>`. Browsers get the refresh token as an httpOnly cookie
  scoped to `/api/v1/auth`.
- **Errors**: `{ "success": false, "error_code": "...", "message": "...", "details": {}, "request_id": "..." }`.
  Validation errors put `details.errors[] = {field, message, type}`.
- **Pagination**: `page` (from 1), `page_size` (1–100), `sort` (`field` or `-field`; whitelisted per endpoint).
  Response shape: `{ items, total, page, page_size }`.
- **Timestamps**: ISO-8601 UTC with `Z`.
- **Request ID**: send `X-Request-ID` (8–64 alphanumeric/hyphen) or one is generated; it is echoed back and
  stored in audit rows.
- **Reasons**: status changes, password resets, unlocks, member removal and session revocation need a
  `reason` (3–1000 characters), stored in the audit log.

## Endpoints (Phase 1)

| Method | Path | Permission |
|---|---|---|
| GET | `/health` | — |
| POST | `/auth/login` · `/auth/token` (OAuth2 form) | — |
| POST | `/auth/refresh` · `/auth/logout` | refresh cookie |
| GET | `/auth/me` | signed in |
| POST | `/auth/change-password` | signed in |
| GET/POST | `/admin/users` | users.read / users.manage |
| GET/PATCH | `/admin/users/{id}` | users.read / users.manage |
| POST | `/admin/users/{id}/status` · `/reset-password` | users.manage |
| POST | `/admin/users/{id}/unlock` | security.manage (platform) |
| POST/DELETE | `/admin/users/{id}/roles[/{user_role_id}]` | users.assign_roles |
| GET | `/admin/permissions` · `/admin/roles[/{id}]` | roles.read |
| POST/PATCH/PUT | `/admin/roles` · `/admin/roles/{id}` · `/admin/roles/{id}/permissions` | roles.manage (custom roles only) |
| GET/POST | `/admin/organizations` | organizations.read / organizations.manage (platform) |
| GET/PATCH | `/admin/organizations/{id}` | organizations.read / organizations.manage |
| POST | `/admin/organizations/{id}/status` | organizations.manage (platform) |
| GET/POST | `/admin/organizations/{id}/members` | organizations.read / organizations.manage_members |
| POST | `/admin/organizations/{id}/members/{user_id}/remove` | organizations.manage_members |
| GET | `/admin/audit-logs` · `/admin/workflow-events` | audit.read |
| GET | `/admin/security/events` · `/login-audit` · `/sessions` | security.read (platform) |
| POST | `/admin/security/sessions/{id}/revoke` | security.manage (platform) |

## Notable error codes

`INVALID_CREDENTIALS`, `TOKEN_EXPIRED`, `SESSION_REVOKED`, `REFRESH_REUSED`, `ACCOUNT_INACTIVE`,
`PASSWORD_CHANGE_REQUIRED`, `PASSWORD_POLICY`, `PERMISSION_DENIED`, `ROLE_ESCALATION_BLOCKED`,
`SELF_ROLE_CHANGE`, `LAST_PLATFORM_ADMIN`, `INVALID_STATUS_TRANSITION`, `USER_NOT_MEMBER`,
`ROLE_SCOPE_MISMATCH`, `ENVIRONMENT_MISMATCH`, `SYSTEM_ROLE_READONLY`, `RATE_LIMITED`, `PAYLOAD_TOO_LARGE`.
