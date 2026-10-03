"""Status machines for every workflow entity (spec section 8, rule 7). Only listed transitions are allowed.

Transitions marked (assumption) are not spelled out in the spec; they are documented in
docs/farmer-workflow.md and listed as open questions in the phase report.
"""
from app.core.state_machine import StateMachine

USER_MACHINE = StateMachine.build(
    "user", initial="ACTIVE",
    transitions={"ACTIVE": {"SUSPENDED", "DEACTIVATED"}, "SUSPENDED": {"ACTIVE", "DEACTIVATED"}},
    terminal={"DEACTIVATED"},
)

ORGANIZATION_MACHINE = StateMachine.build(
    "organization", initial="ACTIVE",
    transitions={"ACTIVE": {"SUSPENDED", "ARCHIVED"}, "SUSPENDED": {"ACTIVE", "ARCHIVED"}},
    terminal={"ARCHIVED"},
)

# Spec: DRAFT → REGISTERED → KYC_PENDING → KYC_VERIFIED → ACTIVE → SUSPENDED.
# KYC_PENDING → REGISTERED (KYC returned for correction) and SUSPENDED → ACTIVE (reinstated) are assumptions.
FARMER_MACHINE = StateMachine.build(
    "farmer", initial="DRAFT",
    transitions={
        "DRAFT": {"REGISTERED"},
        "REGISTERED": {"KYC_PENDING"},
        "KYC_PENDING": {"KYC_VERIFIED", "REGISTERED"},
        "KYC_VERIFIED": {"ACTIVE"},
        "ACTIVE": {"SUSPENDED"},
        "SUSPENDED": {"ACTIVE"},
    },
)

# Spec: DRAFT → SUBMITTED → GIS_REVIEW → VERIFIED / REJECTED → INACTIVE.
# REJECTED → DRAFT and VERIFIED → DRAFT (re-open for correction, re-verification required) and
# INACTIVE → DRAFT (re-activation) are assumptions.
FARM_MACHINE = StateMachine.build(
    "farm", initial="DRAFT",
    transitions={
        "DRAFT": {"SUBMITTED", "INACTIVE"},
        "SUBMITTED": {"GIS_REVIEW", "DRAFT"},
        "GIS_REVIEW": {"VERIFIED", "REJECTED"},
        "VERIFIED": {"DRAFT", "INACTIVE"},
        "REJECTED": {"DRAFT", "INACTIVE"},
        "INACTIVE": {"DRAFT"},
    },
)

# Agreement and bank-account statuses are not enumerated in the spec (assumption, see open questions).
AGREEMENT_MACHINE = StateMachine.build(
    "farmer_agreement", initial="DRAFT",
    transitions={"DRAFT": {"SIGNED", "VOID"}, "SIGNED": {"TERMINATED", "EXPIRED"}},
    terminal={"TERMINATED", "EXPIRED", "VOID"},
)

BANK_ACCOUNT_MACHINE = StateMachine.build(
    "farmer_bank_account", initial="PENDING_VERIFICATION",
    transitions={"PENDING_VERIFICATION": {"VERIFIED", "REJECTED", "INACTIVE"}, "VERIFIED": {"INACTIVE"}, "REJECTED": {"INACTIVE"}},
    terminal={"INACTIVE"},
)

