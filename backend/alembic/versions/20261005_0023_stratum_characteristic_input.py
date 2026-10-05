"""Calculation inputs may come from a stratum characteristic.

The calculation framework reads per-stratum characteristics (e.g. VM0042's mean annual precipitation for the IPCC climate class)
as input source STRATUM_CHARACTERISTIC, but `calculation_inputs.source_type` only allowed the Phase 7 sources, so freezing the
inputs of such a run failed on the check constraint. This widens the constraint.

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-05
"""
from collections.abc import Sequence

from alembic import op

revision: str = '0023'
down_revision: str | None = '0022'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = "source_type IN ('LAB_RESULT', 'MONITORING_RECORD', 'STRATUM_AREA', 'SAMPLING_DESIGN_PARAMETER', 'MODULE_CONSTANT')"
NEW = ("source_type IN ('LAB_RESULT', 'MONITORING_RECORD', 'STRATUM_AREA', 'SAMPLING_DESIGN_PARAMETER', 'MODULE_CONSTANT', "
       "'STRATUM_CHARACTERISTIC')")


def upgrade() -> None:
    op.drop_constraint(op.f('ck_calculation_inputs_source_type'), 'calculation_inputs', type_='check')
    op.create_check_constraint(op.f('ck_calculation_inputs_source_type'), 'calculation_inputs', NEW)


def downgrade() -> None:
    # calculation inputs are append-only: a downgrade fails if frozen runs already hold STRATUM_CHARACTERISTIC inputs
    op.drop_constraint(op.f('ck_calculation_inputs_source_type'), 'calculation_inputs', type_='check')
    op.create_check_constraint(op.f('ck_calculation_inputs_source_type'), 'calculation_inputs', OLD)
