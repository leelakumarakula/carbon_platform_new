"""Payout adapter boundary (Phase 11, D24). Bank / payout providers are external; the platform never fakes a payout.

- `ManualPayoutAdapter` is the only runtime adapter: every automated call raises `ManualActionRequired`. A finance user pays at the bank,
  then records the bank reference and a PAYOUT_EVIDENCE PDF (PAID); a different person reconciles it against a statement.
- A real provider adapter is added only with a contract. There is no public webhook.
- The TEST-only adapter lives in `tests/payout_fixture.py`, is injected into the service layer by tests and is never registered here.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

PayoutStatus = Literal["PENDING", "PAID", "FAILED"]


@dataclass(frozen=True)
class PayoutRequest:
    payout_code: str
    amount: Decimal
    currency: str
    beneficiary_reference: str          # an opaque reference to the verified bank account record — never the account number
    idempotency_key: str


@dataclass(frozen=True)
class ProviderPayout:
    external_id: str
    status: PayoutStatus


class ManualActionRequired(RuntimeError):
    """No automated payout provider: execute the payout at the bank and record it with evidence."""


class PayoutUnavailable(RuntimeError):
    pass


class PayoutTimeout(RuntimeError):
    pass


class PayoutAdapter(Protocol):
    code: str

    def create_payout(self, request: PayoutRequest) -> ProviderPayout: ...
    def get_status(self, reference: str) -> ProviderPayout: ...
    def cancel_payout(self, reference: str) -> None: ...


class ManualPayoutAdapter:
    code = "MANUAL"

    def _manual(self) -> ManualActionRequired:
        return ManualActionRequired("No payout provider is contracted: pay at the bank and record the reference and evidence.")

    def create_payout(self, request: PayoutRequest) -> ProviderPayout:
        raise self._manual()

    def get_status(self, reference: str) -> ProviderPayout:
        raise self._manual()

    def cancel_payout(self, reference: str) -> None:
        raise self._manual()


# The application's adapters. Test adapters are injected into the service layer and never registered here.
ADAPTERS: dict[str, PayoutAdapter] = {"MANUAL": ManualPayoutAdapter()}