# Spec section 8 lists the full project lifecycle (20 states, all allowed by the DB CHECK constraint). Phase 3
# implemented the early transitions, Phase 4 adds METHODOLOGY_REVIEW / METHODOLOGY_CONFIRMED; later phases add theirs.
# Assumptions (docs/project-workflow.md): ELIGIBILITY_REVIEW -> DATA_COLLECTION (returned), STANDARD_SELECTED /
# ACTIVITY_SELECTED -> DATA_COLLECTION (re-opened for correction) and early states -> CLOSED (abandoned).
PROJECT_MACHINE = StateMachine.build(
    "project", initial="DRAFT",
    transitions={
        "DRAFT": {"DATA_COLLECTION", "CLOSED"},
        "DATA_COLLECTION": {"ELIGIBILITY_REVIEW", "CLOSED"},
        "ELIGIBILITY_REVIEW": {"STANDARD_SELECTED", "DATA_COLLECTION"},
        "STANDARD_SELECTED": {"ACTIVITY_SELECTED", "DATA_COLLECTION", "CLOSED"},
        "ACTIVITY_SELECTED": {"METHODOLOGY_REVIEW", "DATA_COLLECTION", "CLOSED"},
        # Phase 4: candidate evaluation + specialist review, then confirm = lock methodology + version.
        "METHODOLOGY_REVIEW": {"METHODOLOGY_CONFIRMED", "DATA_COLLECTION", "CLOSED"},
        # Unlocking is explicit and audited (never silent); MRV_PLANNED is added in Phase 5.
        "METHODOLOGY_CONFIRMED": {"METHODOLOGY_REVIEW", "MRV_PLANNED", "CLOSED"},
        # Phase 5: first MRV plan approved → MRV_PLANNED; first monitoring period started → MONITORING.
        "MRV_PLANNED": {"MONITORING", "CLOSED"},
        # Phase 7: entered only through the calculation workflow — inputs frozen → CALCULATION_READY; first run approved →
        # CALCULATED.
        "MONITORING": {"CALCULATION_READY", "CLOSED"},
        "CALCULATION_READY": {"CALCULATED", "CLOSED"},
        # Phase 8B (C2): aggregate only — first accepted VVB assignment (with an approved calculation) → VERIFICATION; first period
        # VERIFIED by a VVB → VERIFIED. Period-level verification records stay authoritative. VALIDATION and REGISTRY_* are not used.
        "CALCULATED": {"VERIFICATION", "CLOSED"},
        "VERIFICATION": {"VERIFIED", "CLOSED"},
        # Phase 9A (D13): aggregate only — first CONFIRMED registry issuance of any period → ISSUED. Period-level registry and issuance
        # records stay authoritative; REGISTRY_SUBMISSION, REGISTERED, ISSUANCE_PENDING and ACTIVE are not used.
        "VERIFIED": {"ISSUED", "CLOSED"},
        "ISSUED": {"CLOSED"},
    },
    terminal={"CLOSED"},
)

CARBON_RIGHT_MACHINE = StateMachine.build(
    "project_carbon_right", initial="ACTIVE", transitions={"ACTIVE": {"ENDED", "VOID"}}, terminal={"ENDED", "VOID"},
)

METHODOLOGY_VERSION_MACHINE = StateMachine.build(
    "methodology_version", initial="DRAFT",
    transitions={"DRAFT": {"IN_REVIEW", "WITHDRAWN"}, "IN_REVIEW": {"APPROVED", "DRAFT"}, "APPROVED": {"SUPERSEDED", "RETIRED"}},
    terminal={"SUPERSEDED", "RETIRED", "WITHDRAWN"},
)

MRV_PLAN_MACHINE = StateMachine.build(
    "mrv_plan", initial="DRAFT",
    transitions={"DRAFT": {"SUBMITTED", "WITHDRAWN"}, "SUBMITTED": {"APPROVED", "DRAFT"}, "APPROVED": {"SUPERSEDED"}},
    terminal={"SUPERSEDED", "WITHDRAWN"},
)

MONITORING_PERIOD_MACHINE = StateMachine.build(
    "monitoring_period", initial="DRAFT",
    transitions={"DRAFT": {"PLANNED"}, "PLANNED": {"ACTIVE"}, "ACTIVE": {"DATA_COLLECTION"},
                 "DATA_COLLECTION": {"SUBMITTED"}, "SUBMITTED": {"QA_REVIEW", "DATA_COLLECTION"},
                 "QA_REVIEW": {"APPROVED", "REJECTED"}, "REJECTED": {"DATA_COLLECTION"},
                 "APPROVED": {"CLOSED", "DATA_COLLECTION"}},  # re-opened only by a new (correction) dataset version
    terminal={"CLOSED"},
)

MRV_DATASET_MACHINE = StateMachine.build(
    "mrv_dataset", initial="DRAFT",
    transitions={"DRAFT": {"COLLECTING"}, "COLLECTING": {"SUBMITTED"}, "SUBMITTED": {"QA_REVIEW", "COLLECTING"},
                 "QA_REVIEW": {"APPROVED", "REJECTED"}, "APPROVED": {"SUPERSEDED"}},
    terminal={"REJECTED", "SUPERSEDED"},
)

FIELD_COLLECTION_MACHINE = StateMachine.build(
    "field_collection", initial="IN_PROGRESS",
    transitions={"IN_PROGRESS": {"SUBMITTED"}, "SUBMITTED": {"ACCEPTED", "RETURNED"}, "RETURNED": {"SUBMITTED"},
                 "ACCEPTED": {"SUPERSEDED"}},
    terminal={"SUPERSEDED"},
)

OVERLAP_MACHINE = StateMachine.build(
    "farm_overlap_check", initial="OPEN",
    transitions={"OPEN": {"CLEARED", "CONFIRMED_CONFLICT", "OBSOLETE"}, "CONFIRMED_CONFLICT": {"OBSOLETE"}, "CLEARED": {"OBSOLETE"}},
    terminal={"OBSOLETE"},
)


