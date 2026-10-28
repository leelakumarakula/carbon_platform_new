# Hosting Guide — Carbon Platform (frontend + backend)

**For:** the person or team who will put the platform on a server and keep it running.
**Covers:** what you need to buy or prepare, then every step to get the platform live on your own domain with HTTPS.

---

## 1. What you are hosting

The platform is 7 parts. All of them run on one server for a pilot.

| # | Part | What it does | Technology |
|---|---|---|---|
| 1 | **Frontend** | The website users open in a browser | Angular 21, served by nginx |
| 2 | **Backend API** | All business logic: `/api/v1/...` | Python 3.12, FastAPI, uvicorn |
| 3 | **Worker** | Background jobs (expiry sweeps, rescans, clean-up) | Celery (same code as the API) |
| 4 | **Beat** | Scheduler that tells the worker when to run jobs (**exactly one**) | Celery beat |
| 5 | **Database** | All platform data | Microsoft SQL Server 2022 |
| 6 | **Redis** | Job queue and shared rate limits (holds no business data) | Redis 7 |
| 7 | **Object storage** | Uploaded documents and photos (evidence, lab PDFs, payment proofs) | MinIO (S3-compatible) |

In front of all of it sits a **web server with HTTPS** (Caddy in this guide). It gets the certificate automatically.

```
 Browser ──HTTPS──► Caddy :443 ──► Frontend (nginx) ──/api/──► Backend API ──► SQL Server
                                                                   │  ├──────► MinIO (documents)
                                                                   │  └──────► Redis ◄── Worker + Beat
```

The frontend and the API are served from **the same address** (for example `https://carbon.yourcompany.in`). The frontend
calls `/api/v1/...` on its own domain, so no separate API domain is needed. The login cookie is `SameSite=Strict`.

---

## 2. Two levels of hosting: choose yours

The code has two modes. The difference matters because **production mode refuses to start** until some extra
infrastructure exists.

