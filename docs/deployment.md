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
5. Run uvicorn behind a reverse proxy with `--proxy-headers`, so client IPs (rate limiting, audit) are correct.
6. Use a Redis-backed rate limiter before running more than one API process.
7. Set `DATA_ENCRYPTION_KEY` from the secret store and back it up separately. Without it, encrypted bank
   numbers cannot be read. Set `STORAGE_BACKEND` to an object store (the S3 adapter is pending) and a real
   `MALWARE_SCANNER` before accepting real uploads. Use a licensed or self-hosted map tile service.
8. Back up SQL Server (full + log), monitor `security_events` for CRITICAL entries, and set a retention
   policy for `api_access_logs`.
