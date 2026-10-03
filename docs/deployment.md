# Deployment

## Local

See the README: native setup (verified) or `docker-compose.yml` (SQL Server, Redis, MinIO, backend, nginx
frontend; written but not yet run on the development machine).

## Production checklist

1. `APP_ENV=production`; `SECRET_KEY` and `JWT_SECRET` are different, random and at least 32 characters, from a secret store.
2. HTTPS only, with `REFRESH_COOKIE_SECURE=true` (enforced at start-up). Serve the SPA and API from the same
   origin, or list exact origins in `CORS_ORIGINS`.
3. A SQL login with only the rights the app needs (no `sysadmin`, no DDL at runtime). Run migrations from a
   separate deploy step with a DDL-capable login: `python manage.py migrate && python manage.py seed-reference`.
4. Run `bootstrap-admin` once; the admin must change the password at first sign-in. Never run `seed-demo` in production.
5. Run uvicorn behind a reverse proxy with `--no-proxy-headers` and list the proxy addresses in `TRUSTED_PROXIES`, so client
   IPs (rate limiting, audit) are correct and `X-Forwarded-For` from anyone else is ignored (Phase 12B D21; docs/runtime-hardening.md).
6. Use a Redis-backed rate limiter before running more than one API process.
7. Set `DATA_ENCRYPTION_KEY` from the secret store and back it up separately. Without it, encrypted bank
   numbers cannot be read. Set `STORAGE_BACKEND` to an object store (the S3 adapter is pending) and a real
   `MALWARE_SCANNER` before accepting real uploads. Use a licensed or self-hosted map tile service.
8. Background jobs (Phase 12A, [background-jobs.md](background-jobs.md)):
   - Run Celery workers on Linux (prefork) with `-Q default,maintenance`, and exactly one `celery beat`.
   - Use Redis ≥ 7 with authentication + TLS, `noeviction`, never publicly exposed.
   - Set `JOB_ENVIRONMENTS=LIVE`.
   - Workers start after `migrate` (0017 seeds the SYSTEM actors).
   - If Redis or workers are down, jobs wait in SQL Server, lazy expiry keeps workflows correct, and `manage.py jobs-recover`
     republishes after an outage.
9. Back up SQL Server (full + log), monitor `security_events` for CRITICAL entries, and set a retention
   policy for `api_access_logs`.
