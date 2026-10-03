"""Application settings, loaded from environment variables / backend/.env (never committed)."""
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import URL


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

    # Database: either a full DATABASE_URL or the SQL_SERVER_* parts.
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

    # Abuse protection
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10
    GLOBAL_RATE_LIMIT_PER_MINUTE: int = 600
    MAX_FAILED_LOGINS: int = 5
    LOCKOUT_MINUTES: int = 15
    MAX_REQUEST_BYTES: int = 25 * 1024 * 1024

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

    # Documents / object storage. "local" stores files under LOCAL_STORAGE_ROOT (development only);
    # an S3-compatible backend (MinIO / AWS S3) is configured through OBJECT_STORAGE_* (see docs/deployment.md).
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_ROOT: str | None = None
    MAX_UPLOAD_BYTES: int = 15 * 1024 * 1024
    MALWARE_SCANNER: str = "signature"  # signature = EICAR/test-signature hook only; real AV adapter in Phase 12

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

    # MRV / sampling (technical tolerances, not methodology rules)
    # Field-collection PLATFORM DEFAULTS (decisions S1, S2) — not methodology requirements. A methodology version's SAMPLING
    # rule may override them; the values used are frozen on each design version / collection record (services/field_rules.py).
    GPS_MAX_DISTANCE_M: float = 30.0          # collection GPS further than this from the planned point needs a note
    FIELD_CHECKLIST_VERSION: str = "PLATFORM-DEFAULT-2"   # Phase 6: label with the SMP sample code
    FIELD_MIN_PHOTOS_PER_SAMPLE: int = 1
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
    OBJECT_STORAGE_ENDPOINT: str | None = None
    OBJECT_STORAGE_ACCESS_KEY: str | None = None
    OBJECT_STORAGE_SECRET_KEY: str | None = None
    OBJECT_STORAGE_BUCKET: str | None = None
    SATELLITE_PROVIDER: str = "mock"
    LAB_PROVIDER: str = "mock"
    REGISTRY_PROVIDER: str = "manual"
    PAYMENT_PROVIDER: str = "manual"   # Phase 10 D15 / D33: manual until a contracted provider exists; no mock provider at all

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
    JOB_RETENTION_INTERVAL: int = 86400       # retention purge infrastructure (daily; purges nothing until a policy exists)
    JOB_RECOVERY_INTERVAL: int = 60           # recovery tick: republish unpublished jobs, requeue due retries, recover stale leases
    JOB_HEARTBEAT_SECONDS: int = 30           # worker heartbeat into SQL Server

    @field_validator("SQL_SERVER_PORT", mode="before")
    @classmethod
    def _empty_port(cls, v: object) -> object:
        return None if v == "" else v

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
                     self.JOB_HEARTBEAT_SECONDS)
        floors = (self.JOB_MAX_RETRIES, self.JOB_BATCH_SIZE - 1, self.JOB_RETRY_BACKOFF_SECONDS, self.JOB_ORPHAN_GRACE_HOURS)
        if min(floors) < 0 or min(intervals) < 30:
            raise ValueError("Job settings out of range (intervals are at least 30 s; batch size at least 1)")
        if self.JOB_STALE_AFTER_SECONDS < 900:
            raise ValueError("JOB_STALE_AFTER_SECONDS must exceed every task time limit (at least 900 s)")
        return self

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    def database_url(self, database: str | None = None) -> str | URL:
        if self.DATABASE_URL and database is None:
            return self.DATABASE_URL
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


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
