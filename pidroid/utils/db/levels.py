from typing import override
from sqlalchemy import BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from pidroid.utils.db.base import Base

class UserLevels(Base):
    __tablename__ = "UserLevels"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, doc="xd")
    guild_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    total_xp: Mapped[int] = mapped_column(BigInteger, server_default="0")
    current_xp: Mapped[int] = mapped_column(BigInteger, server_default="0")
    xp_to_next_level: Mapped[int] = mapped_column(BigInteger, server_default="100")
    level: Mapped[int] = mapped_column(BigInteger, server_default="0")
    theme_name: Mapped[str | None] = mapped_column(Text, nullable=True)

class LevelRewards(Base):
    __tablename__ = "LevelRewards"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # The ID of the guild the reward is for
    guild_id: Mapped[int] = mapped_column(BigInteger)
    # The required level to obtain the reward
    level: Mapped[int] = mapped_column(BigInteger)
    # The ID of the role that is to be rewarded
    role_id: Mapped[int] = mapped_column(BigInteger)

    @override
    def __repr__(self) -> str:
        return f'<LevelRewards id={self.id} guild_id={self.guild_id} level={self.level} role_id={self.role_id}>'