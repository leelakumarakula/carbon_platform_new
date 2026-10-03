"""Registry adapter boundary (Phase 9A, decisions D4 / D9). Registries are external counterparties; the platform records what a registry
states and never simulates a registry response.

- The adapter is selected per registry account (`registry_accounts.adapter_code`). Only `MANUAL` exists: a real Verra / Gold Standard /
  CCTS adapter is added only with an actual contracted API.
- `ManualRegistryAdapter` never answers on the registry's behalf: every call raises `ManualActionRequired`, and the operator records the
  external reference with evidence instead.
- Serial numbers belong to the registry. An adapter may offer a registry-specific `parse_serial_range`; no universal format is assumed.
- Phase 9B declares transfer_credits / retire_credits / get_credit_inventory; without a contracted registry API they raise
  `ManualActionRequired` — registry transfers, retirements and inventory reconciliation are recorded manually with registry evidence.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal, Protocol

AdapterMode = Literal["API", "MANUAL"]


@dataclass(frozen=True)
class AccountRef:
    registry_code: str                 # registry organization code (counterparty)
    external_account_id: str


@dataclass(frozen=True)
class ExternalRef:
    external_id: str
    payload_sha256: str | None = None


@dataclass(frozen=True)
class SubmitResult:
    """The registry received the request (its own identifier). Acceptance or rejection comes later through a status query."""
    external_submission_id: str
    payload_sha256: str | None = None


@dataclass(frozen=True)
class StatusResult:
    """FOUND / NOT_FOUND answer a lookup by idempotency key; RECEIVED / ACCEPTED / REJECTED are the registry's processing state."""
    status: Literal["NOT_FOUND", "RECEIVED", "ACCEPTED", "REJECTED"]
    external_submission_id: str | None = None
    reason: str | None = None
    payload_sha256: str | None = None


@dataclass(frozen=True)
class ExternalSerialRange:
    serial_start: str | None
    serial_end: str | None
    quantity: int


@dataclass(frozen=True)
class ExternalBatch:
    vintage: str
    quantity: int
    serial_ranges: tuple[ExternalSerialRange, ...] = ()


@dataclass(frozen=True)
class ExternalIssuance:
    external_issuance_id: str
    issuance_date: date
    quantity: int
    unit: str
    batches: tuple[ExternalBatch, ...] = ()
    payload_sha256: str | None = None


@dataclass(frozen=True)
class ParsedSerialRange:
    """Numeric bounds of one registry serial block, from a registry-specific parser only."""
    series: str
    start: int
    end: int


@dataclass(frozen=True)
class SubmissionPackage:
    submission_code: str
    snapshot_sha256: str
    snapshot: dict[str, Any]
    documents: tuple[dict[str, Any], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CreditMovement:
    """A registry-side transfer or retirement request (Phase 9B). Serials are only those the registry supplies."""
    batch_external_issuance_id: str
    quantity: int
    serial_start: str | None = None
    serial_end: str | None = None
    recipient_external_account_id: str | None = None
    beneficiary: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class InventoryLine:
    external_issuance_id: str
    quantity: int


class ManualActionRequired(RuntimeError):
    """The registry is operated manually: record the external reference and evidence instead."""


class RegistryUnavailable(RuntimeError):
    """The registry could not be reached; the request certainly did not arrive (safe to try again later)."""


class RegistryTimeout(RuntimeError):
    """No answer after sending: the registry may or may not have received the request (never retried automatically)."""


class RegistryAdapter(Protocol):
    mode: AdapterMode

    def register_project(self, account: AccountRef, project: dict[str, Any], idempotency_key: str) -> ExternalRef: ...
    def submit_issuance_request(self, account: AccountRef, package: SubmissionPackage, idempotency_key: str) -> SubmitResult: ...
    def get_submission_status(self, account: AccountRef, *, external_submission_id: str | None = None,
                              idempotency_key: str | None = None) -> StatusResult: ...
    def get_issuances(self, account: AccountRef, external_project_id: str) -> list[ExternalIssuance]: ...
    def submit_document(self, account: AccountRef, external_submission_id: str, document: dict[str, Any]) -> ExternalRef: ...
    def parse_serial_range(self, serial_start: str, serial_end: str) -> ParsedSerialRange | None: ...
    def transfer_credits(self, account: AccountRef, movement: CreditMovement, idempotency_key: str) -> ExternalRef: ...
    def retire_credits(self, account: AccountRef, movement: CreditMovement, idempotency_key: str) -> ExternalRef: ...
    def get_credit_inventory(self, account: AccountRef) -> list[InventoryLine]: ...


class ManualRegistryAdapter:
    """Default. Nothing is sent and nothing is simulated."""
    mode: AdapterMode = "MANUAL"

    def _manual(self) -> ManualActionRequired:
        return ManualActionRequired("This registry is operated manually: record the external reference with its evidence.")

    def register_project(self, account: AccountRef, project: dict[str, Any], idempotency_key: str) -> ExternalRef:
        raise self._manual()

    def submit_issuance_request(self, account: AccountRef, package: SubmissionPackage, idempotency_key: str) -> SubmitResult:
        raise self._manual()

    def get_submission_status(self, account: AccountRef, *, external_submission_id: str | None = None,
                              idempotency_key: str | None = None) -> StatusResult:
        raise self._manual()

    def get_issuances(self, account: AccountRef, external_project_id: str) -> list[ExternalIssuance]:
        raise self._manual()

    def submit_document(self, account: AccountRef, external_submission_id: str, document: dict[str, Any]) -> ExternalRef:
        raise self._manual()

    def parse_serial_range(self, serial_start: str, serial_end: str) -> ParsedSerialRange | None:
        return None                     # no registry-specific format is known: serials are stored verbatim only

    def transfer_credits(self, account: AccountRef, movement: CreditMovement, idempotency_key: str) -> ExternalRef:
        raise self._manual()

    def retire_credits(self, account: AccountRef, movement: CreditMovement, idempotency_key: str) -> ExternalRef:
        raise self._manual()

    def get_credit_inventory(self, account: AccountRef) -> list[InventoryLine]:
        raise self._manual()


# The application's adapters. Test adapters are injected into the service layer and never registered here.
ADAPTERS: dict[str, RegistryAdapter] = {"MANUAL": ManualRegistryAdapter()}


def adapter_codes() -> list[str]:
    return sorted(ADAPTERS)


def whole(value: Decimal | int) -> bool:
    d = Decimal(value)
    return d == d.to_integral_value() and d > 0
