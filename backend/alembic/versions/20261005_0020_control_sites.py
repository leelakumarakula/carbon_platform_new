"""VM0042 Quantification Approach 2: baseline control sites as strata with a role.

`project_strata.role` (PROJECT / CONTROL, NOT NULL, default PROJECT): a CONTROL stratum is a baseline control site. It is
sampled with the ordinary sampling-design / field-collection / laboratory flow, but its farms are NOT project participants
(no project area, carbon rights or payouts). `project_strata.linked_stratum_record_ids` (JSON array of PROJECT stratum record
ids) says which project strata the control site represents (VM0042 v2.2 §8.2 QA2: at least one control site per stratum).
Existing strata are PROJECT strata; nothing is guessed.

`stratum_characteristics.characteristic` gains the control-site similarity criteria of VM0042 Table 7: SOIL_TEXTURE,
SOIL_GROUP, SLOPE_CLASS, SOC_PERCENT, ECOREGION, PRECIPITATION_MM.

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0020'
down_revision: str | None = '0019'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = ["SOIL_TYPE", "CROP", "LAND_USE", "MANAGEMENT_PRACTICE", "IRRIGATION", "GEOGRAPHY", "CLIMATE", "OTHER"]
NEW = [*OLD, "SOIL_TEXTURE", "SOIL_GROUP", "SLOPE_CLASS", "SOC_PERCENT", "ECOREGION", "PRECIPITATION_MM"]


def _in(values: list[str]) -> str:
    return "characteristic IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.add_column('project_strata', sa.Column('role', sa.Unicode(length=10), nullable=False, server_default=sa.text("'PROJECT'")))
    op.add_column('project_strata', sa.Column('linked_stratum_record_ids', sa.UnicodeText(), nullable=True))
    op.create_check_constraint(op.f('ck_project_strata_role'), 'project_strata', "role IN ('PROJECT', 'CONTROL')")
    op.create_check_constraint(op.f('ck_project_strata_linked_json'), 'project_strata',
                               "linked_stratum_record_ids IS NULL OR ISJSON(linked_stratum_record_ids) = 1")
    # a control site always names the project strata it represents; a project stratum never does
    op.create_check_constraint(op.f('ck_project_strata_links'), 'project_strata',
                               "(role = 'CONTROL' AND linked_stratum_record_ids IS NOT NULL) OR "
                               "(role = 'PROJECT' AND linked_stratum_record_ids IS NULL)")
    op.drop_constraint(op.f('ck_stratum_characteristics_characteristic'), 'stratum_characteristics', type_='check')
    op.create_check_constraint(op.f('ck_stratum_characteristics_characteristic'), 'stratum_characteristics', _in(NEW))


def downgrade() -> None:
    op.execute(sa.text("""
        IF EXISTS (SELECT 1 FROM project_strata WHERE role = 'CONTROL')
           OR EXISTS (SELECT 1 FROM stratum_characteristics WHERE characteristic IN
                      ('SOIL_TEXTURE', 'SOIL_GROUP', 'SLOPE_CLASS', 'SOC_PERCENT', 'ECOREGION', 'PRECIPITATION_MM'))
        BEGIN; THROW 51000, 'Downgrade refused: control sites or VM0042 stratum characteristics are recorded.', 1; END;
    """))
    op.drop_constraint(op.f('ck_stratum_characteristics_characteristic'), 'stratum_characteristics', type_='check')
    op.create_check_constraint(op.f('ck_stratum_characteristics_characteristic'), 'stratum_characteristics', _in(OLD))
    op.drop_constraint(op.f('ck_project_strata_links'), 'project_strata', type_='check')
    op.drop_constraint(op.f('ck_project_strata_linked_json'), 'project_strata', type_='check')
    op.drop_constraint(op.f('ck_project_strata_role'), 'project_strata', type_='check')
    op.execute(sa.text("""
        DECLARE @df sysname = (SELECT d.name FROM sys.default_constraints d JOIN sys.columns c
                               ON c.default_object_id = d.object_id
                               WHERE d.parent_object_id = OBJECT_ID('project_strata') AND c.name = 'role');
        IF @df IS NOT NULL EXEC('ALTER TABLE project_strata DROP CONSTRAINT ' + @df);
    """))
    op.drop_column('project_strata', 'linked_stratum_record_ids')
    op.drop_column('project_strata', 'role')