| | **Level A — Pilot / UAT** (works with today's code) | **Level B — Full production** |
|---|---|---|
| Setting | `APP_ENV=staging` | `APP_ENV=production` |
| HTTPS, secure login cookie | Yes | Yes (enforced) |
| Documents stored in | MinIO on the same server | MinIO with HTTPS + encryption key service (KES/KMS) |
| Virus scanning of uploads | Test check only; documents are marked **NOT_SCANNED** | **A commercial antivirus service is required.** The code has the hook, but **no vendor adapter is written yet** (developer work) |
| Secrets | In a protected `.env` file on the server | Files mounted by a secret store (`SECRETS_DIR`); plain environment variables are refused |
| SQL Server | In Docker on the same server, Express edition (free, 10 GB limit) | Separate server, Standard edition licence, validated TLS certificate, least-privilege login |
| Redis | Same server, internal network only | TLS (`rediss://`) + dedicated ACL user and password |
| Backups | Nightly script (Section 7) | Encrypted, off-site, 5-minute log backups (`docs/operations-runbook.md`) |
| Swagger page `/docs` | Available | Turned off automatically |
| Good for | Internal testing, UAT, a small pilot with known users | Real farmers, real money, real registry credits at scale |

**Recommendation:** go live with **Level A** first on one server (Sections 3–9). Move to Level B when the items in
Section 10 are ready.

---

## 3. Requirements: what you need before you start

### 3.1 Server

| Item | Level A (pilot, one server) | Level B (production, starting point) |
|---|---|---|
| Servers | 1 Linux virtual machine | 3: app server, database server, storage server (plus a backup location) |
| Operating system | **Ubuntu Server 24.04 LTS** (64-bit, x86_64) | Same |
| CPU | 4 vCPU | App 4 vCPU · DB 4–8 vCPU · Storage 2 vCPU |
| RAM | **16 GB** (SQL Server needs at least 2 GB; 8 GB will be tight) | App 8 GB · DB 32 GB · Storage 4 GB |
| Disk | 100 GB SSD | DB 200 GB SSD · Storage sized for documents (photos ≈ 1–5 MB each) |
| Location | **India** (decided: D50). Examples: AWS Mumbai/Hyderabad, Azure Central India/Pune, Google Cloud Mumbai/Delhi, or an Indian provider such as E2E Networks or Yotta | Same |
| Public IP | 1 static (elastic) IP | Load balancer / static IP for the app server only |

These sizes are a sensible starting point, not measured figures. Watch CPU, RAM and disk in the first weeks and resize.

> **Why Linux?** The background workers (Celery) are supported only on Linux. Every container image here is Linux.
> Windows Server is not recommended.

### 3.2 Software on the server

| Software | Version | Why |
|---|---|---|
| Docker Engine | 27 or newer | Runs every part as a container |
| Docker Compose plugin | **2.24.4 or newer** | The override file uses `!reset` (needs 2.24.4+) |
| Git | any recent | To download the two code repositories |
| openssl | (comes with Ubuntu) | To generate secrets |

Docker installs everything else (Python, Node, SQL Server, Redis, MinIO, nginx, Caddy) inside the images.
**Do not** install Python, Node or SQL Server on the server yourself.

### 3.3 Domain and HTTPS

| Item | Details |
|---|---|
| A domain name | e.g. `carbon.yourcompany.in` (a subdomain of a domain you own is fine) |
| DNS **A record** | Points the domain to the server's public IP |
| TLS certificate | **Automatic and free** from Let's Encrypt through Caddy, once DNS works and ports 80/443 are open |

### 3.4 Accounts, licences and external services

| Item | Level A | Level B | Notes |
|---|---|---|---|
| GitHub access to both repositories | **Required** | Required | `leelakumarakula/carbon_platform_new` (backend) and `charan14111411/carbon_project_frontend` (frontend). Use a deploy key or a personal access token with read access |
| SQL Server licence | Not needed (Express is free) | **Standard edition licence** | Express: 10 GB per database, about 1.4 GB memory. The Developer edition must not be used for real users |
| Antivirus scanning API | Not needed | **Required, vendor not chosen** | Plus a developer to write the adapter (`backend/app/integrations/malware.py`, `register_scanner`) |
| Map tiles (base map) | Public OpenStreetMap is OK for light pilot use | **Licensed or self-hosted tile service** | Settings `MAP_TILE_URL`, `MAP_TERRAIN_URL` |
| Satellite imagery in the 3D view | Esri World Imagery (development default) | ArcGIS licence or another licensed source, or switch it off (`MAP_SATELLITE_URL=` empty) | Display only |
| Secret store | Not needed | Required (vendor not chosen) | Renders one file per secret into `SECRETS_DIR` |
| Monitoring / log platform | Optional | Required | Reads JSON logs and `GET /metrics` |
| SMTP (email) | Not used | Not used yet | External notifications are switched off in this release |
| FarmFuture | Optional | Optional | Boundary import by mobile number; `FARMFUTURE_PROVIDER=none` switches it off |

Free external data services the backend calls when a user asks for them (no key needed): Open-Meteo (weather),
ISRIC SoilGrids (soil), Microsoft Planetary Computer (satellite NDVI).

### 3.5 Network ports

| Port | Open to | Purpose |
|---|---|---|
| **22** | **Your office IP only** | SSH for administration |
| **80** | Everyone | Let's Encrypt check + redirect to HTTPS |
| **443** | Everyone | The platform |
| 1433, 6379, 9000, 9001, 8000, 4200 | **Nobody** (closed) | SQL Server, Redis, MinIO, API, frontend: internal Docker network only |

### 3.6 Outbound internet access the server needs

| Destination | Used for |
|---|---|
| `github.com` | Downloading the code |
| `registry-1.docker.io`, `mcr.microsoft.com`, `packages.microsoft.com`, `pypi.org`, `files.pythonhosted.org`, `registry.npmjs.org` | Building the images |
| `acme-v02.api.letsencrypt.org` | HTTPS certificate |
| `archive-api.open-meteo.com`, `rest.isric.org`, `planetarycomputer.microsoft.com`, `api.farmfuture.io` | External farm data (only when a user requests it) |

Map tiles are loaded by the **user's browser**, not the server.

### 3.7 Secrets you will generate (Step 6 shows how)

| Secret | Purpose | If lost |
|---|---|---|
| `SECRET_KEY`, `JWT_SECRET` | Login tokens (two **different** random values) | Everyone has to sign in again (no data loss) |
| `DATA_ENCRYPTION_KEY` | Encrypts farmers' bank account numbers | **Bank numbers can never be read again.** Back it up separately |
| `SQL_SERVER_PASSWORD` | Database `sa` password | Reset needed |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | MinIO administrator | Reset needed |
| `MINIO_KMS_SECRET_KEY` | Encrypts documents on disk | **Documents can never be read again.** Back it up separately |
| `OBJECT_STORAGE_ACCESS_KEY` / `SECRET_KEY` | The app's own MinIO login (no delete rights) | Reset needed |
| `BOOTSTRAP_ADMIN_PASSWORD` | First Platform Admin (must be changed at first sign-in) | Use another admin to reset |

---

## 4. Step-by-step: Level A on one Ubuntu server

All commands run on the server over SSH. The example domain is `carbon.yourcompany.in`; replace it with yours everywhere.

### Step 1 — Create the server

1. Create an Ubuntu Server 24.04 LTS VM with the size in Section 3.1, in an India region.
2. Attach a static public IP.
3. In the cloud firewall / security group, allow only **22 (your IP), 80 and 443** (Section 3.5).
4. Sign in: `ssh ubuntu@<server-ip>`.

### Step 2 — Install Docker and Git

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install git ca-certificates curl
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
exit                                   # sign out and back in so the docker group applies
```

Sign in again and check:

```bash
docker --version                       # 27.x or newer
docker compose version                 # v2.24.4 or newer
```

### Step 3 — Server firewall (extra safety)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

> Docker-published ports bypass `ufw`. That is why Step 7 removes every published port except Caddy's 80 and 443.

### Step 4 — DNS

At your domain provider, create an **A record**: `carbon.yourcompany.in` → `<server public IP>`. Then check it from the server:

```bash
getent hosts carbon.yourcompany.in      # must print the server's public IP
```

### Step 5 — Download the code (the two repositories must sit side by side)

`docker-compose.yml` builds the frontend from `../carbon_project_frontend`, so the folder layout must be exactly this:

```
/opt/carbon/
├── carbon-platform/            backend repository
└── carbon_project_frontend/    frontend repository
```

```bash
sudo mkdir -p /opt/carbon && sudo chown $USER /opt/carbon && cd /opt/carbon
git clone https://github.com/leelakumarakula/carbon_platform_new.git carbon-platform
git clone https://github.com/charan14111411/carbon_project_frontend.git carbon_project_frontend
cd carbon-platform        && git checkout main    # or the release branch you want to host
cd ../carbon_project_frontend && git checkout main
```

> Host the branch that holds the tested code. Today the latest work is on `fixes_14/10` in both repositories; merge it
> into `main` first, or check out `fixes_14/10` on both.

### Step 6 — Create the settings file `.env`

The file goes in the **backend repository root** (`/opt/carbon/carbon-platform/.env`). Docker Compose reads it from there.

**6a. Generate the secrets** (copy each output into the file below):

```bash
openssl rand -base64 48 | tr -d '\n/+='; echo          # SECRET_KEY
openssl rand -base64 48 | tr -d '\n/+='; echo          # JWT_SECRET   (run again, must be different)
openssl rand -base64 32 | tr '+/' '-_'                 # DATA_ENCRYPTION_KEY (44 characters, ends with =)
echo "Sq1-$(openssl rand -base64 18 | tr -d '\n/+=')"  # SQL_SERVER_PASSWORD (has upper, lower, digit, symbol)
openssl rand -base64 24 | tr -d '\n/+='; echo          # MINIO_ROOT_PASSWORD
echo "carbon-key:$(openssl rand -base64 32)"           # MINIO_KMS_SECRET_KEY
openssl rand -base64 24 | tr -d '\n/+='; echo          # OBJECT_STORAGE_SECRET_KEY
openssl rand -base64 24 | tr -d '\n/+='; echo          # OBJECT_STORAGE_DELETE_SECRET_KEY
```

Do not use the `$` character in any value: Docker Compose would treat it as a variable.

**6b. Create the file** with `nano /opt/carbon/carbon-platform/.env` and fill in this content:

```ini
# ---------- mode ----------
APP_ENV=staging
LOG_FORMAT=json
LOG_LEVEL=INFO

# ---------- login security ----------
SECRET_KEY=<generated>
JWT_SECRET=<generated, different>
JWT_KEY_ID=k1
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=7
REFRESH_COOKIE_SECURE=true
DATA_ENCRYPTION_KEY=<generated Fernet key>

# ---------- database (host, user and driver are set by docker-compose.yml) ----------
DATABASE_URL=
SQL_SERVER_DATABASE=carbon_platform
SQL_SERVER_PASSWORD=<generated>

# ---------- address ----------
CORS_ORIGINS=https://carbon.yourcompany.in

# ---------- documents (MinIO) ----------
OBJECT_STORAGE_REGION=us-east-1
OBJECT_STORAGE_BUCKET_PREFIX=carbon
OBJECT_STORAGE_ACCESS_KEY=carbon-app
OBJECT_STORAGE_SECRET_KEY=<generated>
OBJECT_STORAGE_DELETE_ACCESS_KEY=carbon-cleanup
OBJECT_STORAGE_DELETE_SECRET_KEY=<generated>
MINIO_ROOT_USER=carbon-admin
MINIO_ROOT_PASSWORD=<generated>
MINIO_KMS_SECRET_KEY=<generated, starts with carbon-key:>
MAX_UPLOAD_BYTES=15728640
MALWARE_SCANNER=signature

# ---------- rate limits (shared through Redis) ----------
RATE_LIMIT_BACKEND=redis
LOGIN_RATE_LIMIT_PER_MINUTE=10
MAX_FAILED_LOGINS=5
LOCKOUT_MINUTES=15

# ---------- background jobs ----------
JOB_ENVIRONMENTS=LIVE

# ---------- first administrator (used once by bootstrap-admin) ----------
BOOTSTRAP_ADMIN_EMAIL=admin@yourcompany.in
BOOTSTRAP_ADMIN_PASSWORD=<at least 12 characters, letters and digits>

# ---------- providers ----------
SATELLITE_PROVIDER=planetary-computer
LAB_PROVIDER=manual
REGISTRY_PROVIDER=manual
PAYMENT_PROVIDER=manual
WEATHER_PROVIDER=open-meteo
SOIL_PROVIDER=soilgrids
FARMFUTURE_PROVIDER=farmfuture
NOTIFICATION_EXTERNAL_DELIVERY=disabled

# ---------- maps (replace with licensed sources for production) ----------
MAP_TILE_PROVIDER=osm
MAP_TILE_URL=https://tile.openstreetmap.org/{z}/{x}/{y}.png
MAP_TERRAIN_URL=https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png
MAP_SATELLITE_URL=https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}

