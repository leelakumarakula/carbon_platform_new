"""Status machines for Phase 1 entities. Later phases add farmer, farm, project, credit, ... here."""
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
