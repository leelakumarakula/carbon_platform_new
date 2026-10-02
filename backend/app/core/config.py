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

    # Later-phase integrations (configured now so .env.example is complete)
    REDIS_URL: str | None = None
    OBJECT_STORAGE_ENDPOINT: str | None = None
    OBJECT_STORAGE_ACCESS_KEY: str | None = None
    OBJECT_STORAGE_SECRET_KEY: str | None = None
    OBJECT_STORAGE_BUCKET: str | None = None
    SATELLITE_PROVIDER: str = "mock"
    LAB_PROVIDER: str = "mock"
    REGISTRY_PROVIDER: str = "manual"
    PAYMENT_PROVIDER: str = "mock"

    @field_validator("SQL_SERVER_PORT", mode="before")
    @classmethod
    def _empty_port(cls, v: object) -> object:
        return None if v == "" else v

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