# ---------- operations ----------
OPERATIONAL_RETENTION_DAYS=60
DISK_WARN_FREE_MB=2048
DISK_CRITICAL_FREE_MB=1024
```

What you do **not** set here, because `docker-compose.yml` sets it:
- SQL Server host, port, user (`sa`) and driver (ODBC 18)
- `REDIS_URL`
- `STORAGE_BACKEND=s3` and the MinIO address
- `TRUSTED_PROXIES`

Leave `DEMO_USER_PASSWORD` out: demo data must never be seeded on a hosted server.

**6c. Protect the file:**

```bash
chmod 600 /opt/carbon/carbon-platform/.env
```

Then copy `DATA_ENCRYPTION_KEY` and `MINIO_KMS_SECRET_KEY` into your company password manager **now**.

### Step 7 — Add the hosting files (HTTPS + closed ports)

Create two files next to `docker-compose.yml` in `/opt/carbon/carbon-platform/`.

**7a. `Caddyfile`** gives HTTPS and forwards everything to the frontend container:

```
carbon.yourcompany.in {
    encode gzip
    reverse_proxy frontend:80
}
```

**7b. `docker-compose.prod.yml`** adjusts the base file for hosting. It does four things:
- Closes every internal port.
- Switches SQL Server to the free Express edition.
- Restarts containers automatically.
- Adds Caddy.

```yaml
# Hosting override: docker compose -f docker-compose.yml -f docker-compose.prod.yml ...
services:
  sqlserver:
    environment:
      MSSQL_PID: Express            # free edition, licensed for production use (10 GB per database)
    ports: !reset []
    restart: unless-stopped
  redis:
    ports: !reset []
    restart: unless-stopped
  minio:
    ports: !reset []
    restart: unless-stopped
  backend:
    environment:
      CORS_ORIGINS: https://carbon.yourcompany.in
    ports: !reset []
    restart: unless-stopped
  worker:
    restart: unless-stopped
  beat:
    restart: unless-stopped
  frontend:
    ports: !reset []
    restart: unless-stopped
  caddy:
    image: caddy:2.8-alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on: [frontend]
    restart: unless-stopped

