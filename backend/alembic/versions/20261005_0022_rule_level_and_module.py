"""Monitoring-rule data level and the calculation module selected on a methodology version.

`methodology_monitoring_rules.data_level` (PROJECT / FARM / STRATUM / SAMPLING_POINT, nullable): where the value is recorded.
MRV plans copy it onto the measurement definition; NULL keeps the earlier mapping (laboratory or unit -> sampling point,
otherwise farm). Needed so that e.g. fertiliser N in kg is recorded per farm and a non-permanence risk rating per project.

`methodology_versions.calculation_module_code` (nullable): the registered calculation module chosen for the version on its
Calculation tab (e.g. VM0042-V2.2-QA2-QA3). It is chosen while the version is a DRAFT and approved with the version; the
calculation engine refuses a different module for a version that names one.

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0022'
down_revision: str | None = '0021'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('methodology_monitoring_rules', sa.Column('data_level', sa.Unicode(length=15), nullable=True))
    op.create_check_constraint(op.f('ck_methodology_monitoring_rules_data_level'), 'methodology_monitoring_rules',
                               "data_level IS NULL OR data_level IN ('PROJECT', 'FARM', 'STRATUM', 'SAMPLING_POINT')")
    op.add_column('methodology_versions', sa.Column('calculation_module_code', sa.Unicode(length=80), nullable=True))


def downgrade() -> None:
    op.execute(sa.text("""
        IF EXISTS (SELECT 1 FROM methodology_versions WHERE calculation_module_code IS NOT NULL)
           OR EXISTS (SELECT 1 FROM methodology_monitoring_rules WHERE data_level IS NOT NULL)
        BEGIN; THROW 51000, 'Downgrade refused: module selections or rule data levels are recorded.', 1; END;
    """))
    op.drop_column('methodology_versions', 'calculation_module_code')
    op.drop_constraint(op.f('ck_methodology_monitoring_rules_data_level'), 'methodology_monitoring_rules', type_='check')
    op.drop_column('methodology_monitoring_rules', 'data_level')
