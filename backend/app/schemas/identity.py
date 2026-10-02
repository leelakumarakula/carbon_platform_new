"""Schemas for auth, users, roles, organizations."""
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.common import Code, Email, ORMModel, Reason, RoleCode, UtcDatetime, upper_code

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9 ()-]{6,30}$")]
Country = Annotated[str, StringConstraints(max_length=2), upper_code(r"[A-Z]{2}", "Country (ISO 3166-1 alpha-2)")]
Secret = Annotated[str, StringConstraints(min_length=1, max_length=200)]
UserStatusValue = Literal["ACTIVE", "SUSPENDED", "DEACTIVATED"]
OrgStatusValue = Literal["ACTIVE", "SUSPENDED", "ARCHIVED"]
OrgTypeValue = Literal["PLATFORM", "PROJECT_DEVELOPER", "FIELD_PARTNER", "FARMER_GROUP", "LABORATORY", "VVB",
                       "REGISTRY", "BUYER"]


# ---------- auth ----------
class LoginRequest(BaseModel):
    email: Email
    password: Secret


class RefreshRequest(BaseModel):
    refresh_token: str | None = Field(default=None, max_length=200,
                                      description="Only for non-browser clients; browsers use the httpOnly cookie.")


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int
    must_change_password: bool


class ChangePasswordRequest(BaseModel):
    current_password: Secret
    new_password: Secret


# ---------- organizations ----------
class OrganizationSummary(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    org_type: str


class OrganizationOut(OrganizationSummary):
    country: str | None
    registration_number: str | None
    contact_email: str | None
    status: str
    environment: str
    member_count: int = 0
    created_at: UtcDatetime
    updated_at: UtcDatetime


class OrganizationCreate(BaseModel):
    code: Code
    name: Name
    org_type: OrgTypeValue
    country: Country | None = None
    registration_number: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    contact_email: Email | None = None


class OrganizationUpdate(BaseModel):
    name: Name | None = None
    country: Country | None = None
    registration_number: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    contact_email: Email | None = None


class OrgStatusChange(BaseModel):
    status: OrgStatusValue
    reason: Reason


class MemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str
    user_status: str
    title: str | None
    is_primary: bool
    joined_at: UtcDatetime


class MemberAdd(BaseModel):
    user_id: uuid.UUID
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    is_primary: bool = False


# ---------- roles ----------
class PermissionOut(ORMModel):
    code: str
    module: str
    name: str
    description: str | None


class RoleOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    scope: str
    is_system: bool
    permissions: list[str]
    assignment_count: int = 0


class RoleCreate(BaseModel):
    code: RoleCode
    name: Name
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None
    scope: Literal["PLATFORM", "ORGANIZATION"]
    permissions: list[str] = []


class RoleUpdate(BaseModel):
    name: Name | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None


class RolePermissionsUpdate(BaseModel):
    permissions: list[str]


# ---------- users ----------
class RoleGrantIn(BaseModel):
    role_code: Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, max_length=60)]
    organization_id: uuid.UUID | None = None


class RoleGrantOut(BaseModel):
    id: uuid.UUID
    role_code: str
    role_name: str
    scope: str
    organization_id: uuid.UUID | None
    organization_name: str | None
    assigned_at: UtcDatetime


class MembershipOut(BaseModel):
    organization_id: uuid.UUID
    organization_code: str
    organization_name: str
    org_type: str
    title: str | None
    is_primary: bool


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    status: str
    must_change_password: bool
    mfa_enabled: bool
    is_locked: bool
    locked_until: UtcDatetime | None
    last_login_at: UtcDatetime | None
    environment: str
    created_at: UtcDatetime
    updated_at: UtcDatetime
    roles: list[RoleGrantOut] = []
    organizations: list[MembershipOut] = []


class UserCreate(BaseModel):
    email: Email
    full_name: Name
    phone: Phone | None = None
    temporary_password: Secret
    organization_id: uuid.UUID | None = None
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    roles: list[RoleGrantIn] = []


class UserUpdate(BaseModel):
    full_name: Name | None = None
    phone: Phone | None = None


class UserStatusChange(BaseModel):
    status: UserStatusValue
    reason: Reason


class PasswordReset(BaseModel):
    temporary_password: Secret
    reason: Reason


class MeOut(BaseModel):
    user: UserOut
    permissions: list[str]
    platform_permissions: list[str]