# ---------------------------------------------------------------- Phase 6 — laboratory & sample analysis
# Engagement: project proposes, laboratory accepts; never reactivated (a new engagement is created instead).
LAB_ENGAGEMENT_MACHINE = StateMachine.build(
    "lab_engagement", initial="PROPOSED",
    transitions={"PROPOSED": {"ACTIVE", "ENDED"}, "ACTIVE": {"ENDED"}},
    terminal={"ENDED"},
)

# Physical custody of a sample. Retention / return / disposal are out of scope (decision 21): custody ends at ANALYSED.
# EXCEPTION is resolved back to the state it interrupted (checked against the custody history, not here).
_SAMPLE_ANY = {"EXCEPTION"}
LAB_SAMPLE_MACHINE = StateMachine.build(
    "lab_sample", initial="REGISTERED",
    transitions={
        "REGISTERED": {"SEALED", "VOIDED"} | _SAMPLE_ANY,
        "SEALED": {"IN_SHIPMENT", "VOIDED"} | _SAMPLE_ANY,
        "IN_SHIPMENT": {"SEALED", "DISPATCHED"} | _SAMPLE_ANY,
        "DISPATCHED": {"IN_TRANSIT", "LAB_RECEIVED", "REJECTED_AT_RECEIPT"} | _SAMPLE_ANY,
        "IN_TRANSIT": {"IN_TRANSIT", "LAB_RECEIVED", "REJECTED_AT_RECEIPT"} | _SAMPLE_ANY,
        "LAB_RECEIVED": {"LAB_REGISTERED"} | _SAMPLE_ANY,
        "LAB_REGISTERED": {"IN_ANALYSIS"} | _SAMPLE_ANY,
        "IN_ANALYSIS": {"ANALYSED"} | _SAMPLE_ANY,
        "ANALYSED": {"IN_ANALYSIS"},          # an explicit retest on the same sample
        "EXCEPTION": {"REGISTERED", "SEALED", "IN_SHIPMENT", "DISPATCHED", "IN_TRANSIT", "LAB_RECEIVED", "LAB_REGISTERED", "IN_ANALYSIS",
                      "REJECTED_AT_RECEIPT", "VOIDED"},
    },
    terminal={"REJECTED_AT_RECEIPT", "VOIDED"},
)

LAB_SHIPMENT_MACHINE = StateMachine.build(
    "lab_shipment", initial="DRAFT",
    transitions={"DRAFT": {"DISPATCHED", "CANCELLED"}, "DISPATCHED": {"RECEIVED"}},
    terminal={"RECEIVED", "CANCELLED"},
)

LAB_TEST_MACHINE = StateMachine.build(
    "lab_test", initial="REQUESTED",
    transitions={"REQUESTED": {"IN_PROGRESS", "CANCELLED"}, "IN_PROGRESS": {"RESULT_SUBMITTED", "CANCELLED"},
                 "RESULT_SUBMITTED": {"IN_PROGRESS", "CLOSED"}, "CLOSED": {"IN_PROGRESS"}},  # CLOSED → IN_PROGRESS: correction
    terminal={"CANCELLED"},
)

# Result versions. REJECTED / RETEST_REQUIRED / WITHDRAWN / SUPERSEDED are final for that version.
LAB_RESULT_MACHINE = StateMachine.build(
    "lab_result", initial="DRAFT",
    transitions={"DRAFT": {"SUBMITTED", "WITHDRAWN"}, "SUBMITTED": {"QA_REVIEW", "REJECTED", "RETEST_REQUIRED", "WITHDRAWN"},
                 "QA_REVIEW": {"APPROVED", "REJECTED", "RETEST_REQUIRED"}, "APPROVED": {"SUPERSEDED"}},
    terminal={"REJECTED", "RETEST_REQUIRED", "WITHDRAWN", "SUPERSEDED"},
)


# ---------------------------------------------------------------- Phase 7 — carbon calculation
# Decision A3 (+ C3: DRAFT → BLOCKED when readiness fails at freeze, e.g. NO_CALCULATION_MODULE). Execution is synchronous, so
# there is no CALCULATING state. BLOCKED / CANCELLED / REJECTED / SUPERSEDED are final; a correction is a new run.
CALCULATION_RUN_MACHINE = StateMachine.build(
    "calculation_run", initial="DRAFT",
    transitions={"DRAFT": {"INPUTS_FROZEN", "BLOCKED", "CANCELLED"}, "INPUTS_FROZEN": {"CALCULATED", "BLOCKED", "CANCELLED"},
                 "CALCULATED": {"QA_REVIEW"}, "QA_REVIEW": {"APPROVED", "REJECTED"}, "APPROVED": {"SUPERSEDED"}},
    terminal={"BLOCKED", "CANCELLED", "REJECTED", "SUPERSEDED"},
)


