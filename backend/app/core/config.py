"""Application settings, loaded from environment variables / backend/.env (never committed).

Production (Phase 12B D30): secrets come ONLY from files mounted by the self-hosted secret store under SECRETS_DIR (one file per
setting, named like the setting, e.g. rendered by the secret store's agent / sidecar). In production the `.env` file is not read at
all, and a secret supplied as a plain environment variable is refused at start-up. Development and tests keep `.env`.
"""
import ipaddress
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, PydanticBaseSettingsSource, SettingsConfigDict
from sqlalchemy.engine import URL

# Settings that are secrets (D30). In production each must come from the secret-store mount, never from an environment variable.
SECRET_SETTINGS = ("SECRET_KEY", "JWT_SECRET", "JWT_PREVIOUS_KEYS", "DATA_ENCRYPTION_KEY", "DATA_ENCRYPTION_PREVIOUS_KEYS",
                   "DATABASE_URL", "SQL_SERVER_PASSWORD", "REDIS_URL", "RATE_LIMIT_REDIS_URL", "OBJECT_STORAGE_SECRET_KEY",
                   "OBJECT_STORAGE_DELETE_SECRET_KEY", "ANTIVIRUS_API_KEY", "SMTP_PASSWORD", "METRICS_TOKEN",
                   "BOOTSTRAP_ADMIN_PASSWORD", "DEMO_USER_PASSWORD", "COPERNICUS_CLIENT_SECRET")
_SQL_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}")
# Provider names that denote a simulated / test implementation (D38): never acceptable in production.
MOCK_PROVIDER_NAMES = frozenset({"mock", "fake", "test", "stub", "dummy", "simulated", "simulator", "demo"})


