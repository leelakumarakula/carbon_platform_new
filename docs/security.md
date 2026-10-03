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
| Body size | 25 MB request limit (Content-Length); uploads read with a bounded reader, max `MAX_UPLOAD_BYTES` (15 MB) |
| File uploads | type sniffed from content, not the extension or the client MIME type (PDF/PNG/JPEG/WebP, GeoJSON/KML); filenames sanitised; SHA-256 checksum; `MalwareScanner` hook (dev: EICAR signature only, real engine pending); files served only through the API as attachments; versions append-only |
| KML/XML | DOCTYPE/ENTITY declarations rejected (no XXE or entity expansion); vertex limit 5000 |
| Personal data | KYC ID numbers: only a keyed HMAC fingerprint and the last 4 digits are stored. Bank account numbers: Fernet-encrypted (`DATA_ENCRYPTION_KEY`), only the last 4 digits returned. KYC and bank-proof documents are RESTRICTED |
| Record access | organization scope **or** self-service via `farmers.self` + a linked login; out-of-scope records 404; cross-org overlap details hidden |
| Projects | organization-scoped access (404 outside scope); project roles never grant permissions (the user must hold the role); eligibility approver ≠ submitter; carbon-rights reviewer ≠ recorder; buyers and farmers have no project-wide view (farmers: own participation only); other organizations' overlapping projects shown without identity |
| Methodologies | versions approved by a second person; approved versions immutable (new version to change); rules engine only proposes; confirmation needs a specialist recommendation by someone else; locked methodology changes only via audited unlock; evaluations, results and change history append-only |
| MRV / sampling | MRV only on a LOCKED methodology version; plan, stratum, design, relocation, field-record, QA and dataset approvals by a second person; field collectors see and change only their own assigned points/collections and approve nothing; CONFIGURATION_REQUIRED gaps need an audited acknowledgement; approved plans, strata and datasets are never edited (new versions); dataset snapshots hashed (SHA-256) and re-verified on approval; buyers, labs, VVB, finance and farmers have no MRV access |
| Laboratory | two-sided engagements (proposer ≠ accepter); laboratory-facing API returns explicit allow-list schemas only (no farmer / farm / GPS / MRV data) and only for samples shipped to that laboratory; laboratory documents PDF only; custody events and QA reviews append-only and approved results immutable (DB triggers); one APPROVED result per root sample + rule; lab QA separation of duties (analyst, submitter, registrant, sealer, shipment creator / dispatcher, retest requester); report SHA-256 re-verified at QA; DEMO and live never mixed |
| Separation of duties | KYC submitter ≠ verifier, bank account adder ≠ verifier, farm submitter ≠ verifier, evidence capturer ≠ reviewer |
| Audit | append-only tables enforced by DB triggers; secrets never logged (`SENSITIVE_FIELDS`) |
| Secrets | environment / `.env` (never committed); production guard requires secure cookies and distinct keys. Rotating `DATA_ENCRYPTION_KEY` needs a re-encryption job (not built yet). Losing it makes stored bank numbers unrecoverable, so keep it in the secret store with a backup |
| MFA | columns and a secret-store reference are ready; enrolment flow planned with Security Admin tooling |

Tests in `backend/tests` cover: unauthorized access, role escalation, cross-organization access, invalid,
expired and forged tokens, refresh-token reuse, lockout, rate limiting, and append-only enforcement. Phase 2 adds: cross-organization farmer/farm access, self-service limits, restricted documents, separation of duties, file-type spoofing, the EICAR test file, unsafe KML, and the absence of clear-text identity and bank numbers in responses and the database. Phase 5 adds: MRV RBAC per role, organization isolation of MRV records, collector restrictions (own points only, no review), separation of duties on every MRV approval, and snapshot-hash lineage. Phase 6 adds: laboratory allow-lists and organization isolation, two-sided engagements, laboratory QA separation of duties, the append-only / immutability triggers, PDF-only laboratory documents, and the wind-down rules after an engagement ends.
