"""Remove a table and a row

Revision ID: c8d1a40ab779
Revises: 58da93f13d53
Create Date: 2023-04-10 20:58:52.260814

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8d1a40ab779'
down_revision = '58da93f13d53'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('UserLevels')
    op.drop_column('GuildConfigurations', 'xp_multiplier')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('GuildConfigurations', sa.Column('xp_multiplier', sa.BIGINT(), server_default=sa.text("'1'::bigint"), autoincrement=False, nullable=True))
    op.create_table('UserLevels',
    sa.Column('id', sa.BIGINT(), server_default=sa.text('nextval(\'"UserLevels_id_seq"\'::regclass)'), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BIGINT(), autoincrement=False, nullable=True),
    sa.Column('user_id', sa.BIGINT(), autoincrement=False, nullable=True),
    sa.Column('total_xp', sa.BIGINT(), autoincrement=False, nullable=True),
    sa.Column('current_xp', sa.BIGINT(), autoincrement=False, nullable=True),
    sa.Column('level', sa.BIGINT(), autoincrement=False, nullable=True),
    sa.Column('xp_to_next_level', sa.BIGINT(), server_default=sa.text("'100'::bigint"), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('id', name='UserLevels_pkey')
    )
    # ### end Alembic commands ###
