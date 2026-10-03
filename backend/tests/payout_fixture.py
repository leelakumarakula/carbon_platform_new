"""TEST-ONLY payout provider adapter (Phase 11). Injected into the service layer by tests, never registered in
`app.integrations.payout.ADAPTERS`, never used in DEMO or LIVE: it exercises the provider paths (timeout → UNCONFIRMED, status query,
provider-reported PAID / FAILED) without any real money or provider."""
from app.integrations.payout import PayoutRequest, PayoutTimeout, ProviderPayout


class TestPayoutAdapter:
    __test__ = False                                                 # not a pytest test class
    code = "TEST"

    def __init__(self) -> None:
        self.payouts: dict[str, str] = {}                           # external id → status as the fake provider sees it
        self.by_key: dict[str, str] = {}                            # our idempotency key (payout code) → external id
        self.timeout_next = False

    def create_payout(self, request: PayoutRequest) -> ProviderPayout:
        ext = f"TPYT-{request.payout_code}"
        self.payouts[ext] = "PENDING"
        self.by_key[request.idempotency_key] = ext
        if self.timeout_next:
            self.timeout_next = False
            raise PayoutTimeout("TEST provider did not answer")
        return ProviderPayout(ext, "PENDING")

    def get_status(self, reference: str) -> ProviderPayout:
        ext = self.by_key.get(reference, reference)
        return ProviderPayout(ext, self.payouts.get(ext, "PENDING"))  # type: ignore[arg-type]

    def cancel_payout(self, reference: str) -> None:
        self.payouts[self.by_key.get(reference, reference)] = "FAILED"

    def settle(self, external_id: str, status: str = "PAID") -> None:
        self.payouts[external_id] = status
