from typing import override
from discord import Colour
from sqlalchemy import BigInteger, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property

from pidroid.utils.db.base import Base

COLOUR_BINDINGS = {
    "blue": (":blue_square:", "#55acee"),
    "brown": (":brown_square:", "#c1694f"),
    "green": (":green_square:", "#78b159"),
    "orange": (":orange_square:", "#f4900c"),
    "purple": (":purple_square:", "#aa8ed6"),
    "red": (":red_square:", "#dd2e44"),
    "white": (":white_large_square:", "#e6e7e8"),
    "yellow": (":yellow_square:", "#fdcb58"), 
}

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

    @hybrid_property
    async def rank(self):
        # This part is used when accessing the property on an instance
        return await self._calculate_rank()

    async def _calculate_rank(self) -> int:
        # Create a session (you may need to modify this if you have a different way of managing sessions)
        session: AsyncSession | None = AsyncSession.object_session(self)
        if session is None:
            raise ValueError("Session is not available")

        # Query to calculate the rank
        rank_subquery = (
            select(
                func.rank().over(order_by=UserLevels.total_xp.desc()).label("rank")
            )
            .filter(UserLevels.guild_id == self.guild_id)
            .subquery()
        )

        # Get the rank for the current instance
        query = (
            select(rank_subquery)
            .filter(rank_subquery.c.id == self.id)
        )
        result = await session.execute(query)

        return result.scalar()


    def _get_theme_bindings(self) -> tuple[str, str] | None:
        """Returns theme bindings for the current user."""
        if self.theme_name is None:
            return None
        return COLOUR_BINDINGS.get(self.theme_name)

    @property
    def default_progress_character(self) -> str:
        """Returns default progress character for use in level progression display."""
        return COLOUR_BINDINGS["green"][0]

    @property
    def progress_character(self) -> str | None:
        """Returns custom progress character for use in level progression display."""
        bindings = self._get_theme_bindings()
        if bindings:
            return bindings[0]
        return None

    @property
    def default_embed_colour(self) -> Colour:
        """Returns default embed colour for use in level progression display."""
        return Colour.from_str(COLOUR_BINDINGS["green"][1])
    
    @property
    def embed_colour(self) -> Colour | None:
        """Returns custom embed colour for use in level progression display."""
        bindings = self._get_theme_bindings()
        if bindings:
            return Colour.from_str(bindings[1])
        return None

    @override
    def __repr__(self) -> str:
        return f'<UserLevels guild_id={self.guild_id} user_id={self.user_id} current_level={self.level}>'

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