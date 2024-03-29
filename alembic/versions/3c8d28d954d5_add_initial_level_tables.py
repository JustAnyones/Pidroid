"""Add initial level tables

Revision ID: 3c8d28d954d5
Revises: e4ab9de39520
Create Date: 2023-01-15 20:47:31.740632

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3c8d28d954d5'
down_revision = 'e4ab9de39520'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('LevelRewards',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=True),
    sa.Column('level', sa.Integer(), nullable=True),
    sa.Column('role_id', sa.BigInteger(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('UserLevels',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=True),
    sa.Column('user_id', sa.BigInteger(), nullable=True),
    sa.Column('total_xp', sa.BigInteger(), nullable=True),
    sa.Column('current_xp', sa.BigInteger(), nullable=True),
    sa.Column('messages_sent', sa.BigInteger(), nullable=True),
    sa.Column('level', sa.BigInteger(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('GuildConfigurations', sa.Column('xp_system_active', sa.Boolean(), server_default='false', nullable=True))
    op.add_column('GuildConfigurations', sa.Column('xp_per_message_min', sa.BigInteger(), server_default='15', nullable=True))
    op.add_column('GuildConfigurations', sa.Column('xp_per_message_max', sa.BigInteger(), server_default='25', nullable=True))
    op.add_column('GuildConfigurations', sa.Column('xp_multiplier', sa.BigInteger(), server_default='1', nullable=True))
    op.add_column('GuildConfigurations', sa.Column('xp_exempt_roles', sa.ARRAY(sa.BigInteger()), server_default='{}', nullable=True))
    op.add_column('GuildConfigurations', sa.Column('xp_exempt_channels', sa.ARRAY(sa.BigInteger()), server_default='{}', nullable=True))
    op.drop_column('GuildConfigurations', 'strict_anti_phishing')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('GuildConfigurations', sa.Column('strict_anti_phishing', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True))
    op.drop_column('GuildConfigurations', 'xp_exempt_channels')
    op.drop_column('GuildConfigurations', 'xp_exempt_roles')
    op.drop_column('GuildConfigurations', 'xp_multiplier')
    op.drop_column('GuildConfigurations', 'xp_per_message_max')
    op.drop_column('GuildConfigurations', 'xp_per_message_min')
    op.drop_column('GuildConfigurations', 'xp_system_active')
    op.drop_table('UserLevels')
    op.drop_table('LevelRewards')
    # ### end Alembic commands ###
