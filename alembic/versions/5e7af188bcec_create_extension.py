"""Create extension

Revision ID: 5e7af188bcec
Revises: d6f1a4f3d06e
Create Date: 2025-03-29 17:20:03.016725

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5e7af188bcec'
down_revision = 'd6f1a4f3d06e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
