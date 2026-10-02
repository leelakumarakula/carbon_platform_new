"""Phase 5 governance decisions S1/S2: field-collection rules frozen per design version and per field record.

Adds `field_rules` (JSON) to sampling design versions and field collection records, plus `checklist_version` and
`gps_tolerance_m` on field collection records. Existing rows are backfilled with the platform defaults that were in force
when they were created (30 m GPS tolerance, 1 m duplicate threshold, checklist PLATFORM-DEFAULT-1, 1 photo) — this records
the rules they were collected under; it does not change any collected value.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-03 01:04:45.457604
"""
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0007'
down_revision: str | None = '0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOTE = ("Values marked PLATFORM_DEFAULT are platform governance defaults, not requirements of any methodology; "
        "values marked METHODOLOGY come from the locked methodology version's SAMPLING rules.")
LEGACY = {
    "gps_tolerance_m": 30.0, "gps_tolerance_source": "PLATFORM_DEFAULT", "gps_tolerance_rule": None,
    "duplicate_distance_m": 1.0, "duplicate_distance_source": "PLATFORM_DEFAULT", "duplicate_distance_rule": None,
    "min_photos": 1, "min_photos_source": "PLATFORM_DEFAULT", "min_photos_rule": None,
    "checklist_version": "PLATFORM-DEFAULT-1",
    "checklist_items": [
        {"key": "location_confirmed", "label": "Location confirmed on site"},
        {"key": "depth_measured", "label": "Sampling depth measured"},
        {"key": "sample_labelled", "label": "Sample bag labelled with the collection code"},
        {"key": "photo_taken", "label": "Field photo taken"},
    ],
    "checklist_source": "PLATFORM_DEFAULT", "methodology_version_id": None, "resolved_at": None, "note": NOTE,
    "backfilled_by_migration": "0007",
}


def upgrade() -> None:
    op.add_column('field_collection_records', sa.Column('field_rules', sa.UnicodeText(), nullable=True))
    op.add_column('field_collection_records', sa.Column('checklist_version', sa.Unicode(length=120), nullable=True))
    op.add_column('field_collection_records', sa.Column('gps_tolerance_m', sa.Numeric(precision=8, scale=1), nullable=True))
    op.add_column('sampling_design_versions', sa.Column('field_rules', sa.UnicodeText(), nullable=True))
    op.create_check_constraint('ck_field_collection_records_field_rules_json', 'field_collection_records',
                               'field_rules IS NULL OR ISJSON(field_rules) = 1')
    op.create_check_constraint('ck_sampling_design_versions_field_rules_json', 'sampling_design_versions',
                               'field_rules IS NULL OR ISJSON(field_rules) = 1')
    legacy = json.dumps(LEGACY)
    op.execute(sa.text("UPDATE sampling_design_versions SET field_rules = :r WHERE field_rules IS NULL").bindparams(r=legacy))
    op.execute(sa.text("UPDATE field_collection_records SET field_rules = :r, checklist_version = 'PLATFORM-DEFAULT-1', "
                       "gps_tolerance_m = 30.0 WHERE field_rules IS NULL").bindparams(r=legacy))


def downgrade() -> None:
    op.drop_constraint('ck_sampling_design_versions_field_rules_json', 'sampling_design_versions', type_='check')
    op.drop_constraint('ck_field_collection_records_field_rules_json', 'field_collection_records', type_='check')
    op.drop_column('sampling_design_versions', 'field_rules')
    op.drop_column('field_collection_records', 'gps_tolerance_m')
    op.drop_column('field_collection_records', 'checklist_version')
    op.drop_column('field_collection_records', 'field_rules')
