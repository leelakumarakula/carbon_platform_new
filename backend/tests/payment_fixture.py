"""TEST-ONLY payment provider adapter (Phase 10, D15 / D32). It is injected into the service layer by tests, never registered in
`app.integrations.payment.ADAPTERS`, never used in DEMO and never in LIVE: it exists to exercise the provider paths (outbox, timeout →
UNCONFIRMED, events, duplicate events, reconciliation, provider refunds) without any real money or provider."""
import hashlib
import json
from decimal import Decimal

from app.integrations.payment import PaymentRequest, PaymentTimeout, ProviderEvent, ProviderPayment, ProviderRefund


class TestPaymentAdapter:
    __test__ = False                                                 # not a pytest test class
    code = "TEST"

    def __init__(self) -> None:
        self.payments: dict[str, str] = {}                          # external id → status as the fake provider sees it
        self.by_key: dict[str, str] = {}                            # our idempotency key (payment code) → external id
        self.timeout_next = False
        self.refunds: list[str] = []

    def create_payment(self, request: PaymentRequest) -> ProviderPayment:
        ext = f"TPAY-{request.payment_code}"
        self.payments[ext] = "PENDING"
        self.by_key[request.idempotency_key] = ext
        if self.timeout_next:
            self.timeout_next = False
            raise PaymentTimeout("TEST provider did not answer")
        return ProviderPayment(ext, "PENDING")

    def get_status(self, external_payment_id: str) -> ProviderPayment:
        ext = self.by_key.get(external_payment_id, external_payment_id)
        return ProviderPayment(ext, self.payments.get(ext, "PENDING"))  # type: ignore[arg-type]

    def refund(self, external_payment_id: str, amount: Decimal, currency: str, idempotency_key: str) -> ProviderRefund:
        ref = f"TRFD-{idempotency_key}"
        self.refunds.append(ref)
        return ProviderRefund(ref)

    def parse_event(self, raw: bytes) -> ProviderEvent:
        body = json.loads(raw)
        return ProviderEvent(body["id"], body["payment"], body["type"], hashlib.sha256(raw).hexdigest())

    @staticmethod
    def event(event_id: str, external_payment_id: str, event_type: str) -> bytes:
        return json.dumps({"id": event_id, "payment": external_payment_id, "type": event_type}, sort_keys=True).encode()
