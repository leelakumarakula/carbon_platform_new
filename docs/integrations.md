# External integrations

The core depends on interfaces; vendors sit behind adapters selected by configuration. A mock or development adapter is
never presented as a real external confirmation, and the UI labels DEMO data and illustrative entries.

| Interface | Status | Implementations | Setting |
|---|---|---|---|
| Object storage | in use (Phase 2) | `LocalFileStorage` (development). S3 / MinIO pending | `STORAGE_BACKEND`, `LOCAL_STORAGE_ROOT`, `OBJECT_STORAGE_*` |
| Malware scanner | in use (Phase 2) | `SignatureScanner` (EICAR test signature only). Real antivirus engine pending | `MALWARE_SCANNER` |
| Basemap tiles | in use (D6) | any XYZ tile source; OpenStreetMap public tiles by default (development only) | `MAP_TILE_*` |
| Notifications | in use | in-app only. Email, SMS and WhatsApp adapters pending | — |
| Satellite, weather, land records | planned (Phase 6+); Phase 5 records no satellite data — field evidence only | mock + real | `SATELLITE_PROVIDER` |
| Laboratory (LIMS) | interface only (Phase 6): `LimsAdapter` (submit manifest, fetch results, acknowledge) in `app/integrations/lims.py`; `NoLimsAdapter` raises `LimsNotConfigured` | manual entry in the laboratory workspace (source MANUAL); a real LIMS would import as `LIMS_IMPORT` with an external result ID. There is no mock result source | — |
| Verification (VVB/ACVA) | planned (Phase 8) | workflow only; the platform is not the verifier | — |
| Registry | in use (Phase 9A, 9B): `RegistryAdapter` in `app/integrations/registry.py` (register_project, submit_issuance_request, get_submission_status, get_issuances, submit_document, parse_serial_range; 9B: transfer_credits, retire_credits, get_credit_inventory — manual reconciliation only, MISMATCH recorded, never auto-fixed) | `ManualRegistryAdapter` only — never simulates (raises `ManualActionRequired`; operators record references with evidence). Selected per registry account (`adapter_code`). A Verra / Gold Standard / CCTS adapter is added only with a contracted API. The API-mode paths are exercised with a TEST-only adapter injected in tests (never registered) | `registry_accounts.adapter_code` |
| Payment | in use (Phase 10): `PaymentAdapter` in `app/integrations/payment.py` (create_payment, get_status, refund, parse_event) | `ManualPaymentAdapter` only — raises `ManualActionRequired`; buyers record payments with evidence and the payee's finance confirms. No mock provider exists; the TEST adapter (`tests/payment_fixture.py`) is injected in tests and never registered. A real provider (with its webhook signature scheme) is added only with a contract; until then there is no public webhook route | `PAYMENT_PROVIDER=manual` |
| Payout | in use (Phase 11): `PayoutAdapter` in `app/integrations/payout.py` (create_payout, get_status, cancel_payout) | `ManualPayoutAdapter` only — raises `ManualActionRequired`. Finance pays at the bank, records the reference with a PAYOUT_EVIDENCE PDF, and a different person reconciles against a statement. No mock provider exists; the TEST adapter (`tests/payout_fixture.py`) is injected in tests and never registered. A bank / payout provider is added only with a contract. There is no webhook and no bulk-file export. | — |

**Methodologies are not an integration.** Rules are entered by methodology specialists from the authoritative source
and approved by a second person (docs/methodology-engine.md). The platform does not fetch or interpret methodology
documents automatically.
