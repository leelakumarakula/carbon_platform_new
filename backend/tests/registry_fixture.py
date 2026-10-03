"""TEST-ONLY registry adapter (Phase 9A). It is injected into the service layer by tests, never registered in
`app.integrations.registry.ADAPTERS`, and every record it leads to lives in the rolled-back test database.

It plays an imaginary API registry so the API-mode paths can be exercised: receipt, acceptance / rejection through status queries,
timeouts before and after receipt, unavailability, issuances with serial numbers and a registry-specific serial parser for the TEST
format `TSER-<series>-<number>` (a made-up format, not any real registry's)."""
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from app.integrations.registry import (
    AccountRef,
    CreditMovement,
    ExternalIssuance,
    ExternalRef,
    InventoryLine,
    ParsedSerialRange,
    RegistryTimeout,
    RegistryUnavailable,
    StatusResult,
    SubmissionPackage,
    SubmitResult,
)

SERIAL = re.compile(r"^TSER-([A-Z]+)-(\d{6})$")


def _sha(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


@dataclass
class TestRegistryAdapter:
    __test__ = False                                  # not a pytest test class
    mode: str = "API"
    behaviour: str | None = None                      # None | "unavailable" | "timeout_before" | "timeout_after"
    calls: list[str] = field(default_factory=list)    # idempotency keys of every submit call
    received: dict[str, str] = field(default_factory=dict)          # idempotency key → external submission id (registry-side dedupe)
    status: dict[str, str] = field(default_factory=dict)
    reasons: dict[str, str] = field(default_factory=dict)
    issued: dict[str, list[ExternalIssuance]] = field(default_factory=dict)

    def register_project(self, account: AccountRef, project: dict[str, Any], idempotency_key: str) -> ExternalRef:
        return ExternalRef(f"TEST-PRJ-{idempotency_key[:8]}")

    def submit_issuance_request(self, account: AccountRef, package: SubmissionPackage, idempotency_key: str) -> SubmitResult:
        self.calls.append(idempotency_key)
        if self.behaviour == "unavailable":
            raise RegistryUnavailable("TEST registry offline (request not sent)")
        if self.behaviour == "timeout_before":
            raise RegistryTimeout("TEST timeout before the registry received anything")
        ext = self.received.setdefault(idempotency_key, f"TEST-SUB-{len(self.received) + 1:04d}")
        self.status.setdefault(ext, "RECEIVED")
        if self.behaviour == "timeout_after":
            raise RegistryTimeout("TEST timeout after the registry received the request")
        return SubmitResult(ext, payload_sha256=_sha("received", ext))

    def get_submission_status(self, account: AccountRef, *, external_submission_id: str | None = None,
                              idempotency_key: str | None = None) -> StatusResult:
        ext = external_submission_id or (self.received.get(idempotency_key) if idempotency_key else None)
        if ext is None:
            return StatusResult("NOT_FOUND", payload_sha256=_sha("not-found", idempotency_key or ""))
        st = self.status[ext]
        return StatusResult(st, ext, reason=self.reasons.get(ext), payload_sha256=_sha(st, ext))   # type: ignore[arg-type]

    def decide(self, external_submission_id: str, status: str, reason: str | None = None) -> None:
        self.status[external_submission_id] = status
        if reason:
            self.reasons[external_submission_id] = reason

    def issue(self, external_project_id: str, issuance: ExternalIssuance) -> None:
        self.issued.setdefault(external_project_id, []).append(issuance)

    def get_issuances(self, account: AccountRef, external_project_id: str) -> list[ExternalIssuance]:
        return list(self.issued.get(external_project_id, []))

    def submit_document(self, account: AccountRef, external_submission_id: str, document: dict[str, Any]) -> ExternalRef:
        return ExternalRef(f"TEST-DOC-{external_submission_id}")

    def parse_serial_range(self, serial_start: str, serial_end: str) -> ParsedSerialRange | None:
        a, b = SERIAL.match(serial_start), SERIAL.match(serial_end)
        if a is None or b is None or a.group(1) != b.group(1):
            return None
        return ParsedSerialRange(series=a.group(1), start=int(a.group(2)), end=int(b.group(2)))

    # Phase 9B: declared so the protocol is complete; the platform never calls them automatically (manual, evidence-backed flows)
    def transfer_credits(self, account: AccountRef, movement: CreditMovement, idempotency_key: str) -> ExternalRef:
        return ExternalRef(f"TEST-TRF-{idempotency_key[:8]}")

    def retire_credits(self, account: AccountRef, movement: CreditMovement, idempotency_key: str) -> ExternalRef:
        return ExternalRef(f"TEST-RET-{idempotency_key[:8]}")

    def get_credit_inventory(self, account: AccountRef) -> list[InventoryLine]:
        return []