volumes:
  caddy_data:
  caddy_config:
```

To save typing, make a shortcut for the rest of this guide:

```bash
cd /opt/carbon/carbon-platform
echo "alias dc='docker compose -f docker-compose.yml -f docker-compose.prod.yml'" >> ~/.bashrc && source ~/.bashrc
```

> **Client IP addresses** (used for rate limits and the audit log) are already handled. The containers get addresses from
> `172.28.0.128/25`, and the backend trusts `X-Forwarded-For` only from that range (`TRUSTED_PROXIES`). Caddy and nginx are
> both inside it. If `172.28.0.0/24` clashes with your cloud network, change `subnet`, `ip_range`, `gateway` and
> `TRUSTED_PROXIES` together in `docker-compose.yml`.

### Step 8 — Build and start

```bash
cd /opt/carbon/carbon-platform
dc up -d --build                 # first build takes 5–10 minutes
dc ps                            # every service "running"; minio-init "exited (0)"
```

`minio-init` is a one-time job. It creates the private, versioned, encrypted buckets `carbon-live` / `carbon-demo` and the
app's MinIO user, then stops. That is normal.

### Step 9 — Create the database and the first administrator

```bash
dc exec backend python manage.py setup              # creates the DB, runs every migration, loads roles/permissions
dc exec backend python manage.py bootstrap-admin    # creates BOOTSTRAP_ADMIN_EMAIL as Platform Admin
dc restart worker beat                              # workers start cleanly now that the schema exists
```

Then remove `BOOTSTRAP_ADMIN_PASSWORD` from `.env` (it is used only once).

**Never run `seed-demo` on a hosted server.**

### Step 10 — Check that it works

| Check | Command or action | Expected |
|---|---|---|
| HTTPS certificate | Open `https://carbon.yourcompany.in` | Padlock, sign-in page |
| API alive | `curl -s https://carbon.yourcompany.in/api/v1/health/live` | `{"status":"alive"}` |
| API ready | `curl -s https://carbon.yourcompany.in/api/v1/health/ready` | `"status":"ready"`; `details` explains any check that is not `ok` |
| Sign in | Sign in as the bootstrap admin | Asked to change the password, then the dashboard |
| Uploads | Upload any evidence photo | Saved; scan status **NOT_SCANNED** (expected at Level A) |
| Workers | Administration → Background jobs | Worker heartbeat shown, jobs complete |
| Internal ports closed | From your laptop: `nc -zv <server-ip> 1433` (also 6379, 9000, 8000) | Refused / timed out |

