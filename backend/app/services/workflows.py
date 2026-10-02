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

OVERLAP_MACHINE = StateMachine.build(
    "farm_overlap_check", initial="OPEN",
    transitions={"OPEN": {"CLEARED", "CONFIRMED_CONFLICT", "OBSOLETE"}, "CONFIRMED_CONFLICT": {"OBSOLETE"}, "CLEARED": {"OBSOLETE"}},
    terminal={"OBSOLETE"},
)
