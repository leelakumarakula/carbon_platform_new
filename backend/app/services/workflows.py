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
        "METHODOLOGY_CONFIRMED": {"METHODOLOGY_REVIEW", "CLOSED"},
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

OVERLAP_MACHINE = StateMachine.build(
    "farm_overlap_check", initial="OPEN",
    transitions={"OPEN": {"CLEARED", "CONFIRMED_CONFLICT", "OBSOLETE"}, "CONFIRMED_CONFLICT": {"OBSOLETE"}, "CLEARED": {"OBSOLETE"}},
    terminal={"OBSOLETE"},
)
