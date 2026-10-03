"""Laboratory information management system (LIMS) adapter boundary — Phase 6 defines the interface only.

No vendor is integrated. The internal model never depends on a vendor API: an adapter translates between the canonical
types below and one LIMS. Imported results would enter as `source = LIMS_IMPORT` with a unique `external_result_id` per
laboratory, mapped to an in-scope methodology LABORATORY rule, and still go through laboratory QA like manual results.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class ManifestItem:
    sample_code: str
    test_codes: tuple[str, ...]
    depth_top_cm: Decimal
    depth_bottom_cm: Decimal
    description: str


@dataclass(frozen=True)
class Manifest:
    """What a laboratory receives for a shipment — the same allow-listed data as the laboratory-facing API (no farm / GPS)."""
    shipment_code: str
    project_code: str
    items: tuple[ManifestItem, ...]


@dataclass(frozen=True)
class ExternalResult:
    external_result_id: str
    test_code: str
    result_type: str                 # NUMERIC | TEXT — text is kept verbatim, never parsed
    value_number: Decimal | None
    value_text: str | None
    unit: str | None
    analysed_at: datetime
    method_reported: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


class LimsAdapter(Protocol):
    def submit_manifest(self, laboratory_org_id: uuid.UUID, manifest: Manifest) -> str: ...
    def fetch_results(self, laboratory_org_id: uuid.UUID, since: datetime | None) -> list[ExternalResult]: ...
    def acknowledge(self, laboratory_org_id: uuid.UUID, external_result_ids: list[str]) -> None: ...


class LimsNotConfigured(RuntimeError):
    pass


class NoLimsAdapter:
    """Default: no LIMS integration exists. Every call fails explicitly — nothing is simulated."""

    def submit_manifest(self, laboratory_org_id: uuid.UUID, manifest: Manifest) -> str:
        raise LimsNotConfigured("No LIMS adapter is configured; laboratories use the laboratory workspace.")

    def fetch_results(self, laboratory_org_id: uuid.UUID, since: datetime | None) -> list[ExternalResult]:
        raise LimsNotConfigured("No LIMS adapter is configured; laboratories use the laboratory workspace.")

    def acknowledge(self, laboratory_org_id: uuid.UUID, external_result_ids: list[str]) -> None:
        raise LimsNotConfigured("No LIMS adapter is configured; laboratories use the laboratory workspace.")


def get_lims_adapter() -> LimsAdapter:
    return NoLimsAdapter()
