"""External farm reference data: append-only weather / soil / satellite NDVI observations (evidence only).

Table: farm_external_observations (farm, boundary version, organization, environment, data type, provider, dataset, period, centroid,
request JSON without credentials, normalised summary JSON, SHA-256 of the provider's raw response, who / when). A trigger makes it
append-only (no UPDATE, no DELETE). Additive: no existing table changes; nothing reads it in a workflow or a calculation.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-04 15:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = '0019'
down_revision: str | None = '0018'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('farm_external_observations',
    sa.Column('farm_id', sa.Uuid(), nullable=False),
    sa.Column('boundary_id', sa.Uuid(), nullable=True),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('environment', sa.Unicode(length=10), nullable=False),
    sa.Column('data_type', sa.Unicode(length=20), nullable=False),
    sa.Column('provider', sa.Unicode(length=40), nullable=False),
    sa.Column('dataset', sa.Unicode(length=120), nullable=False),
    sa.Column('period_start', sa.Date(), nullable=True),
    sa.Column('period_end', sa.Date(), nullable=True),
    sa.Column('latitude', sa.Numeric(precision=10, scale=7), nullable=False),
    sa.Column('longitude', sa.Numeric(precision=10, scale=7), nullable=False),
    sa.Column('request', sa.UnicodeText(), nullable=False),
    sa.Column('summary', sa.UnicodeText(), nullable=False),
    sa.Column('raw_sha256', sa.Unicode(length=64), nullable=False),
    sa.Column('fetched_by', sa.Uuid(), nullable=False),
    sa.Column('fetched_at', mssql.DATETIME2(), server_default=sa.text('SYSUTCDATETIME()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("data_type IN ('WEATHER', 'SOIL', 'SATELLITE_NDVI', 'LAND_RECORD')",
                       name=op.f('ck_farm_external_observations_data_type')),
    sa.CheckConstraint("environment IN ('LIVE', 'DEMO')", name=op.f('ck_farm_external_observations_environment')),
    sa.CheckConstraint('ISJSON(summary) = 1 AND ISJSON(request) = 1', name=op.f('ck_farm_external_observations_json')),
    sa.CheckConstraint('period_start IS NULL OR period_end IS NULL OR period_start <= period_end',
                       name=op.f('ck_farm_external_observations_period')),
    sa.CheckConstraint('latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180',
                       name=op.f('ck_farm_external_observations_location')),
    sa.ForeignKeyConstraint(['boundary_id'], ['farm_boundaries.id'], name=op.f('fk_farm_external_observations_boundary_id_farm_boundaries')),
    sa.ForeignKeyConstraint(['farm_id'], ['farms.id'], name=op.f('fk_farm_external_observations_farm_id_farms')),
    sa.ForeignKeyConstraint(['fetched_by'], ['users.id'], name=op.f('fk_farm_external_observations_fetched_by_users')),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'],
                            name=op.f('fk_farm_external_observations_organization_id_organizations')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_farm_external_observations'))
    )
    op.create_index('ix_farm_external_observations_farm', 'farm_external_observations', ['farm_id', 'data_type', 'fetched_at'],
                    unique=False)
    # ---- hand-written: external evidence is append-only (a new fetch is a new row)
    op.execute("""
CREATE TRIGGER trg_farm_external_observations_append_only ON dbo.farm_external_observations
AFTER UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    THROW 51000, 'farm_external_observations: external evidence is append-only; rows are never changed or deleted.', 1;
END""")


def downgrade() -> None:
    # ---- hand-written: recorded evidence is never dropped silently
    op.execute("""
IF EXISTS (SELECT 1 FROM dbo.farm_external_observations)
BEGIN;
    THROW 51000, 'Downgrade refused: external farm observations exist.', 1;
END;""")
    op.execute("DROP TRIGGER IF EXISTS trg_farm_external_observations_append_only")
    op.drop_index('ix_farm_external_observations_farm', table_name='farm_external_observations')
    op.drop_table('farm_external_observations')
