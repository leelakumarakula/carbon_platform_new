"""Farmer schemas. KYC identity numbers and bank account numbers are write-only: never returned."""
import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.schemas.common import Email, Reason, UtcDatetime, upper_code
from app.schemas.documents import DocumentOut

Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
Country = Annotated[str, StringConstraints(max_length=2), upper_code(r"[A-Z]{2}", "Country (ISO 3166-1 alpha-2)")]
Lang = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[a-z]{2,3}(-[A-Za-z]{2})?$")]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9 ()-]{6,30}$")]
TypeCode = Annotated[str, StringConstraints(max_length=40), upper_code(r"[A-Z][A-Z0-9_]{2,39}", "Type code")]
Gender = Literal["FEMALE", "MALE", "OTHER", "UNDISCLOSED"]
FarmerStatusValue = Literal["DRAFT", "REGISTERED", "KYC_PENDING", "KYC_VERIFIED", "ACTIVE", "SUSPENDED"]


class FarmerCreate(BaseModel):
    organization_id: uuid.UUID
    full_name: Name
    gender: Gender | None = None
    date_of_birth: date | None = None
    preferred_language: Lang | None = None
    participation_type: Literal["INDIVIDUAL", "GROUP_MEMBER"] = "INDIVIDUAL"
    group_organization_id: uuid.UUID | None = None
    address_line: LongText | None = None
    village: Text | None = None
    sub_district: Text | None = None
    district: Text | None = None
    state: Text | None = None
    postal_code: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = None
    country: Country
    primary_phone: Phone | None = None
    email: Email | None = None

    @field_validator("date_of_birth")
    @classmethod
    def _dob(cls, v: date | None) -> date | None:
        if v and (v > date.today() or v.year < 1900):
            raise ValueError("date of birth must be in the past")
        return v


class FarmerUpdate(BaseModel):
    full_name: Name | None = None
    gender: Gender | None = None
    date_of_birth: date | None = None
    preferred_language: Lang | None = None
    participation_type: Literal["INDIVIDUAL", "GROUP_MEMBER"] | None = None
    group_organization_id: uuid.UUID | None = None
    address_line: LongText | None = None
    village: Text | None = None
    sub_district: Text | None = None
    district: Text | None = None
    state: Text | None = None
    postal_code: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = None


class FarmerStatusChange(BaseModel):
    status: Literal["REGISTERED", "ACTIVE", "SUSPENDED"]
    reason: Reason


class ContactIn(BaseModel):
    contact_type: Literal["PHONE", "EMAIL", "ALTERNATE_PHONE", "ADDRESS"]
    value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=320)]
    label: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None
    is_primary: bool = False


class KycSubmit(BaseModel):
    id_type: Literal["NATIONAL_ID", "VOTER_ID", "TAX_ID", "PASSPORT", "DRIVING_LICENSE", "OTHER"]
    id_number: Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=40),
                         Field(description="Write-only. Only the last 4 characters and a keyed fingerprint are stored.")]
    document_id: uuid.UUID


class KycDecision(BaseModel):
    decision: Literal["VERIFIED", "RETURNED"]
    notes: Reason
    acknowledge_possible_duplicate: bool = False


class ConsentIn(BaseModel):
    consent_type: TypeCode
    consent_text_version: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    language: Lang | None = None
    capture_method: Literal["PAPER_SIGNED", "DIGITAL_SIGNATURE", "VERBAL_RECORDED", "OTP", "ONLINE_CHECKBOX"]
    document_id: uuid.UUID | None = None


class ConsentDefinitionIn(BaseModel):
    consent_type: TypeCode
    title: Name
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    text_version: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)] | None = None
    required_for_activation: bool = False


class ConsentDefinitionOut(BaseModel):
    id: uuid.UUID
    consent_type: str
    version: int
    title: str
    description: str | None
    text_version: str | None
    required_for_activation: bool
    status: str
    created_at: UtcDatetime
    retired_at: UtcDatetime | None


class AgreementCreate(BaseModel):
    agreement_type: TypeCode
    template_version: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    counterparty_organization_id: uuid.UUID | None = None
    terms_summary: Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)] | None = None
    effective_from: date | None = None
    effective_to: date | None = None


