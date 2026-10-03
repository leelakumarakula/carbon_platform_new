"""Identity and access (spec section 7.1)."""
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Unicode, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Environment, Timestamped, UUIDPrimaryKey, in_check, utcnow


class OrganizationType(str, Enum):
    PLATFORM = "PLATFORM"
    PROJECT_DEVELOPER = "PROJECT_DEVELOPER"
    FIELD_PARTNER = "FIELD_PARTNER"
    FARMER_GROUP = "FARMER_GROUP"
    LABORATORY = "LABORATORY"
    VVB = "VVB"
    REGISTRY = "REGISTRY"
    BUYER = "BUYER"


class OrganizationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DEACTIVATED = "DEACTIVATED"
    SYSTEM = "SYSTEM"            # Phase 12A: non-login background-job actor (audit attribution only; no role, no password)


class RoleScope(str, Enum):
    PLATFORM = "PLATFORM"          # granted platform-wide (organization_id NULL)
    ORGANIZATION = "ORGANIZATION"  # granted within one organization


class Organization(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint(in_check("org_type", OrganizationType), name="org_type"),
        CheckConstraint(in_check("status", OrganizationStatus), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
    )
    code: Mapped[str] = mapped_column(Unicode(40), unique=True)
    name: Mapped[str] = mapped_column(Unicode(200))
    org_type: Mapped[str] = mapped_column(Unicode(30))
    country: Mapped[str | None] = mapped_column(Unicode(2))  # ISO 3166-1 alpha-2
    registration_number: Mapped[str | None] = mapped_column(Unicode(100))
    contact_email: Mapped[str | None] = mapped_column(Unicode(320))
    status: Mapped[str] = mapped_column(Unicode(20), default=OrganizationStatus.ACTIVE.value)
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)

    members: Mapped[list["OrganizationUser"]] = relationship(back_populates="organization")


class User(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(in_check("status", UserStatus), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
    )
    email: Mapped[str] = mapped_column(Unicode(320), unique=True)  # stored lower-case
    full_name: Mapped[str] = mapped_column(Unicode(200))
    phone: Mapped[str | None] = mapped_column(Unicode(30))
    password_hash: Mapped[str] = mapped_column(Unicode(255))
    status: Mapped[str] = mapped_column(Unicode(20), default=UserStatus.ACTIVE.value)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    password_changed_at: Mapped[datetime | None]
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    locked_until: Mapped[datetime | None]
    last_login_at: Mapped[datetime | None]
    # MFA-ready: secret is a reference into a secret store, never the raw secret.
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    mfa_secret_ref: Mapped[str | None] = mapped_column(Unicode(200))
    environment: Mapped[str] = mapped_column(Unicode(10), default=Environment.LIVE.value)

    roles: Mapped[list["UserRole"]] = relationship(back_populates="user", foreign_keys="UserRole.user_id",
                                                   cascade="all, delete-orphan")
    memberships: Mapped[list["OrganizationUser"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def is_locked(self, now: datetime | None = None) -> bool:
        return self.locked_until is not None and self.locked_until > (now or utcnow())


class Permission(UUIDPrimaryKey, Base):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(Unicode(80), unique=True)   # e.g. "users.manage"
    module: Mapped[str] = mapped_column(Unicode(40))
    name: Mapped[str] = mapped_column(Unicode(120))
    description: Mapped[str | None] = mapped_column(Unicode(500))


class Role(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "roles"
    __table_args__ = (CheckConstraint(in_check("scope", RoleScope), name="scope"),)
    code: Mapped[str] = mapped_column(Unicode(60), unique=True)
    name: Mapped[str] = mapped_column(Unicode(120))
    description: Mapped[str | None] = mapped_column(Unicode(1000))
    scope: Mapped[str] = mapped_column(Unicode(20))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))

    permissions: Mapped[list["RolePermission"]] = relationship(back_populates="role", cascade="all, delete-orphan")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
    granted_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))

    role: Mapped[Role] = relationship(back_populates="permissions")
    permission: Mapped[Permission] = relationship()


class UserRole(UUIDPrimaryKey, Base):
    """Role grant. organization_id NULL = platform-wide grant (only for PLATFORM-scope roles)."""
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", "organization_id"),)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))
    assigned_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    user: Mapped[User] = relationship(back_populates="roles", foreign_keys=[user_id])
    role: Mapped[Role] = relationship()
    organization: Mapped[Organization | None] = relationship()


class OrganizationUser(UUIDPrimaryKey, Base):
    __tablename__ = "organization_users"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str | None] = mapped_column(Unicode(120))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    joined_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))

    organization: Mapped[Organization] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class UserSession(UUIDPrimaryKey, Base):
    __tablename__ = "sessions"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    last_seen_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    revoked_reason: Mapped[str | None] = mapped_column(Unicode(100))
    ip_address: Mapped[str | None] = mapped_column(Unicode(64))
    user_agent: Mapped[str | None] = mapped_column(Unicode(400))

    def is_active(self, now: datetime | None = None) -> bool:
        now = now or utcnow()
        return self.revoked_at is None and self.expires_at > now


class RefreshToken(UUIDPrimaryKey, Base):
    """Only the SHA-256 hash of a refresh token is stored. Tokens rotate on every use."""
    __tablename__ = "refresh_tokens"
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(Unicode(64), unique=True)
    issued_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]
    replaced_by_id: Mapped[uuid.UUID | None]
    revoked_at: Mapped[datetime | None]


Index("ix_user_roles_organization_id", UserRole.organization_id)
