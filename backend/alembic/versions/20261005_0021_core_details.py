"""Soil-core details on field collection records (VM0042 v2.2 §8.2.1.6, Equation 3).

`probe_diameter_mm` (inside diameter of the probe or auger, mm) and `cores_count` (number of cores composited into the
sample) convert a sample's dry soil mass to a mass per hectare. Both are nullable: a methodology version makes them mandatory
at submission through its SAMPLING rule key `core_details_required` (frozen in the record's field rules). Existing records
keep NULL; nothing is guessed.

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0021'
down_revision: str | None = '0020'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('field_collection_records', sa.Column('probe_diameter_mm', sa.Numeric(precision=6, scale=2), nullable=True))
    op.add_column('field_collection_records', sa.Column('cores_count', sa.Integer(), nullable=True))
    op.create_check_constraint(op.f('ck_field_collection_records_probe_diameter'), 'field_collection_records',
                               "probe_diameter_mm IS NULL OR (probe_diameter_mm > 0 AND probe_diameter_mm <= 500)")
    op.create_check_constraint(op.f('ck_field_collection_records_cores_count'), 'field_collection_records',
                               "cores_count IS NULL OR cores_count BETWEEN 1 AND 200")


def downgrade() -> None:
    op.execute(sa.text("""
        IF EXISTS (SELECT 1 FROM field_collection_records WHERE probe_diameter_mm IS NOT NULL OR cores_count IS NOT NULL)
        BEGIN; THROW 51000, 'Downgrade refused: soil-core details are recorded.', 1; END;
    """))
    op.drop_constraint(op.f('ck_field_collection_records_cores_count'), 'field_collection_records', type_='check')
    op.drop_constraint(op.f('ck_field_collection_records_probe_diameter'), 'field_collection_records', type_='check')
    op.drop_column('field_collection_records', 'cores_count')
    op.drop_column('field_collection_records', 'probe_diameter_mm')