def _production_env() -> bool:
    return os.environ.get("APP_ENV", "").strip().lower() == "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "development"  # development | test | production
    APP_NAME: str = "Carbon Platform API"
    API_PREFIX: str = "/api/v1"

    SECRET_KEY: str = Field(min_length=32)
    JWT_SECRET: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "carbon-platform"
    ACCESS_TOKEN_MINUTES: int = 15
    REFRESH_TOKEN_DAYS: int = 7
    REFRESH_COOKIE_NAME: str = "cp_refresh"
    REFRESH_COOKIE_SECURE: bool = False

    # Database: either a full DATABASE_URL (split into the parts below by _split_database_url) or the SQL_SERVER_* parts.
    DATABASE_URL: str | None = None
    SQL_SERVER_HOST: str = "localhost"
    SQL_SERVER_PORT: int | None = 1433  # empty = let the driver choose (e.g. shared memory to a local instance)
    SQL_SERVER_DATABASE: str = "carbon_platform"
    SQL_SERVER_USERNAME: str | None = None
    SQL_SERVER_PASSWORD: str | None = None
    SQL_SERVER_DRIVER: str = "ODBC Driver 17 for SQL Server"
    SQL_SERVER_TRUSTED_CONNECTION: bool = False
    SQL_SERVER_TRUST_SERVER_CERTIFICATE: bool = True
    DB_ECHO: bool = False

    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:4200"]

    # Abuse protection. Existing limits (login per IP and per IP+email, global per IP, DB lockout) are unchanged.
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10
    GLOBAL_RATE_LIMIT_PER_MINUTE: int = 600
    MAX_FAILED_LOGINS: int = 5
    LOCKOUT_MINUTES: int = 15
    MAX_REQUEST_BYTES: int = 25 * 1024 * 1024   # enforced on the streamed body (chunked bodies included), not only Content-Length
    # Phase 12B D19 (locked values; per minute). Uploads and per-user / per-organization limits apply to authenticated requests;
    # the API burst limit is one deployment-wide ceiling over all API requests (interpretation of "job / API burst", documented).
    REFRESH_RATE_LIMIT_PER_MINUTE: int = 100        # per client IP (F5)
    UPLOAD_RATE_LIMIT_PER_MINUTE: int = 100         # per user, multipart uploads
    USER_RATE_LIMIT_PER_MINUTE: int = 1000          # per user, all authenticated API requests
    ORGANIZATION_RATE_LIMIT_PER_MINUTE: int = 5000  # per organization of the caller, all authenticated API requests
    API_BURST_RATE_LIMIT_PER_MINUTE: int = 10000    # whole deployment, all API requests
    # D18 / D20: "memory" (one process: development / tests) or "redis" (shared; required in production). Redis outage = fail open.
    RATE_LIMIT_BACKEND: str = "memory"
    RATE_LIMIT_REDIS_URL: str | None = None         # default: REDIS_URL (use a separate ACL user, see docs/runtime-hardening.md)
    RATE_LIMIT_KEY_PREFIX: str = "rl"
    RATE_LIMIT_REDIS_TIMEOUT_SECONDS: float = 0.5
    RATE_LIMIT_REDIS_RETRY_SECONDS: float = 5.0
    # D21: reverse proxies whose X-Forwarded-For is trusted (IPs or CIDRs). Empty = X-Forwarded-For is ignored entirely.
    TRUSTED_PROXIES: Annotated[list[str], NoDecode] = []

    API_ACCESS_LOG_ENABLED: bool = True

    # Seeding (read only by manage.py; never used at request time)
    BOOTSTRAP_ADMIN_EMAIL: str | None = None
    BOOTSTRAP_ADMIN_PASSWORD: str | None = None
    BOOTSTRAP_ADMIN_NAME: str = "Platform Administrator"
    DEMO_USER_PASSWORD: str | None = None

    # Personal-data protection. DATA_ENCRYPTION_KEY is a Fernet key (32 url-safe base64 bytes) used for
    # field-level encryption of bank account numbers. Generate: python -c "from cryptography.fernet import
    # Fernet; print(Fernet.generate_key().decode())". Losing it makes encrypted values unreadable.
    DATA_ENCRYPTION_KEY: str = Field(min_length=44)
    # D30 rotation: earlier Fernet keys still accepted for decryption (MultiFernet); `manage.py rotate-data-key` re-encrypts with
    # DATA_ENCRYPTION_KEY, after which the old keys are removed. Comma separated.
    DATA_ENCRYPTION_PREVIOUS_KEYS: Annotated[list[str], NoDecode] = []
    # D30 JWT signing-key rotation: tokens carry `kid` = JWT_KEY_ID and are signed with JWT_SECRET; JWT_PREVIOUS_KEYS ("kid:secret",
    # comma separated) still verify until their tokens expire (ACCESS_TOKEN_MINUTES), then are removed.
    JWT_KEY_ID: str = "k1"
    JWT_PREVIOUS_KEYS: Annotated[list[str], NoDecode] = []
    # D30: directory of secret files mounted by the self-hosted secret store (required in production; no vendor chosen)
    SECRETS_DIR: str | None = None

    # Documents / object storage (Phase 12B D2–D11). "local" stores files under LOCAL_STORAGE_ROOT (development / test only);
    # "s3" is the S3-compatible MinIO backend (stdlib SigV4 client): one private, versioned bucket per data environment named
    # "<OBJECT_STORAGE_BUCKET_PREFIX>-<live|demo>", server-side encryption (SSE-S3) required on every object.
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_ROOT: str | None = None
    MAX_UPLOAD_BYTES: int = 15 * 1024 * 1024
    # Antivirus (Phase 12B D12–D17). "signature" = EICAR/test-signature check only (development / test / DEMO, reported NOT_SCANNED);
    # production requires a commercial scanner adapter registered under MALWARE_SCANNER with ANTIVIRUS_ENDPOINT / ANTIVIRUS_API_KEY.
    # No vendor is selected yet: the vendor adapter is a deployment prerequisite (docs/storage-and-scanning.md).
    MALWARE_SCANNER: str = "signature"
    ANTIVIRUS_ENDPOINT: str | None = None
    ANTIVIRUS_API_KEY: str | None = None
    ANTIVIRUS_TIMEOUT_SECONDS: int = 30

    # GIS (technical tolerances, not business rules — see docs/farmer-workflow.md)
    FARM_OVERLAP_MIN_AREA_M2: float = 1.0      # shared edges produce ~0 m² numeric slivers; below this = touching
    FARM_AREA_WARNING_HA: float = 1000.0       # warning only: unusually large single farm, likely a digitising error
    FARM_DECLARED_AREA_WARNING_PCT: float = 25.0  # warning only: declared vs measured area differ by more than this
    FARM_MAX_VERTICES: int = 5000

    # Basemap tiles for the map components (decision D6). The browser loads tiles directly from this URL
    # template; it is configuration, not business logic. The default is OpenStreetMap's public server, which is
    # for development only (usage policy: attribution, no heavy use) — set a licensed/self-hosted source for production.
    MAP_TILE_PROVIDER: str = "osm-dev"
    MAP_TILE_URL: str = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    MAP_TILE_ATTRIBUTION: str = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    MAP_TILE_MAX_ZOOM: int = 19
    MAP_TILE_SUBDOMAINS: str = ""
    # 3D view terrain (elevation) tiles for the map components — display only, never used for any area or business rule.
    # Default: the public AWS "Terrain Tiles" dataset (terrarium encoding), for development only; production sets a licensed /
    # self-hosted DEM source. Empty URL = the 3D view still tilts / rotates, but without relief.
    MAP_TERRAIN_URL: str = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
    MAP_TERRAIN_ENCODING: str = "terrarium"     # terrarium | mapbox (how elevation is packed in the PNG)
    MAP_TERRAIN_MAX_ZOOM: int = 15
    MAP_TERRAIN_ATTRIBUTION: str = 'Elevation: <a href="https://registry.opendata.aws/terrain-tiles/">AWS Terrain Tiles</a>'
    # 3D view satellite imagery draped on the terrain — display only. Default: Esri World Imagery, for development only
    # (production use needs an ArcGIS licence or a licensed / self-hosted imagery source). Empty URL = no satellite option.
    MAP_SATELLITE_URL: str = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    MAP_SATELLITE_MAX_ZOOM: int = 18
    MAP_SATELLITE_ATTRIBUTION: str = "Imagery &copy; Esri, Maxar, Earthstar Geographics, and the GIS User Community"

    # MRV / sampling (technical tolerances, not methodology rules)
    # Field-collection PLATFORM DEFAULTS (decisions S1, S2) — not methodology requirements. A methodology version's SAMPLING
    # rule may override them; the values used are frozen on each design version / collection record (services/field_rules.py).
    GPS_MAX_DISTANCE_M: float = 30.0          # collection GPS further than this from the planned point needs a note
    FIELD_CHECKLIST_VERSION: str = "PLATFORM-DEFAULT-2"   # Phase 6: label with the SMP sample code
    FIELD_MIN_PHOTOS_PER_SAMPLE: int = 1
    # Baseline control sites (VM0042 v2.2 §8.2 Quantification Approach 2, Table 7): a control site must lie within this
    # distance of every project stratum it represents, and its mean annual precipitation within this tolerance.
    CONTROL_SITE_MAX_DISTANCE_KM: float = 250.0
    CONTROL_SITE_PRECIPITATION_TOLERANCE_MM: float = 100.0
    # Phase 7 (decision A18): calculations run synchronously; a run with more frozen input rows than this is BLOCKED
    # (INPUT_TOO_LARGE) instead of holding an HTTP request open. Background execution is deferred.
    CALCULATION_MAX_INPUT_ROWS: int = 20000
    # Phase 8A (B11): reports are generated synchronously; a run whose report would exceed this many rows (inputs + outputs +
    # findings + QA reviews) is refused (REPORT_TOO_LARGE). Background report generation is deferred (Phase 12).
    CALCULATION_REPORT_MAX_ROWS: int = 20000
    # Decision V1 (platform governance, not a methodology rule): approving an MRV plan with CONFIGURATION_REQUIRED gaps is
    # allowed (with an audited acknowledgement) for DEMO projects and outside production only. No production exception exists.
    SAMPLING_MAX_ATTEMPTS_PER_POINT: int = 400  # rejection-sampling attempts per requested point before giving up
    SAMPLING_DUPLICATE_DISTANCE_M: float = 1.0  # two points closer than this in one period are duplicates

    # Which farms may join a project (decision P3, kept as implemented in Phase 3). Only SAME_ORGANIZATION is
    # supported; a partner-organization policy needs a business decision (partnership model, consent, rights).
    PROJECT_FARM_ORG_POLICY: str = "SAME_ORGANIZATION"

    # Later-phase integrations (configured now so .env.example is complete)
    REDIS_URL: str | None = None
    REDIS_CA_CERT: str | None = None                      # CA bundle for a private-CA rediss:// endpoint (D23)
    OBJECT_STORAGE_ENDPOINT: str | None = None            # e.g. https://minio.internal:9000 (path-style; TLS required in production)
    OBJECT_STORAGE_REGION: str = "us-east-1"              # SigV4 signing region (MinIO default)
    OBJECT_STORAGE_ACCESS_KEY: str | None = None          # application identity: put / get / head / list — no delete permission (D8)
    OBJECT_STORAGE_SECRET_KEY: str | None = None
    OBJECT_STORAGE_DELETE_ACCESS_KEY: str | None = None   # separate identity used ONLY by the orphan-deletion job (D10); unset = no deletion
    OBJECT_STORAGE_DELETE_SECRET_KEY: str | None = None
    OBJECT_STORAGE_BUCKET_PREFIX: str = "carbon"          # buckets: <prefix>-live, <prefix>-demo (one private bucket per environment)
    OBJECT_STORAGE_CA_CERT: str | None = None             # CA bundle for a private TLS endpoint
    OBJECT_STORAGE_TIMEOUT_SECONDS: int = 30
    # D38: runtime providers are MANUAL (no simulated provider exists at runtime; test doubles live in the test suite only).
    SATELLITE_PROVIDER: str = "manual"   # manual | planetary-computer (Microsoft, no key) | copernicus (needs COPERNICUS_CLIENT_*)
    LAB_PROVIDER: str = "manual"         # laboratories use the laboratory workspace (NoLimsAdapter)
    REGISTRY_PROVIDER: str = "manual"
    PAYMENT_PROVIDER: str = "manual"   # Phase 10 D15 / D33: manual until a contracted provider exists; no mock provider at all
    # External farm reference data (evidence only: fetched on request, stored append-only, never an input to a workflow or a calculation).
    WEATHER_PROVIDER: str = "open-meteo"      # open-meteo (historical reanalysis, no key) | none
    SOIL_PROVIDER: str = "soilgrids"          # soilgrids (ISRIC SoilGrids 2.0, no key) | none
    LAND_RECORDS_PROVIDER: str = "manual"     # no public land-records API exists; land records are uploaded as documents
    OPEN_METEO_ARCHIVE_URL: str = "https://archive-api.open-meteo.com/v1/archive"
    SOILGRIDS_URL: str = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    COPERNICUS_TOKEN_URL: str = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"  # noqa: S105
    COPERNICUS_STATISTICS_URL: str = "https://sh.dataspace.copernicus.eu/api/v1/statistics"
    COPERNICUS_CLIENT_ID: str | None = None
    COPERNICUS_CLIENT_SECRET: str | None = None
    SATELLITE_MAX_CLOUD_PCT: int = 30
    PLANETARY_COMPUTER_STAC_URL: str = "https://planetarycomputer.microsoft.com/api/stac/v1"
    PLANETARY_COMPUTER_DATA_URL: str = "https://planetarycomputer.microsoft.com/api/data/v1"
    SATELLITE_PLOT_MAX_CLOUD_PCT: int = 10     # a scene is skipped when more than this share of the plot is cloud / shadow
    SATELLITE_MAX_SCENES: int = 6              # least-cloudy scenes checked per fetch (each costs 3 statistics calls)
    EXTERNAL_DATA_TIMEOUT_SECONDS: int = 30

    # Phase 12A background jobs. SQL Server is the system of record; REDIS_URL is only the Celery broker (transport). Without it,
    # jobs stay QUEUED in SQL Server (publication is retried by the recovery tick) and lazy expiry keeps the platform correct.
    # Intervals are operational defaults (seconds), not business rules; retention is NOT configured here (no policy exists).
    JOB_ENVIRONMENTS: Annotated[list[str], NoDecode] = ["LIVE", "DEMO"]   # data environments scheduled jobs run for
    JOB_MAX_RETRIES: int = 3                  # bounded retries of transient failures (non-retryable errors fail at once)
    JOB_RETRY_BACKOFF_SECONDS: int = 60       # deterministic exponential backoff base: 60, 120, 240 … (capped at 1 h)
    JOB_STALE_AFTER_SECONDS: int = 1800       # lease: a CLAIMED / RUNNING job older than this is recovered (> every task time limit)
    JOB_BATCH_SIZE: int = 200                 # rows per sweep batch (each row in its own short transaction)
    JOB_EXPIRY_INTERVAL: int = 600            # reservation / order / listing expiry sweeps (10 min)
    JOB_ORPHAN_SCAN_INTERVAL: int = 86400     # orphan stored-file scan (daily)
    JOB_ORPHAN_GRACE_HOURS: int = 24          # a file younger than this is never an orphan candidate (uploads in flight)
    JOB_RETENTION_INTERVAL: int = 86400       # retention purge (daily): Phase 12B-III operational-retention policies
    JOB_RECOVERY_INTERVAL: int = 60           # recovery tick: republish unpublished jobs, requeue due retries, recover stale leases
    JOB_HEARTBEAT_SECONDS: int = 30           # worker heartbeat into SQL Server
    JOB_RESCAN_INTERVAL: int = 86400          # Phase 12B D15: background rescan of documents not yet scanned CLEAN by a real scanner

    # Phase 12B D44 / D43: structured logs and platform-neutral metrics (no monitoring vendor selected).
    LOG_FORMAT: str = "json"                  # json | text (text only for local reading)
    LOG_LEVEL: str = "INFO"
    METRICS_TOKEN: str | None = None          # bearer token for GET /metrics; unset = the endpoint is disabled

    # Phase 12B D39 / D41 / D42: SMTP is the selected FUTURE external channel. Delivery is DEFERRED: the only accepted value is
    # "disabled". SMTP settings are configuration for the boundary only; nothing is sent.
    NOTIFICATION_EXTERNAL_DELIVERY: str = "disabled"

    # Phase 12B-III operations. D48: operational records (access logs, read notifications, stopped worker heartbeats, temporary
    # files) are purged after this many days; append-only / financial / credit / audit / verification records are never purged.
    OPERATIONAL_RETENTION_DAYS: int = 60
    # Disk-space safety (operational defaults, not business SLAs): below WARN readiness is degraded; below CRITICAL readiness fails,
    # local uploads and local backup / restore drills are refused before they can exhaust the disk.
    DISK_WARN_FREE_MB: int = 2048
    DISK_CRITICAL_FREE_MB: int = 1024
    # D26: production SQL Server backups go off-host (BACKUP TO URL, S3-compatible bucket with object lock) and are encrypted with a
    # server certificate. Names only — the credential and certificate live in SQL Server / the secret store.
    BACKUP_URL: str | None = None                     # e.g. s3://backup-store.internal/carbon-sql-backups (no host invented)
    BACKUP_ENCRYPTION_CERT: str | None = None         # name of the server certificate in master
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str | None = None
    SMTP_STARTTLS: bool = True

    @classmethod
    def settings_customise_sources(cls, settings_cls: type[BaseSettings], init_settings: PydanticBaseSettingsSource,
                                   env_settings: PydanticBaseSettingsSource, dotenv_settings: PydanticBaseSettingsSource,
                                   file_secret_settings: PydanticBaseSettingsSource) -> tuple[PydanticBaseSettingsSource, ...]:
        if _production_env():                     # D30: production never reads .env
            return init_settings, env_settings, file_secret_settings
        return init_settings, env_settings, dotenv_settings, file_secret_settings

    @model_validator(mode="before")
    @classmethod
    def _split_database_url(cls, data: Any) -> Any:
        """DATABASE_URL wins: it is split into the SQL_SERVER_* parts so create-db, `master` connections, backups / drills and the
        `_test` database switch keep working from one URL. No user in the URL = Windows authentication."""
        raw = data.get("DATABASE_URL") if isinstance(data, dict) else None
        if not raw:
            return data
        from sqlalchemy.engine import make_url
        u = make_url(raw)
        if not u.drivername.startswith("mssql") or not u.host or not u.database:
            raise ValueError("DATABASE_URL must look like mssql+pyodbc://[user:password]@host[\\instance][:port]/database?driver=...")
        q = {k.lower(): v for k, v in u.query.items() if isinstance(v, str)}
        driver = q.get("driver", "ODBC Driver 18 for SQL Server")
        if re.fullmatch(r"ODBC Driver \d+", driver.strip(), re.IGNORECASE):   # "ODBC Driver 18" -> the installed driver's full name
            driver = f"{driver.strip()} for SQL Server"
        trusted = not u.username or q.get("trusted_connection", "").lower() == "yes"
        return {**data, "SQL_SERVER_HOST": u.host, "SQL_SERVER_PORT": u.port, "SQL_SERVER_DATABASE": u.database,
                "SQL_SERVER_USERNAME": None if trusted else u.username, "SQL_SERVER_PASSWORD": None if trusted else u.password,
                "SQL_SERVER_DRIVER": driver, "SQL_SERVER_TRUSTED_CONNECTION": trusted,
                "SQL_SERVER_TRUST_SERVER_CERTIFICATE": q.get("trustservercertificate", "yes").lower() == "yes"}

    @field_validator("SQL_SERVER_PORT", "METRICS_TOKEN", "COPERNICUS_CLIENT_ID", "COPERNICUS_CLIENT_SECRET", mode="before")
    @classmethod
    def _empty_is_unset(cls, v: object) -> object:
        return None if v == "" else v                                # `METRICS_TOKEN=` as in .env.example = unset (endpoint disabled)

    @field_validator("TRUSTED_PROXIES", "DATA_ENCRYPTION_PREVIOUS_KEYS", "JWT_PREVIOUS_KEYS", mode="before")
    @classmethod
    def _split_list(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip().startswith("["):
            return [e.strip() for e in v.split(",") if e.strip()]
        return v

    @field_validator("JOB_ENVIRONMENTS", mode="before")
    @classmethod
    def _split_environments(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip().startswith("["):
            return [e.strip().upper() for e in v.split(",") if e.strip()]
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip().startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        if self.is_production:
            if not self.REFRESH_COOKIE_SECURE:
                raise ValueError("REFRESH_COOKIE_SECURE must be true in production")
            if self.SECRET_KEY == self.JWT_SECRET:
                raise ValueError("SECRET_KEY and JWT_SECRET must differ in production")
        if not set(self.JOB_ENVIRONMENTS) <= {"LIVE", "DEMO"}:
            raise ValueError("JOB_ENVIRONMENTS may contain only LIVE and DEMO")
        intervals = (self.JOB_EXPIRY_INTERVAL, self.JOB_ORPHAN_SCAN_INTERVAL, self.JOB_RETENTION_INTERVAL, self.JOB_RECOVERY_INTERVAL,
                     self.JOB_HEARTBEAT_SECONDS, self.JOB_RESCAN_INTERVAL)
        floors = (self.JOB_MAX_RETRIES, self.JOB_BATCH_SIZE - 1, self.JOB_RETRY_BACKOFF_SECONDS, self.JOB_ORPHAN_GRACE_HOURS)
        if min(floors) < 0 or min(intervals) < 30:
            raise ValueError("Job settings out of range (intervals are at least 30 s; batch size at least 1)")
        if self.STORAGE_BACKEND not in ("local", "s3"):
            raise ValueError("STORAGE_BACKEND must be 'local' or 's3'")
        if self.STORAGE_BACKEND == "s3" and not (self.OBJECT_STORAGE_ENDPOINT and self.OBJECT_STORAGE_ACCESS_KEY and self.OBJECT_STORAGE_SECRET_KEY):
            raise ValueError("STORAGE_BACKEND=s3 needs OBJECT_STORAGE_ENDPOINT, OBJECT_STORAGE_ACCESS_KEY and OBJECT_STORAGE_SECRET_KEY")
        if self.is_production:
            if self.STORAGE_BACKEND != "s3" or not (self.OBJECT_STORAGE_ENDPOINT or "").startswith("https://"):
                raise ValueError("Production requires STORAGE_BACKEND=s3 with an https:// OBJECT_STORAGE_ENDPOINT (MinIO, D2 / D5)")
            if self.MALWARE_SCANNER == "signature" or not (self.ANTIVIRUS_ENDPOINT and self.ANTIVIRUS_API_KEY):
                raise ValueError("Production requires a real antivirus scanner (MALWARE_SCANNER, ANTIVIRUS_ENDPOINT, ANTIVIRUS_API_KEY; D13 / D17)")
        if self.JOB_STALE_AFTER_SECONDS < 900:
            raise ValueError("JOB_STALE_AFTER_SECONDS must exceed every task time limit (at least 900 s)")
        self._runtime_guards()
        return self

    def _runtime_guards(self) -> None:
        """Phase 12B-II start-up validation (D18-D23, D30, D38, D39-D44, D47)."""
        limits = (self.REFRESH_RATE_LIMIT_PER_MINUTE, self.UPLOAD_RATE_LIMIT_PER_MINUTE, self.USER_RATE_LIMIT_PER_MINUTE,
                  self.ORGANIZATION_RATE_LIMIT_PER_MINUTE, self.API_BURST_RATE_LIMIT_PER_MINUTE, self.LOGIN_RATE_LIMIT_PER_MINUTE,
                  self.GLOBAL_RATE_LIMIT_PER_MINUTE)
        if min(limits) < 1 or self.MAX_REQUEST_BYTES < 1024:
            raise ValueError("Rate limits must be at least 1 per minute and MAX_REQUEST_BYTES at least 1 KiB")
        if self.RATE_LIMIT_BACKEND not in ("memory", "redis"):
            raise ValueError("RATE_LIMIT_BACKEND must be 'memory' or 'redis'")
        if self.RATE_LIMIT_BACKEND == "redis" and not (self.RATE_LIMIT_REDIS_URL or self.REDIS_URL):
            raise ValueError("RATE_LIMIT_BACKEND=redis needs RATE_LIMIT_REDIS_URL or REDIS_URL")
        for cidr in self.TRUSTED_PROXIES:
            try:
                net = ipaddress.ip_network(cidr, strict=False)
            except ValueError as e:
                raise ValueError(f"TRUSTED_PROXIES: {cidr!r} is not an IP address or CIDR") from e
            if net.prefixlen == 0:
                raise ValueError("TRUSTED_PROXIES must not trust every address (0.0.0.0/0 or ::/0) (D21)")
        _validate_rotation_keys(self.DATA_ENCRYPTION_KEY, self.DATA_ENCRYPTION_PREVIOUS_KEYS, self.JWT_KEY_ID, self.JWT_PREVIOUS_KEYS)
        if self.MAP_TERRAIN_ENCODING not in ("terrarium", "mapbox"):
            raise ValueError("MAP_TERRAIN_ENCODING must be 'terrarium' or 'mapbox'")
        if self.LOG_FORMAT not in ("json", "text"):
            raise ValueError("LOG_FORMAT must be 'json' or 'text'")
        if self.NOTIFICATION_EXTERNAL_DELIVERY != "disabled":
            raise ValueError("External notification delivery is deferred (D39 / D41): NOTIFICATION_EXTERNAL_DELIVERY must be 'disabled'")
        if self.OPERATIONAL_RETENTION_DAYS < 1 or not 0 < self.DISK_CRITICAL_FREE_MB < self.DISK_WARN_FREE_MB:
            raise ValueError("OPERATIONAL_RETENTION_DAYS must be >= 1 and 0 < DISK_CRITICAL_FREE_MB < DISK_WARN_FREE_MB")
        if self.BACKUP_ENCRYPTION_CERT and not _SQL_NAME.fullmatch(self.BACKUP_ENCRYPTION_CERT):
            raise ValueError("BACKUP_ENCRYPTION_CERT must be a plain SQL Server certificate name")
        if self.BACKUP_URL and not self.BACKUP_URL.startswith("s3://"):
            raise ValueError("BACKUP_URL must be an s3:// URL (SQL Server 2022 BACKUP TO URL, S3-compatible object storage)")
        if self.SECRETS_DIR and not Path(self.SECRETS_DIR).is_dir():
            raise ValueError("SECRETS_DIR does not exist or is not a directory")
        if self.WEATHER_PROVIDER not in ("open-meteo", "none") or self.SOIL_PROVIDER not in ("soilgrids", "none"):
            raise ValueError("WEATHER_PROVIDER must be 'open-meteo' or 'none'; SOIL_PROVIDER must be 'soilgrids' or 'none'")
        if self.SATELLITE_PROVIDER == "copernicus" and not (self.COPERNICUS_CLIENT_ID and self.COPERNICUS_CLIENT_SECRET):
            raise ValueError("SATELLITE_PROVIDER=copernicus needs COPERNICUS_CLIENT_ID and COPERNICUS_CLIENT_SECRET")
        if self.SATELLITE_PROVIDER not in ("manual", "planetary-computer", "copernicus") and \
                self.SATELLITE_PROVIDER.strip().lower() not in MOCK_PROVIDER_NAMES:      # simulated names: refused in production below (D38)
            raise ValueError("SATELLITE_PROVIDER must be manual, planetary-computer or copernicus")
        if not 0 <= self.SATELLITE_PLOT_MAX_CLOUD_PCT <= 100 or not 1 <= self.SATELLITE_MAX_SCENES <= 20:
            raise ValueError("SATELLITE_PLOT_MAX_CLOUD_PCT must be 0-100 and SATELLITE_MAX_SCENES 1-20")
        for name in ("OPEN_METEO_ARCHIVE_URL", "SOILGRIDS_URL", "COPERNICUS_TOKEN_URL", "COPERNICUS_STATISTICS_URL", "PLANETARY_COMPUTER_STAC_URL",
                     "PLANETARY_COMPUTER_DATA_URL"):
            if not str(getattr(self, name)).startswith("https://"):
                raise ValueError(f"{name} must be an https:// URL")
        if not 0 <= self.SATELLITE_MAX_CLOUD_PCT <= 100 or not 1 <= self.EXTERNAL_DATA_TIMEOUT_SECONDS <= 120:
            raise ValueError("SATELLITE_MAX_CLOUD_PCT must be 0-100 and EXTERNAL_DATA_TIMEOUT_SECONDS 1-120")
        if not self.is_production:
            return
        # ---- production only
        if self.LOG_FORMAT != "json":
            raise ValueError("Production logs must be structured JSON (D44)")
        for name in ("SATELLITE_PROVIDER", "LAB_PROVIDER", "REGISTRY_PROVIDER", "PAYMENT_PROVIDER", "WEATHER_PROVIDER", "SOIL_PROVIDER",
                     "LAND_RECORDS_PROVIDER"):
            if str(getattr(self, name)).strip().lower() in MOCK_PROVIDER_NAMES:
                raise ValueError(f"{name}={getattr(self, name)!r}: simulated providers are not allowed in production (D38)")
        if self.RATE_LIMIT_BACKEND != "redis":
            raise ValueError("Production requires RATE_LIMIT_BACKEND=redis: limits must be shared by every API process (D18)")
        for name in ("REDIS_URL", "RATE_LIMIT_REDIS_URL"):
            url = getattr(self, name)
            if url:
                _require_secure_redis(name, url)
        if not self.SECRETS_DIR:
            raise ValueError("Production requires SECRETS_DIR: secrets are mounted by the self-hosted secret store (D30)")
        plain = [n for n in SECRET_SETTINGS if getattr(self, n, None) and os.environ.get(n)]
        if plain:
            raise ValueError(f"Secrets supplied as plain environment variables are refused in production (D30): {', '.join(plain)}"
                             " - provide them as files under SECRETS_DIR")
        if self.METRICS_TOKEN is not None and len(self.METRICS_TOKEN) < 32:
            raise ValueError("METRICS_TOKEN must be at least 32 characters")
        if self.OPERATIONAL_RETENTION_DAYS < 60:
            raise ValueError("Production operational retention is at least 60 days (D48)")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    def database_url(self, database: str | None = None) -> str | URL:
        query = {"driver": self.SQL_SERVER_DRIVER}
        if self.SQL_SERVER_TRUST_SERVER_CERTIFICATE:
            query["TrustServerCertificate"] = "yes"
        if self.SQL_SERVER_TRUSTED_CONNECTION:
            query["Trusted_Connection"] = "yes"
        return URL.create(
            "mssql+pyodbc",
            username=None if self.SQL_SERVER_TRUSTED_CONNECTION else self.SQL_SERVER_USERNAME,
            password=None if self.SQL_SERVER_TRUSTED_CONNECTION else self.SQL_SERVER_PASSWORD,
            host=self.SQL_SERVER_HOST,
            port=self.SQL_SERVER_PORT,
            database=database or self.SQL_SERVER_DATABASE,
            query=query,
        )


def _require_secure_redis(name: str, url: str) -> None:
    """D22 / D23 / F8: self-hosted production Redis is reached over TLS with a dedicated ACL user and password."""
    u = urlsplit(url)
    if u.scheme != "rediss":
        raise ValueError(f"{name}: production Redis must use TLS (rediss://) (D23)")
    if not u.username or not u.password:
        raise ValueError(f"{name}: production Redis must authenticate with an ACL user and password (rediss://user:password@host) (D23)")
    if u.username == "default":
        raise ValueError(f"{name}: use a dedicated Redis ACL user, not 'default' (D23)")


def _validate_rotation_keys(primary: str, previous: list[str], kid: str, jwt_previous: list[str]) -> None:
    from cryptography.fernet import Fernet
    for k in [primary, *previous]:
        try:
            Fernet(k.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as e:
            raise ValueError("DATA_ENCRYPTION_KEY / DATA_ENCRYPTION_PREVIOUS_KEYS must be Fernet keys") from e
    if not kid or ":" in kid or "," in kid or len(kid) > 40:
        raise ValueError("JWT_KEY_ID must be a short identifier without ':' or ','")
    seen = {kid}
    for entry in jwt_previous:
        k, sep, secret = entry.partition(":")
        if not sep or not k or len(secret) < 32:
            raise ValueError("JWT_PREVIOUS_KEYS entries must be 'kid:secret' with a secret of at least 32 characters")
        if k in seen:
            raise ValueError(f"JWT key id {k!r} is used twice")
        seen.add(k)


def _settings_kwargs() -> dict[str, Any]:
    secrets_dir = os.environ.get("SECRETS_DIR")
    return {"_secrets_dir": secrets_dir} if secrets_dir else {}


@lru_cache
def get_settings() -> Settings:
    return Settings(**_settings_kwargs())  # type: ignore[call-arg]
