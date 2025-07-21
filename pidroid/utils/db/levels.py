from discord import Colour
from sqlalchemy import BigInteger, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from typing import override

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
    "ja": (":black_square_button:", "#AD8B87"), # custom logic
}
SQUARE_COUNT = 10

JA_CURRENT_SQUARES = [
    "<:ja1:1396837098882990150>",
    "<:ja2:1396837111126036553>",
    "<:ja3:1396837120190054532>",
    "<:ja4:1396837128159236249>",
    "<:ja5:1396837144613355673>",
    "<:ja6:1396837154814169162>",
]
JA_REMAINING_SQUARES = [
    "<:ja1g:1396837478400262266>",
    "<:ja2g:1396837487963406456>",
    "<:ja3g:1396837495634792458>",
    "<:ja4g:1396837503465689240>",
    "<:ja5g:1396837514790178907>",
    "<:ja6g:1396837522235068517>",
]

assert len(JA_CURRENT_SQUARES) == len(JA_REMAINING_SQUARES), "JA_CURRENT_SQUARES must be the same length as JA_REMAINING_SQUARES"

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

    async def calculate_rank(self, session: AsyncSession) -> int:
        instance = await session.merge(self)

        # Query to calculate the rank
        rank_subquery = (
            select(
                UserLevels,
                func.rank().over(order_by=UserLevels.total_xp.desc()).label("rank")
            )
            .where(UserLevels.guild_id == instance.guild_id)
            .subquery()
        )

        # Get the rank for the current instance
        query = (
            select(rank_subquery)
            .where(rank_subquery.c.user_id == instance.user_id)
        )
        result = await session.execute(query)
        row = result.fetchone()
        if row is None:
            return -1
        value: int = row[-1] # last column
        return value

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
    
    def __get_ja_progress_bar(self, current_square_count: int) -> str:
        """Returns a progress bar string for the current level using JA emotes."""
        total_square_count = len(JA_CURRENT_SQUARES)

        current_prog = ""
        remaining_prog = ""
        for i in range(current_square_count):
            current_prog += JA_CURRENT_SQUARES[i]
        for i in range(current_square_count, total_square_count):
            remaining_prog += JA_REMAINING_SQUARES[i]

        return f'{current_prog}{remaining_prog}'

    def get_progress_bar(self) -> str:
        """Returns a progress bar string for the current level."""
        # https://github.com/KumosLab/Discord-Levels-Bot/blob/b01e22a9213b004eed5f88d68b500f4f4cd04891/KumosLab/Database/Create/RankCard/text.py
        dashes = SQUARE_COUNT
        current_dashes = int(self.current_xp / int(self.xp_to_next_level / dashes))

        # JA theme has custom logic
        if self.theme_name == "ja":
            return self.__get_ja_progress_bar(current_dashes)

        # Select progress character to use
        character = self.default_progress_character
        if self.progress_character:
            character = self.progress_character

        current_prog = f'{character}' * current_dashes
        remaining_prog = '⬛' * (dashes - current_dashes)
        return f'{current_prog}{remaining_prog}'

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
