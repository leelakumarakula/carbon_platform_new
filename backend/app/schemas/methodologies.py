"""Methodology catalog, versioning, rules and project candidate-evaluation schemas (Phase 4)."""
import uuid
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.schemas.common import Reason, UtcDatetime, upper_code

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=300)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
Url = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500, pattern=r"^https?://\S+$")]
Code = Annotated[str, StringConstraints(max_length=40), upper_code(r"[A-Z][A-Z0-9_.-]{1,39}", "Code")]
FactKey = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[a-z][a-z0-9_]{1,59}$")]
Category = Literal["STANDARD", "ACTIVITY", "COUNTRY", "GEOGRAPHY", "LAND_USE", "HISTORICAL_PRACTICE", "CURRENT_PRACTICE", "PROPOSED_PRACTICE",
                   "START_DATE", "DATA_AVAILABILITY", "BASELINE", "ADDITIONALITY", "MONITORING", "QUANTIFICATION", "SAMPLING", "EVIDENCE",
                   "OTHER"]
Operator = Literal["EQUALS", "NOT_EQUALS", "IN", "NOT_IN", "ANY_IN", "ALL_IN", "NONE_IN", "GTE", "LTE", "BETWEEN", "DATE_ON_OR_AFTER",
                   "DATE_ON_OR_BEFORE", "IS_TRUE", "IS_FALSE", "EXISTS"]
Outcome = Literal["APPLICABLE", "NOT_APPLICABLE", "NEEDS_INFORMATION", "EVIDENCE_REQUIRED"]


# ---------------------------------------------------------------- catalog
class MethodologyIn(BaseModel):
    code: Code
    name: Name
    standard_id: uuid.UUID
    activity_ids: list[uuid.UUID] = Field(min_length=1)
    owner_name: Short | None = None
    description: Text | None = None
    source_url: Url | None = None
    environment: Literal["LIVE", "DEMO"] = "LIVE"


class MethodologyUpdate(BaseModel):
    name: Name | None = None
    owner_name: Short | None = None
    description: Text | None = None
    source_url: Url | None = None
    status: Literal["ACTIVE", "INACTIVE"] | None = None
    reason: Reason | None = None


class VersionIn(BaseModel):
    version_label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
    effective_from: date | None = None
    effective_to: date | None = None
    source_name: Short | None = None
    source_url: Url | None = None
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    based_on_version_id: uuid.UUID | None = None   # copy rules from an existing version of the same methodology

    @model_validator(mode="after")
    def _dates(self) -> "VersionIn":
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to is before effective_from.")
        return self


class VersionUpdate(BaseModel):
    effective_from: date | None = None
    effective_to: date | None = None
    source_name: Short | None = None
    source_url: Url | None = None
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class VersionTransition(BaseModel):
    reason: Reason
    supersedes_version_id: uuid.UUID | None = None   # on approval: the older APPROVED version this one replaces


class _RuleBase(BaseModel):
    rule_code: Code
    title: Name
    description: Text | None = None
    source_reference: Short | None = None
    sort_order: int = 0


class ApplicabilityRuleIn(_RuleBase):
    category: Category
    fact_key: FactKey
    operator: Operator
    expected_value: Any = None
    on_fail: Literal["NOT_APPLICABLE", "EVIDENCE_REQUIRED", "NEEDS_INFORMATION"] = "NOT_APPLICABLE"
    evidence_requirement: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None
    mandatory: bool = True


class MonitoringRuleIn(_RuleBase):
    parameter: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    # explicit provenance (decision V2-A); required — the platform never infers it. UNCLASSIFIED is not accepted for new rules.
    measurement_source: Literal["FIELD", "FIELD_ACTIVITY", "LABORATORY"]
    unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    frequency: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    method: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None
    evidence_requirement: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None
    data_level: Literal["PROJECT", "FARM", "STRATUM", "SAMPLING_POINT"] | None = None


class CalculationRuleIn(_RuleBase):
    step: Literal["BASELINE", "PROJECT", "EMISSIONS", "REMOVALS", "LEAKAGE", "UNCERTAINTY", "ADJUSTMENT", "NET"]
    equation_reference: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    parameters: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class GeneralRuleIn(_RuleBase):
    rule_type: Literal["CREDITING_PERIOD", "BASELINE", "ADDITIONALITY", "LEAKAGE", "UNCERTAINTY", "SAMPLING", "PERMANENCE", "GENERAL"]
    parameters: dict[str, Any] | None = None


RuleKind = Literal["applicability", "monitoring", "calculation", "general"]


class RuleOut(BaseModel):
    id: uuid.UUID
    kind: RuleKind
    rule_code: str
    title: str
    description: str | None
    source_reference: str | None
    sort_order: int
    data: dict[str, Any]          # kind-specific fields


