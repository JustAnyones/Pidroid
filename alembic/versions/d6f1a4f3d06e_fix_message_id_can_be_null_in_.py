"""Fix message_id can be null in Suggestions

Revision ID: d6f1a4f3d06e
Revises: 92b55b3bbe0d
Create Date: 2023-08-24 18:19:17.097811

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd6f1a4f3d06e'
down_revision = '92b55b3bbe0d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('Suggestions', 'message_id',
               existing_type=sa.BIGINT(),
               nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('Suggestions', 'message_id',
               existing_type=sa.BIGINT(),
               nullable=False)
    # ### end Alembic commands ###
