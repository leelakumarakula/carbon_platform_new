"""Production readiness is recorded per module code version; calculation output values are widened.

1. `methodology_versions.calculation_readiness_module_version`: the module code version (e.g. "1.2.0") a PRODUCTION_READY decision
   was made for. `registry.bind` treats the version as production-ready only while the bound module has exactly this version, so a
   module code change (VM0042 1.2.0 -> 1.3.0) needs a new readiness approval. Existing PRODUCTION_READY approvals carry no recorded
   version: they are reset to NOT_PRODUCTION_READY here (they would never match anyway) and must be requested and approved again.
2. `calculation_outputs.value` Unicode(80) -> Unicode(1000) (the same as `calculation_inputs.value`): an exact, unrounded 34-digit
   Decimal written without exponent (e.g. 1E-60 or a large product) exceeded 80 characters, so the database write failed after the run
   had been computed.

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0024'
down_revision: str | None = '0023'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('methodology_versions', sa.Column('calculation_readiness_module_version', sa.Unicode(length=20), nullable=True))
    op.execute("UPDATE dbo.methodology_versions SET calculation_readiness = N'NOT_PRODUCTION_READY' "
               "WHERE calculation_readiness = N'PRODUCTION_READY' AND calculation_readiness_module_version IS NULL")
    op.alter_column('calculation_outputs', 'value', existing_type=sa.Unicode(length=80), type_=sa.Unicode(length=1000), existing_nullable=False)


def downgrade() -> None:
    # calculation outputs are append-only: the downgrade fails if a stored value is longer than 80 characters
    op.alter_column('calculation_outputs', 'value', existing_type=sa.Unicode(length=1000), type_=sa.Unicode(length=80), existing_nullable=False)
    op.drop_column('methodology_versions', 'calculation_readiness_module_version')
