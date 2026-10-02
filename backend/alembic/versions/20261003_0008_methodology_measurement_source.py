"""Decision V2-A: explicit measurement provenance on methodology monitoring rules.

Adds `methodology_monitoring_rules.measurement_source` (FIELD / FIELD_ACTIVITY / LABORATORY / UNCLASSIFIED, NOT NULL, CHECK).
The platform never infers the value from a unit, name, numeric type or sampling frequency.

Backfill of existing rows (deterministic; nothing is guessed):
- the DEMO soil-sampling rule `DM1` of the DEMO methodologies `DEMO-ALM-SOC` and `DEMO-CCTS-SOIL` (environment DEMO) →
  LABORATORY. This is the known intended semantics of the DEMO definition in `app/seed/demo_methodologies.py` ("Soil sampling
  per stratum (DEMO)", soil organic carbon analysed on the samples). It is an explicit assignment by methodology code and rule
  code, not a classification rule.
- every other existing row → UNCLASSIFIED. Such rules cannot be captured in Phase 5 (MEASUREMENT_SOURCE_UNCLASSIFIED), are a
  CONFIGURATION_REQUIRED gap for MRV plans, and a version containing one cannot be submitted or approved; a methodology
  specialist classifies them in a new version.
Each backfilled row gets one methodology change-history entry (idempotent: re-running the upgrade adds none twice).
Rule-set revision counters are not changed: the classification records an existing intent, it is not a rule edit.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0008'
down_revision: str | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHANGE_TYPE = 'METHODOLOGY_RULE_SOURCE_BACKFILLED'
DEMO_LABORATORY = [('DEMO-ALM-SOC', 'DM1'), ('DEMO-CCTS-SOIL', 'DM1')]


def upgrade() -> None:
    op.add_column('methodology_monitoring_rules', sa.Column('measurement_source', sa.Unicode(length=20), nullable=True))
    for code, rule_code in DEMO_LABORATORY:
        op.execute(sa.text("""
            UPDATE r SET measurement_source = 'LABORATORY'
            FROM methodology_monitoring_rules r
            JOIN methodology_versions v ON v.id = r.methodology_version_id
            JOIN methodologies m ON m.id = v.methodology_id
            WHERE m.code = :code AND m.environment = 'DEMO' AND r.rule_code = :rule AND r.measurement_source IS NULL
        """).bindparams(code=code, rule=rule_code))
    op.execute(sa.text("UPDATE methodology_monitoring_rules SET measurement_source = 'UNCLASSIFIED' WHERE measurement_source IS NULL"))
    op.alter_column('methodology_monitoring_rules', 'measurement_source', existing_type=sa.Unicode(length=20), nullable=False)
    op.create_check_constraint('ck_methodology_monitoring_rules_measurement_source', 'methodology_monitoring_rules',
                               "measurement_source IN ('FIELD', 'FIELD_ACTIVITY', 'LABORATORY', 'UNCLASSIFIED')")
    # audit trail: one change-history entry per backfilled rule (the history table is append-only)
    op.execute(sa.text(f"""
        INSERT INTO methodology_change_history (methodology_id, methodology_version_id, change_type, summary, old_value, new_value, reason)
        SELECT v.methodology_id, v.id, '{CHANGE_TYPE}',
               CONCAT('Monitoring rule ', r.rule_code, ' measurement source set to ', r.measurement_source, ' by migration 0008'),
               NULL,
               CONCAT('{{"rule_id": "', CONVERT(NVARCHAR(36), r.id), '", "rule_code": "', r.rule_code, '", "measurement_source": "',
                      r.measurement_source, '"}}'),
               CASE WHEN r.measurement_source = 'LABORATORY'
                    THEN 'Decision V2-A: DEMO soil-sampling rule DM1 is analysed in the laboratory (DEMO definition)'
                    ELSE 'Decision V2-A: existing rule could not be classified safely; a specialist must classify it in a new version' END
        FROM methodology_monitoring_rules r
        JOIN methodology_versions v ON v.id = r.methodology_version_id
        WHERE NOT EXISTS (SELECT 1 FROM methodology_change_history h
                          WHERE h.change_type = '{CHANGE_TYPE}' AND h.methodology_version_id = v.id
                            AND h.new_value LIKE CONCAT('%', CONVERT(NVARCHAR(36), r.id), '%'))
    """))


def downgrade() -> None:
    # the change-history entries stay (append-only by trigger); the upgrade does not duplicate them
    op.drop_constraint('ck_methodology_monitoring_rules_measurement_source', 'methodology_monitoring_rules', type_='check')
    op.drop_column('methodology_monitoring_rules', 'measurement_source')