### Step 11 — Set up the platform for use

The new database is empty apart from roles and the platform organization. As the admin, in the app:
1. Create organizations: developer, laboratory, VVB, buyer and the registry organizations (VREG / GSREG / ICMREG).
2. Create users and assign roles. Keep separation of duties: for example, the methodology author and approver must be two
   different people.
3. Create standards (VCS, GS, CCTS) and activities.
4. Create the methodologies and versions. Attach the calculation module, submit with the source and effective date,
   and have a second specialist approve. These are the same steps used on the test database.

The test-database scripts that did steps 3–4 via the API (`add_gs_ccts.py`, `add_verra.py`) can be pointed at the hosted
URL to do it in one go. Ask the development team.

---

## 5. Optional: move the current test data to the server

Use this only if you want the test projects online. For real use, a **fresh** database (Section 4) is cleaner.

1. On the Windows machine (SSMS): back up `dmrv_db1` to a `.bak` file, and zip `carbon-platform\storage\local-dev`.
2. Copy both to the server (`scp`).
3. Restore into the container:
   ```bash
   dc cp dmrv_db1.bak sqlserver:/var/opt/mssql/dmrv_db1.bak
   dc exec sqlserver /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "<SQL_SERVER_PASSWORD>" -Q \
     "RESTORE FILELISTONLY FROM DISK='/var/opt/mssql/dmrv_db1.bak'"   # note the two logical file names
   dc exec sqlserver /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "<SQL_SERVER_PASSWORD>" -Q \
     "RESTORE DATABASE dmrv_db1 FROM DISK='/var/opt/mssql/dmrv_db1.bak' WITH MOVE '<data name>' TO '/var/opt/mssql/data/dmrv_db1.mdf', MOVE '<log name>' TO '/var/opt/mssql/data/dmrv_db1_log.ldf'"
   ```
