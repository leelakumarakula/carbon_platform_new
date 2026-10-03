"""Payment adapter boundary (Phase 10, decisions D15–D17, D33). Payment providers are external; the platform never fakes a financial
confirmation.

- `ManualPaymentAdapter` is the only runtime adapter until a payment provider is contracted. It never answers on a provider's behalf: every
  automated call raises `ManualActionRequired`. A manual payment is recorded by the buyer with evidence (PAYMENT_EVIDENCE) and confirmed by
  the seller's finance team (the payee, D16) — a different person.
- A real provider adapter is added only with a contract (including its webhook signature scheme). Until then there is NO public webhook
  route (D17); provider events reach `payment_service.ingest_event` only from an adapter.
- The TEST-only fake provider lives in `tests/payment_fixture.py`: it is injected into the service layer by tests and never registered
  here, never used in DEMO and never in LIVE.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

EventType = Literal["SUCCEEDED", "FAILED", "CANCELLED", "PENDING"]


@dataclass(frozen=True)
class PaymentRequest:
    payment_code: str
    order_code: str
    amount: Decimal
    currency: str
    idempotency_key: str


@dataclass(frozen=True)
class ProviderPayment:
    external_id: str
    status: EventType


@dataclass(frozen=True)
class ProviderEvent:
    """A provider notification as parsed by its adapter; only the payload hash is kept."""
    external_event_id: str
    external_payment_id: str
    event_type: EventType
    payload_sha256: str


@dataclass(frozen=True)
class ProviderRefund:
    external_id: str


class ManualActionRequired(RuntimeError):
    """No automated provider: record the payment / refund manually with evidence."""


class PaymentUnavailable(RuntimeError):
    pass


class PaymentTimeout(RuntimeError):
    pass


class PaymentAdapter(Protocol):
    code: str

    def create_payment(self, request: PaymentRequest) -> ProviderPayment: ...
    def get_status(self, external_payment_id: str) -> ProviderPayment: ...
    def refund(self, external_payment_id: str, amount: Decimal, currency: str, idempotency_key: str) -> ProviderRefund: ...
    def parse_event(self, raw: bytes) -> ProviderEvent: ...


class ManualPaymentAdapter:
    code = "MANUAL"

    def _manual(self) -> ManualActionRequired:
        return ManualActionRequired("No payment provider is contracted: record the payment or refund manually with evidence.")

    def create_payment(self, request: PaymentRequest) -> ProviderPayment:
        raise self._manual()

    def get_status(self, external_payment_id: str) -> ProviderPayment:
        raise self._manual()

    def refund(self, external_payment_id: str, amount: Decimal, currency: str, idempotency_key: str) -> ProviderRefund:
        raise self._manual()

    def parse_event(self, raw: bytes) -> ProviderEvent:
        raise self._manual()


# The application's adapters. Test adapters are injected into the service layer and never registered here (D15, D33).
ADAPTERS: dict[str, PaymentAdapter] = {"MANUAL": ManualPaymentAdapter()}

# ISO 4217 minor units of the currencies accepted for listings (D8). A currency outside this list is refused, never guessed.
CURRENCY_EXPONENTS: dict[str, int] = {
    "INR": 2, "USD": 2, "EUR": 2, "GBP": 2, "CHF": 2, "AUD": 2, "CAD": 2, "NZD": 2, "SGD": 2, "HKD": 2, "AED": 2, "SAR": 2, "ZAR": 2,
    "BRL": 2, "CNY": 2, "SEK": 2, "NOK": 2, "DKK": 2, "JPY": 0, "KRW": 0, "BHD": 3, "KWD": 3, "OMR": 3, "JOD": 3,
}


def money_ok(value: Decimal, currency: str) -> bool:
    """True if `value` has no more decimals than the currency's minor unit allows."""
    exp = CURRENCY_EXPONENTS.get(currency)
    if exp is None:
        return False
    return value == value.quantize(Decimal(1).scaleb(-exp))