class AgreementSign(BaseModel):
    signed_document_id: uuid.UUID
    signature_method: Literal["PAPER_SIGNED", "DIGITAL_SIGNATURE", "THUMBPRINT", "OTP"]


class AgreementStatusChange(BaseModel):
    status: Literal["TERMINATED", "EXPIRED", "VOID"]
    reason: Reason


class BankAccountIn(BaseModel):
    account_holder_name: Name
    bank_name: Name
    branch_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    routing_code: Annotated[str, StringConstraints(max_length=30), upper_code(r"[A-Z0-9]{4,30}", "Routing code")]
    account_number: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9 -]{6,40}$"),
                              Field(description="Write-only. Stored encrypted; only the last 4 digits are ever shown.")]
    is_primary: bool = True
    proof_document_id: uuid.UUID | None = None


class BankDecision(BaseModel):
    decision: Literal["VERIFIED", "REJECTED"]
    notes: Reason


class LinkUser(BaseModel):
    user_id: uuid.UUID


# ---------------------------------------------------------------- outputs
class ContactOut(BaseModel):
    id: uuid.UUID
    contact_type: str
    value: str
    label: str | None
    is_primary: bool
    is_active: bool
    created_at: UtcDatetime


class ConsentOut(BaseModel):
    id: uuid.UUID
    consent_type: str
    consent_definition_id: uuid.UUID | None = None
    version: int | None = None                     # consent definition version this grant refers to
    required_for_activation: bool = False
    is_current_version: bool = False               # granted against the currently active definition
    granted: bool = False
    granted_at: UtcDatetime | None = None
    consent_text_version: str
    language: str | None
    capture_method: str
    document_id: uuid.UUID | None
    status: str
    captured_at: UtcDatetime
    captured_by: uuid.UUID | None
    withdrawn_at: UtcDatetime | None
    withdrawal_reason: str | None


class AgreementOut(BaseModel):
    id: uuid.UUID
    agreement_number: str
    agreement_type: str
    template_version: str
    counterparty_organization_id: uuid.UUID
    terms_summary: str | None
    effective_from: date | None
    effective_to: date | None
    status: str
    signed_at: UtcDatetime | None
    signature_method: str | None
    signed_document_id: uuid.UUID | None
    created_at: UtcDatetime


class BankAccountOut(BaseModel):
    id: uuid.UUID
    account_holder_name: str
    bank_name: str
    branch_name: str | None
    routing_code: str
    account_number_masked: str
    is_primary: bool
    status: str
    proof_document_id: uuid.UUID | None
    verified_at: UtcDatetime | None
    review_notes: str | None
    created_at: UtcDatetime


class KycOut(BaseModel):
    id_type: str | None
    id_number_masked: str | None
    document_id: uuid.UUID | None
    possible_duplicate: bool
    submitted_at: UtcDatetime | None
    submitted_by: uuid.UUID | None
    verified_at: UtcDatetime | None
    verified_by: uuid.UUID | None
    notes: str | None


class ChecklistItem(BaseModel):
    key: str
    label: str
    done: bool
    required: bool = True


class TransitionReadiness(BaseModel):
    target: str
    ready: bool
    items: list[ChecklistItem]


class FarmerSummary(BaseModel):
    id: uuid.UUID
    farmer_code: str
    full_name: str
    village: str | None
    district: str | None
    state: str | None
    country: str
    status: str
    organization_id: uuid.UUID
    organization_name: str | None
    environment: str
    farm_count: int
    created_at: UtcDatetime


class FarmerOut(FarmerSummary):
    group_organization_id: uuid.UUID | None
    user_id: uuid.UUID | None
    gender: str | None
    date_of_birth: date | None
    preferred_language: str | None
    participation_type: str
    address_line: str | None
    sub_district: str | None
    postal_code: str | None
    updated_at: UtcDatetime
    kyc: KycOut
    contacts: list[ContactOut]
    consents: list[ConsentOut]
    agreements: list[AgreementOut]
    bank_accounts: list[BankAccountOut]
    documents: list[DocumentOut]
    allowed_transitions: list[str]
    readiness: list[TransitionReadiness]
    can_manage: bool
    can_verify_kyc: bool
    can_manage_bank: bool
    can_verify_bank: bool
    is_self: bool