4. In `.env` set `SQL_SERVER_DATABASE=dmrv_db1`, and use the **same `DATA_ENCRYPTION_KEY`** as the Windows `backend/.env`
   (otherwise bank numbers cannot be read).
5. `dc up -d`, then `dc exec backend python manage.py migrate`.
6. Copy the documents into MinIO. Put the unzipped folder into the backend container, then run the migration
   (a dry run first):
   ```bash
   dc cp local-dev backend:/tmp/local-dev
   dc exec -e LOCAL_STORAGE_ROOT=/tmp/local-dev backend python manage.py storage-migrate --dry-run
   dc exec -e LOCAL_STORAGE_ROOT=/tmp/local-dev backend python manage.py storage-migrate
   ```
   It checks every file's SHA-256 and never deletes the originals.

---

## 6. Day-to-day operations

| Task | Command (from `/opt/carbon/carbon-platform`) |
|---|---|
| See what is running | `dc ps` |
| Follow API logs | `dc logs -f --tail 200 backend` |
| Worker logs | `dc logs -f --tail 200 worker` |
| Restart the API | `dc restart backend` |
| Stop everything | `dc down` (data stays in Docker volumes) |
| Start everything | `dc up -d` |
| Health | `curl -s https://carbon.yourcompany.in/api/v1/health/ready` |
| Jobs back after a Redis/worker outage | `dc exec backend python manage.py jobs-recover` |
| Disk space | `df -h` and `docker system df` |

**Never** run `docker compose down -v`: `-v` deletes the database and document volumes.

The data lives in the Docker volumes `carbon-platform_sqldata` (database), `carbon-platform_miniodata` (documents) and
`carbon-platform_caddy_data` (certificates).

---

## 7. Backups (Level A)

What must be backed up:
1. the database;
2. the documents;
3. the `.env` file (stored separately, in the password manager).

**7a. Nightly script.** Create `/opt/carbon/backup.sh`:

```bash
#!/bin/sh
set -eu
cd /opt/carbon/carbon-platform
SQL_SERVER_PASSWORD=$(grep '^SQL_SERVER_PASSWORD=' .env | cut -d= -f2-)
SQL_SERVER_DATABASE=$(grep '^SQL_SERVER_DATABASE=' .env | cut -d= -f2-)
D=$(date +%Y%m%d-%H%M)
mkdir -p /opt/carbon/backups
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T sqlserver /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa \
  -P "$SQL_SERVER_PASSWORD" -Q "BACKUP DATABASE [$SQL_SERVER_DATABASE] TO DISK='/var/opt/mssql/backup-$D.bak' WITH CHECKSUM, INIT"
docker compose -f docker-compose.yml -f docker-compose.prod.yml cp sqlserver:/var/opt/mssql/backup-$D.bak /opt/carbon/backups/
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T sqlserver rm /var/opt/mssql/backup-$D.bak
docker run --rm -v carbon-platform_miniodata:/data:ro -v /opt/carbon/backups:/b alpine tar czf /b/documents-$D.tgz -C /data .
find /opt/carbon/backups -type f -mtime +14 -delete      # keep 14 days on the server
```

