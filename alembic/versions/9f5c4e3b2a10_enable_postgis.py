"""enable_postgis

Revision ID: 9f5c4e3b2a10
Revises: b1d15542540b
Create Date: 2026-08-05 19:00:00.000000

Enables the PostGIS extension when the target database is PostgreSQL.
SQLite (local MVP) keeps the existing lat/lng FLOAT columns and skips this.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9f5c4e3b2a10"
down_revision: str | Sequence[str] | None = "b1d15542540b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def downgrade() -> None:
    """Downgrade schema (PostGIS extension is left installed by design)."""
    # Extension removal would affect other schemas in the same database, so we
    # intentionally do not DROP EXTENSION postgis on downgrade.