# ---------------------------------------------------------------- Phase 8A — internal pre-verification (not VVB / ACVA)
CALCULATION_FINDING_MACHINE = StateMachine.build(
    "calculation_finding", initial="OPEN",
    transitions={"OPEN": {"RESPONDED", "WITHDRAWN"}, "RESPONDED": {"RESOLVED", "OPEN", "WITHDRAWN"}, "RESOLVED": {"OPEN"}},
    terminal={"WITHDRAWN"},
)

# B9: READY = "internally approved for submission to verification" — it is NOT verification.
CALCULATION_READINESS_MACHINE = StateMachine.build(
    "calculation_readiness", initial="DRAFT",
    transitions={"DRAFT": {"SUBMITTED", "WITHDRAWN"}, "SUBMITTED": {"READY", "REJECTED", "WITHDRAWN"}, "READY": {"INVALIDATED"}},
    terminal={"REJECTED", "WITHDRAWN", "INVALIDATED"},
)


# ---------------------------------------------------------------- Phase 8B — VVB / ACVA verification (C5, C14, C15)
VERIFICATION_ASSIGNMENT_MACHINE = StateMachine.build(
    "verification_assignment", initial="PROPOSED",
    transitions={"PROPOSED": {"ACCEPTED", "DECLINED", "WITHDRAWN"}, "ACCEPTED": {"COMPLETED", "TERMINATED"}},
    terminal={"COMPLETED", "DECLINED", "WITHDRAWN", "TERMINATED"},
)

VERIFICATION_SUBMISSION_MACHINE = StateMachine.build(
    "verification_submission", initial="SUBMITTED",
    transitions={"SUBMITTED": {"SUPERSEDED", "INVALIDATED"}},
    terminal={"SUPERSEDED", "INVALIDATED"},
)

VERIFICATION_FINDING_MACHINE = StateMachine.build(
    "verification_finding", initial="OPEN",
    transitions={"OPEN": {"RESPONDED"}, "RESPONDED": {"CLOSED", "OPEN"}, "CLOSED": {"OPEN"}},
)

CORRECTIVE_ACTION_MACHINE = StateMachine.build(
    "corrective_action", initial="REQUESTED",
    transitions={"REQUESTED": {"RESPONDED", "CANCELLED"}, "RESPONDED": {"ACCEPTED", "REQUESTED", "CANCELLED"}},
    terminal={"ACCEPTED", "CANCELLED"},
)


# ---------------------------------------------------------------- Phase 9A — registry submission & credit issuance
REGISTRY_ACCOUNT_MACHINE = StateMachine.build(
    "registry_account", initial="ACTIVE", transitions={"ACTIVE": {"CLOSED"}}, terminal={"CLOSED"},
)

REGISTRY_REGISTRATION_MACHINE = StateMachine.build(
    "registry_registration", initial="PENDING", transitions={"PENDING": {"REGISTERED", "REJECTED"}}, terminal={"REGISTERED", "REJECTED"},
)

REGISTRY_SUBMISSION_MACHINE = StateMachine.build(
    "registry_submission", initial="DRAFT",
    transitions={
        "DRAFT": {"FROZEN", "CANCELLED", "INVALIDATED"},
        "FROZEN": {"SUBMITTING", "SUBMITTED", "CANCELLED", "INVALIDATED"},
        # SUBMITTING → FROZEN only when the registry was certainly not reached (RegistryUnavailable before sending)
        "SUBMITTING": {"SUBMITTED", "SUBMISSION_UNCONFIRMED", "FROZEN"},
        # SUBMISSION_UNCONFIRMED → FROZEN only after confirming that the registry has no such submission
        "SUBMISSION_UNCONFIRMED": {"SUBMITTED", "FROZEN"},
        "SUBMITTED": {"ACCEPTED", "REJECTED", "WITHDRAWN"},
    },
    terminal={"REJECTED", "WITHDRAWN", "CANCELLED", "INVALIDATED"},
)

CREDIT_ISSUANCE_MACHINE = StateMachine.build(
    "credit_issuance", initial="RECORDED",
    transitions={"RECORDED": {"CONFIRMED", "VOIDED"}, "CONFIRMED": {"CORRECTED", "CANCELLED"}},
    terminal={"VOIDED", "CORRECTED", "CANCELLED"},
)

CREDIT_BATCH_MACHINE = StateMachine.build(
    "credit_batch", initial="RECORDED",
    transitions={"RECORDED": {"ISSUED", "VOIDED"}, "ISSUED": {"SUPERSEDED", "CANCELLED"}},
    terminal={"VOIDED", "SUPERSEDED", "CANCELLED"},
)
