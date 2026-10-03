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
| Registry | planned (Phase 9) | Manual + mock; Verra / Gold Standard / CCTS adapters where APIs exist | `REGISTRY_PROVIDER` |
| Payment | planned (Phase 10–11) | mock (never in production mode) + real | `PAYMENT_PROVIDER` |

**Methodologies are not an integration.** Rules are entered by methodology specialists from the authoritative source
and approved by a second person (docs/methodology-engine.md). The platform does not fetch or interpret methodology
documents automatically.
