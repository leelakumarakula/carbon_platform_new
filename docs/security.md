# Security

| Control (spec §30) | Implementation |
|---|---|
| Password hashing | bcrypt (cost 12); policy ≥12 chars, letters + digits, ≤72 bytes, no edge spaces |
| Access token | HS256 JWT, 15 min, `sub`/`sid`/`iss`/`exp`/`jti`, kept in memory by the SPA |
| Refresh token | 48 random bytes; only its SHA-256 is stored; httpOnly + SameSite=Strict cookie on `/api/v1/auth`; rotated on every use; reuse revokes the session and logs a CRITICAL event |
| Session control | Every request checks the session isn't revoked or expired and the user is ACTIVE and not locked |
| Lockout | 5 failures → 15-minute lock (configurable); generic error message; login audit records the real reason |
| Rate limiting | per IP and per IP+email on login (10/min), global per IP (600/min); in-memory (Redis needed before scaling out) |
| Authorization | permission check per route + organization scoping in services; escalation guards; last-admin protection |
| Temporary passwords | `must_change_password` blocks every permissioned endpoint until changed |
| Input validation | Pydantic schemas; e-mail normalisation; codes upper-cased and pattern-checked |
| Headers | nosniff, frame DENY, no-referrer, Permissions-Policy, API `Cache-Control: no-store` and CSP `default-src 'none'`, HSTS in production |
| CORS | explicit origin list; credentials allowed only for those origins |
| Body size | 25 MB limit (Content-Length); upload type validation and the malware-scan hook arrive with documents (Phase 2) |
| Audit | append-only tables enforced by DB triggers; secrets never logged (`SENSITIVE_FIELDS`) |
| Secrets | environment / `.env` (never committed); production guard requires secure cookies and distinct keys |
| MFA | columns and a secret-store reference are ready; enrolment flow planned with Security Admin tooling |

Tests in `backend/tests` cover: unauthorized access, role escalation, cross-organization access, invalid,
expired and forged tokens, refresh-token reuse, lockout, rate limiting, and append-only enforcement.