```bash
chmod 700 /opt/carbon/backup.sh
(crontab -l 2>/dev/null; echo "30 1 * * * /opt/carbon/backup.sh >> /opt/carbon/backup.log 2>&1") | crontab -
```

**7b. Copy the backups off the server every day.** Send them to a cloud storage bucket in another region (for example with
`rclone` or the cloud provider's CLI). A backup that stays only on the same server is lost together with the server.

**7c. Test a restore once a month.** Restore the `.bak` into a scratch database and open a few records.

Notes:
- SQL Server Express does not support backup compression, so the script does not use it.
- The documents are encrypted on disk with `MINIO_KMS_SECRET_KEY`. Without that key the document backup is useless.

---

## 8. Updating to a new version

```bash
cd /opt/carbon/carbon-platform
/opt/carbon/backup.sh                                # 1. backup first
git pull && (cd ../carbon_project_frontend && git pull)
dc build                                             # 2. new images
dc up -d                                             # 3. restart with the new code
dc exec backend python manage.py migrate             # 4. database changes
dc exec backend python manage.py seed-reference      # 5. new roles/permissions (safe to repeat)
curl -s https://carbon.yourcompany.in/api/v1/health/ready
```

If the new version is broken:
1. `git checkout <previous commit>` in both repositories, then `dc up -d --build`.
2. If a migration must be undone, restore the backup from step 1. Do not use `alembic downgrade` on real data.

---

## 9. Security checklist (Level A)

- [ ] Only ports 22 (your IP), 80 and 443 are open; `nc` checks in Step 10 fail for 1433/6379/9000/8000.
- [ ] `.env` is `chmod 600`; not in Git; `DATA_ENCRYPTION_KEY` and `MINIO_KMS_SECRET_KEY` saved in the password manager.
- [ ] `REFRESH_COOKIE_SECURE=true`, `APP_ENV=staging`, `JOB_ENVIRONMENTS=LIVE`, no `DEMO_USER_PASSWORD`, `seed-demo` never run.
- [ ] The bootstrap admin changed their password; `BOOTSTRAP_ADMIN_PASSWORD` removed from `.env`.
- [ ] SSH: key login only (`PasswordAuthentication no` in `/etc/ssh/sshd_config`).
- [ ] Ubuntu security updates: `sudo apt -y install unattended-upgrades`.
- [ ] Nightly backup runs, is copied off the server, and a restore has been tested.
- [ ] Users know uploads are **not virus-scanned** at Level A.

---

## 10. Moving to Level B (full production)

With `APP_ENV=production` the backend **checks all of the following at start-up and refuses to start** if any is missing.

| # | Requirement | What to provide | Owner |
|---|---|---|---|
| 1 | **Antivirus adapter** | Choose a commercial scanning API. A developer writes the adapter and registers it (`register_scanner`). Then set `MALWARE_SCANNER`, `ANTIVIRUS_ENDPOINT` and `ANTIVIRUS_API_KEY` | Business + developer |
| 2 | Secret store | All secrets as files in `SECRETS_DIR` (one file per setting). `.env` is not read, and secrets in environment variables are refused | DevOps |
| 3 | Object storage over HTTPS | `OBJECT_STORAGE_ENDPOINT=https://...`, MinIO with KES/KMS (not the single-key mode), versioning, replication to a second site | DevOps |
| 4 | Redis with TLS + ACL user | `REDIS_URL=rediss://<user>:<password>@host:6380/0`, `noeviction`, AOF on; the user must not be `default` | DevOps |
| 5 | SQL Server with a trusted TLS certificate | `SQL_SERVER_TRUST_SERVER_CERTIFICATE=false`. The connection always uses `Encrypt=yes` | DBA |
| 6 | Least-privilege database login | The app login has no `sysadmin` and no DDL rights. Migrations run as a separate deploy step with a DDL login | DBA |
| 7 | Rate limits in Redis | `RATE_LIMIT_BACKEND=redis` (already set at Level A) | — |
| 8 | JSON logs, no SQL echo | `LOG_FORMAT=json`, `DB_ECHO=false` (already set at Level A) | — |
| 9 | Retention at least 60 days | `OPERATIONAL_RETENTION_DAYS>=60` (already set) | — |
| 10 | No simulated providers | No `*_PROVIDER` may be mock / fake / test / stub / demo (the current `manual` values are fine) | — |

Not checked at start-up, but required for go-live (`docs/production-readiness.md`):
- SQL Server **Standard** licence, FULL recovery model, SQL Agent backup jobs (`ops/sqlserver/backup-jobs.sql`): log every 5 min,
  diff every 6 h, full weekly, encrypted, to an off-site **object-locked** bucket (60 days).
- A restore drill that meets the targets: **RPO 15 min, RTO 1 h**.
- A monitoring platform that collects the JSON logs, scrapes `GET /metrics` (with `METRICS_TOKEN`, at least 32 characters) and
  routes the alerts listed in `docs/operations-runbook.md`.
- Licensed or self-hosted map tiles.
- Workers on Linux with `-Q default,maintenance` and **exactly one** beat.

Detailed references in the repository:
- `docs/deployment.md`
- `docs/production-readiness.md`
- `docs/operations-runbook.md`
- `docs/runtime-hardening.md`
- `docs/storage-and-scanning.md`
- `docs/background-jobs.md`
- `docs/object-storage-recovery.md`

---

## 11. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `dc` says `set SQL_SERVER_PASSWORD in .env` | `.env` missing or not in the backend repository root | Create it as in Step 6 |
| `!reset` error | Docker Compose older than 2.24.4 | Update Docker (Step 2) |
| Frontend build fails: path not found | Repositories not side by side | Layout in Step 5 |
| No HTTPS / certificate error | DNS not pointing to the server yet, or port 80 closed | Check Step 4 and the firewall; `dc logs caddy` |
| Backend restarts in a loop | A setting is invalid; the first log line names it | `dc logs backend` and fix `.env` |
| `sqlserver` unhealthy | Password too weak, or less than 2 GB RAM free | Strong password (upper, lower, digit, symbol); more RAM |
| Sign-in works, then you are logged out at once | Site opened over `http://` with `REFRESH_COOKIE_SECURE=true` | Always use `https://` |
| `429 Too Many Requests` at sign-in | Login rate limit (10/min) or lockout after 5 wrong passwords | Wait 15 minutes, or an admin unlocks the user |
| Upload answers `503 STORAGE_UNAVAILABLE` | MinIO down or `minio-init` failed | `dc logs minio minio-init`; `dc up -d` |
| Upload answers `503 DISK_SPACE_LOW` | Less than 1 GB free | Free disk space / resize; never delete database files by hand |
| Jobs stay QUEUED | Worker or Redis down | `dc ps`, `dc restart worker beat`, then `manage.py jobs-recover` |
| Map is grey | Browser cannot reach the tile server, or tile licence/usage limit reached | Check `MAP_TILE_URL`; use a licensed tile service |

---

## 12. What was and was not verified for this guide

| Item | Status |
|---|---|
| Settings, start-up checks and production guards | Taken from the code (`backend/app/core/config.py`) |
| Frontend production build (`ng build --configuration production`) | **Built successfully** on 28-10-2026 |
| Backend + frontend + SQL Server running together | Verified daily on the Windows development machine (without Docker) |
| `docker-compose.yml`, the override file, Caddy and the backup script | **Not run yet**: Docker is not installed on the development machine. Do a first run on a test server and fix anything that comes up before inviting users |
| Level B infrastructure (secret store, antivirus, KES, Redis TLS, monitoring) | Not provisioned; listed as pending in `docs/production-readiness.md` |
