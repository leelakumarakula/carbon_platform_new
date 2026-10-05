# Fresh setup: new database → migrations → first admin → ready to test

This takes you from an **empty SQL Server database** to a running platform with one Platform Admin. Then follow [e2e-test-flow.md](e2e-test-flow.md) to test the whole flow.

Run every backend command from the **`backend`** folder; the settings file `.env` is read from there.

## 1. Prerequisites

| Tool | Version / note |
|---|---|
| Python | 3.12 |
| Node.js | 20.19+ or 22 (Angular 21) |
| SQL Server | any edition, with a database you created (e.g. `CC`) |
| ODBC driver | **ODBC Driver 18 for SQL Server** (or 17, named in the URL) |
| Git | to get the code |

Your Windows account (or the SQL login you use) must be able to `ALTER DATABASE` and create tables in your database.

## 2. Get the code

```powershell
git clone <repo-url> carbon_platform_new      # or: git pull, on the branch you test
cd carbon_platform_new
```

The migrations are part of the code: `backend/alembic/versions/` (0001 … 0019). You don't run SQL scripts by hand.

## 3. Backend: Python environment

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements\dev.txt
```

## 4. Backend: settings file `backend/.env`

Copy the template, then edit it:
```powershell
copy ..\.env.example .env
```

**Fill in these lines:**

| Setting | Value |
|---|---|
| `DATABASE_URL` | Your database. Windows login: `mssql+pyodbc://@localhost\SQL_LOCAL/CC?driver=ODBC+Driver+18`. Replace `localhost\SQL_LOCAL` with your server\instance and `CC` with your database name. SQL login: `mssql+pyodbc://user:password@localhost/CC?driver=ODBC+Driver+18`. |
| `SECRET_KEY` | output of command **A** below |
| `JWT_SECRET` | output of command **A** again (a *different* value) |
| `DATA_ENCRYPTION_KEY` | output of command **B** below |
| `BOOTSTRAP_ADMIN_EMAIL` | your admin email, e.g. `admin@cc.example.com` |
| `BOOTSTRAP_ADMIN_PASSWORD` | a temporary password: **12+ characters, letters and digits** (you change it at first sign-in) |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | `100` (you'll switch users a lot when testing; the default 10 locks you out) |
| `SATELLITE_PROVIDER` | `planetary-computer` (optional). This enables the farm's **External data → satellite** card with free Microsoft Planetary Computer data, no key needed: Sentinel-2 NDVI / NDMI, plot cloud %, and Landsat surface temperature. Leave it as `manual` to keep the card off. |

Generate the keys:
```powershell
# A: run twice, once for SECRET_KEY and once for JWT_SECRET
.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(48))"
# B: DATA_ENCRYPTION_KEY
.venv\Scripts\python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> ⚠️ **Two rules for `.env`:**
> - **Delete the `# comments` at the end of lines** you fill in, or put them on their own line. A trailing comment on an empty value breaks the setting.
> - With `DATABASE_URL` set, leave the `SQL_SERVER_*` lines as they are; the URL wins.
>
> Never commit `.env` or share it: it holds your keys.

## 5. Migrations and reference data

```powershell
.venv\Scripts\python manage.py setup
```

`setup` runs three steps:

| Step | What it does |
|---|---|
| `create-db` | Creates the database only if it's missing, so your existing one is kept. Turns on the snapshot isolation the app needs. |
| `migrate` | Runs all 19 migrations: about 140 tables, the append-only triggers and the sequences. |
| `seed-reference` | Adds the 96 permissions, 21 system roles, the **PLATFORM** organization, and the **Personal data processing** consent type. |

Expected last line:
```
reference data: {'permissions_added': 96, 'roles_added': 21, ..., 'consent_definitions_added': 0 or 1}
```

Check that the migrations are at the latest version:
```powershell
.venv\Scripts\alembic current        # shows: 0019 (head)
```

Every one of these commands is safe to run again; nothing is duplicated.

## 6. Create the first Platform Admin

```powershell
.venv\Scripts\python manage.py bootstrap-admin
```
Expected: `Created admin@cc.example.com (must change password at first sign-in)`.

This is the only account made from the command line. The admin creates every other organization and user in the UI.

## 7. Start the app (two terminals)

**Terminal 1, backend** (in `backend`):
```powershell
.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

**Terminal 2, frontend** (in `frontend`):
```powershell
npm install
npx ng serve
```

Open **http://localhost:4200** and sign in with the bootstrap email and temporary password. You're forced to set a new password, then you land on the dashboard.

## 8. Create the organizations and users (as admin, in the UI)

**Organizations: Administration → Organizations** (PLATFORM already exists):

| Code | Name | Type | Country |
|---|---|---|---|
| `DEV` | Green Farms Developer | Project developer | IN |
| `LAB` | Soil Test Lab | Laboratory | IN |
| `VVB` | Verify Co | VVB | IN |
| `BUY` | Buyer Co | Buyer (optional) | IN |

**Users: Administration → Users → New user.** Give each a temporary password; each user must change it at first sign-in.

| Email | Organization | Role |
|---|---|---|
| `pm@cc.example.com` | Green Farms Developer | Project Manager / Project Developer |
| `qa@cc.example.com` | Green Farms Developer | Data Quality / QA Officer |
| `gis@cc.example.com` | Green Farms Developer | GIS / Remote Sensing Specialist |
| `mrv@cc.example.com` | Green Farms Developer | MRV Manager |
| `sup@cc.example.com` | Green Farms Developer | Field Supervisor |
| `col@cc.example.com` | Green Farms Developer | Field Collector / Field Agent |
| `analyst@cc.example.com` | Green Farms Developer | Carbon Calculation Analyst |
| `meth1@cc.example.com` | **None (platform staff)** | Methodology Specialist |
| `meth2@cc.example.com` | **None (platform staff)** | Methodology Specialist |
| `labmgr@cc.example.com` | Soil Test Lab | Lab Manager / Lab QA |
| `labtech@cc.example.com` | Soil Test Lab | Lab Technician |
| `labqa@cc.example.com` | Soil Test Lab | Lab Manager / Lab QA |
| `vvb@cc.example.com` | Verify Co | VVB / ACVA Reviewer |

Why so many users? The platform enforces **separation of duties**: whoever submits something can never approve it. Most steps therefore need two or three different people.

✅ Check: sign in as `pm@`, set the new password, and the menu shows only the project-developer pages.

## 9. Test the flow

Continue with **[e2e-test-flow.md](e2e-test-flow.md)** from **Stage A** (catalog), through Stage I.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Data source name not found` / driver error | Install ODBC Driver 18, or put `driver=ODBC+Driver+17` in the URL |
| `Login failed` / `Cannot open database` | Check the server\instance and database name in `DATABASE_URL`; your Windows user needs access to that database |
| `SECRET_KEY ... at least 32 characters` | Fill in the keys with commands A and B (step 4) |
| `Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD` | Fill both in `.env`; run the command from the `backend` folder |
| Admin password rejected | 12+ characters, with letters and digits |
| "Too many sign-in attempts" | `LOGIN_RATE_LIMIT_PER_MINUTE=100`, then restart the backend |
| Login page shows a network error | The backend isn't running on port 8000 |
| A setting seems ignored | A trailing `# comment` on that line in `.env`; move it to its own line |

**Optional: backend self-test.** It uses a separate `<yourdb>_test` database that it creates itself; it never touches your data.
```powershell
.venv\Scripts\python -m pytest -q
```