class VersionOut(BaseModel):
    id: uuid.UUID
    methodology_id: uuid.UUID
    version_number: int
    version_label: str
    status: str
    effective_from: date | None
    effective_to: date | None
    source_name: str | None
    source_url: str | None
    source_document_id: uuid.UUID | None
    rules_version: int
    monitoring_rules_version: int
    calculation_rules_version: int
    calculation_readiness: str
    calculation_module_code: str | None = None
    is_demo_illustrative: bool
    notes: str | None
    based_on_version_id: uuid.UUID | None
    created_by: uuid.UUID | None
    created_at: UtcDatetime
    submitted_by: uuid.UUID | None
    submitted_at: UtcDatetime | None
    approved_by: uuid.UUID | None
    approved_at: UtcDatetime | None
    superseded_at: UtcDatetime | None
    superseded_by_id: uuid.UUID | None
    status_reason: str | None
    rule_counts: dict[str, int] = {}


class VersionDetail(VersionOut):
    methodology_code: str
    methodology_name: str
    readiness_request: dict[str, Any] | None = None   # open production-readiness request (requested_by, requested_at, evidence)
    rules: list[RuleOut]
    can_edit: bool
    can_submit: bool
    can_approve: bool


class MethodologyOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    standard_id: uuid.UUID
    standard_name: str | None
    activity_ids: list[uuid.UUID]
    owner_name: str | None
    description: str | None
    source_url: str | None
    status: str
    environment: str
    versions: list[VersionOut]


class ChangeOut(BaseModel):
    id: int
    methodology_version_id: uuid.UUID | None
    change_type: str
    summary: str
    reason: str | None
    changed_by: uuid.UUID | None
    changed_at: UtcDatetime
    request_id: str | None


# ---------------------------------------------------------------- project candidates
FactValue = str | int | float | bool | list[str] | None


class EvaluationIn(BaseModel):
    declared_facts: dict[FactKey, FactValue] = {}   # user-declared facts (recorded as DECLARED, never overrides system facts)


class RuleResultOut(BaseModel):
    rule_code: str
    title: str
    category: str
    fact_key: str
    operator: str
    expected: Any
    actual: Any
    fact_source: str | None
    check: str
    effect: str
    reason: str
    evidence_requirement: str | None
    source_reference: str | None


class CandidateOut(BaseModel):
    id: uuid.UUID
    methodology_id: uuid.UUID
    methodology_code: str
    methodology_name: str
    methodology_version_id: uuid.UUID
    version_label: str
    version_status: str
    calculation_readiness: str
    is_demo_illustrative: bool
    outcome: Outcome
    rules_version: int
    rules: list[RuleResultOut]
    evidence_requirements: list[str]
    reviews: list["ReviewOut"] = []


class EvaluationOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    engine_version: str
    facts: dict[str, Any]
    candidate_count: int
    evaluated_by: uuid.UUID | None
    evaluated_at: UtcDatetime
    candidates: list[CandidateOut]
    note: str = "Candidates are proposals from deterministic rules. A methodology specialist reviews and the project developer confirms."


class ReviewIn(BaseModel):
    evaluation_result_id: uuid.UUID
    recommendation: Literal["RECOMMENDED", "NOT_RECOMMENDED"]
    notes: Reason
    evidence_acknowledged: bool = False


class ReviewOut(BaseModel):
    id: uuid.UUID
    evaluation_result_id: uuid.UUID
    recommendation: str
    notes: str
    evidence_acknowledged: bool
    reviewed_by: uuid.UUID | None
    reviewer_name: str | None = None
    reviewed_at: UtcDatetime


class ConfirmIn(BaseModel):
    evaluation_result_id: uuid.UUID
    notes: Reason


class UnlockIn(BaseModel):
    reason: Reason


class ProjectMethodologyOut(BaseModel):
    id: uuid.UUID
    methodology_id: uuid.UUID
    methodology_code: str
    methodology_name: str
    methodology_version_id: uuid.UUID
    version_label: str
    version_status: str
    rules_version: int
    monitoring_rules_version: int
    calculation_rules_version: int
    calculation_readiness: str
    status: str
    confirmation_notes: str
    confirmed_by: uuid.UUID | None
    locked_at: UtcDatetime
    unlocked_at: UtcDatetime | None
    unlock_reason: str | None
    newer_version_available: bool = False


class ProjectMethodologyView(BaseModel):
    methodology_status: str
    project_status: str
    current: ProjectMethodologyOut | None
    history: list[ProjectMethodologyOut]
    latest_evaluation: EvaluationOut | None
    evaluation_count: int
    can_evaluate: bool
    can_review: bool
    can_confirm: bool
    can_unlock: bool
    findings: list[str] = []      # e.g. crediting-period checks configured by the locked version


CandidateOut.model_rebuild()


class CalculationModuleOption(BaseModel):
    """A registered calculation module as offered on a version's Calculation tab."""
    code: str
    version: str
    label: str
    methodology_code: str
    version_label: str
    readiness: str
    compatible: bool
    selected: bool
    calculation_rules: list[dict[str, Any]]
    monitoring_rules: list[dict[str, Any]]
    sampling_parameters: dict[str, Any]
    assumptions: list[str]
    variables: list[dict[str, Any]]


class ModuleSelectionIn(BaseModel):
    module_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)] | None
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]
