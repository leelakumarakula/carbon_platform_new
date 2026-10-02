"""Explicit status machines (spec section 8, rule 7).

Every workflow entity declares its permitted transitions once; services call
`machine.assert_transition(current, target)` before changing status, and record
a workflow_event + audit_log for every transition.
"""
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from app.core.errors import InvalidTransition


@dataclass(frozen=True)
class StateMachine:
    entity_type: str
    transitions: Mapping[str, frozenset[str]]
    initial: str
    terminal: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def build(cls, entity_type: str, initial: str, transitions: Mapping[str, Iterable[str]],
              terminal: Iterable[str] = ()) -> "StateMachine":
        states = set(transitions) | {t for ts in transitions.values() for t in ts} | {initial} | set(terminal)
        table = {s: frozenset(transitions.get(s, ())) for s in states}
        for t in terminal:
            if table[t]:
                raise ValueError(f"{entity_type}: terminal state {t} has outgoing transitions")
        return cls(entity_type, table, initial, frozenset(terminal))

    @property
    def states(self) -> frozenset[str]:
        return frozenset(self.transitions)

    def allowed_from(self, current: str) -> frozenset[str]:
        return self.transitions.get(current, frozenset())

    def can(self, current: str, target: str) -> bool:
        return target in self.allowed_from(current)

    def assert_transition(self, current: str, target: str) -> None:
        if target not in self.states:
            raise InvalidTransition(f"'{target}' is not a valid {self.entity_type} status.",
                                    details={"entity_type": self.entity_type, "to": target})
        if not self.can(current, target):
            raise InvalidTransition(
                f"A {self.entity_type} cannot move from {current} to {target}.",
                details={"entity_type": self.entity_type, "from": current, "to": target,
                         "allowed": sorted(self.allowed_from(current))})
