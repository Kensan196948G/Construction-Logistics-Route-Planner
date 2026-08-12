"""Add route_candidates.generation for route regeneration history

Revision ID: a1b2c3d4e5f6
Revises: 9f5c4e3b2a10
Create Date: 2026-08-12

Generation is an additive, non-destructive column: regenerating a project's
routes keeps the previous batch in the database (audit trail + confirmation
history) while list/report queries expose only the latest batch.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "9f5c4e3b2a10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "route_candidates",
        sa.Column("generation", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("route_candidates", "generation")
