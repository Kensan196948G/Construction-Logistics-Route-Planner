"""Add delivery/avoid-condition persistence and FK indexes

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-12

Delivery conditions (delivery_date, time_window, holiday,
night_delivery_allowed) and avoid conditions were accepted by the API but
dropped on persistence: the DB model had no columns for them. This revision is
additive and non-destructive: existing projects keep their data and simply
report the previous defaults ("daytime" / []) until re-edited.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("delivery_date", sa.Date(), nullable=True))
    op.add_column("projects", sa.Column("time_window", sa.String(length=50), nullable=True))
    op.add_column(
        "projects",
        sa.Column("holiday", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "projects",
        sa.Column("night_delivery_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("projects", sa.Column("avoid_conditions", sa.JSON(), nullable=True))

    # Foreign-key lookup indexes for the hot read paths (list by project,
    # latest-generation routes, risks per route, audit trail per project).
    op.create_index("ix_projects_owner_user_id", "projects", ["owner_user_id"])
    op.create_index("ix_project_locations_project_id", "project_locations", ["project_id"])
    op.create_index("ix_vehicle_conditions_project_id", "vehicle_conditions", ["project_id"])
    op.create_index("ix_route_candidates_project_id", "route_candidates", ["project_id"])
    op.create_index("ix_route_segments_route_id", "route_segments", ["route_id"])
    op.create_index("ix_route_risks_route_id", "route_risks", ["route_id"])
    op.create_index("ix_risk_comments_risk_id", "risk_comments", ["risk_id"])
    op.create_index("ix_reports_project_id", "reports", ["project_id"])
    op.create_index("ix_audit_logs_project_id", "audit_logs", ["project_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_public_geo_features_data_source_id", "public_geo_features", ["data_source_id"])
    op.create_index("ix_data_source_fetch_logs_data_source_id", "data_source_fetch_logs", ["data_source_id"])


def downgrade() -> None:
    op.drop_index("ix_data_source_fetch_logs_data_source_id", table_name="data_source_fetch_logs")
    op.drop_index("ix_public_geo_features_data_source_id", table_name="public_geo_features")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_project_id", table_name="audit_logs")
    op.drop_index("ix_reports_project_id", table_name="reports")
    op.drop_index("ix_risk_comments_risk_id", table_name="risk_comments")
    op.drop_index("ix_route_risks_route_id", table_name="route_risks")
    op.drop_index("ix_route_segments_route_id", table_name="route_segments")
    op.drop_index("ix_route_candidates_project_id", table_name="route_candidates")
    op.drop_index("ix_vehicle_conditions_project_id", table_name="vehicle_conditions")
    op.drop_index("ix_project_locations_project_id", table_name="project_locations")
    op.drop_index("ix_projects_owner_user_id", table_name="projects")
    op.drop_column("projects", "avoid_conditions")
    op.drop_column("projects", "night_delivery_allowed")
    op.drop_column("projects", "holiday")
    op.drop_column("projects", "time_window")
    op.drop_column("projects", "delivery_date")
