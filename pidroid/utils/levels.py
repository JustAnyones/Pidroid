from __future__ import annotations

import logging

from discord import Member, Colour
from typing import TYPE_CHECKING, override

from pidroid.utils.db.levels import LevelRewards, UserLevels

if TYPE_CHECKING:
    from pidroid.utils.api import API

logger = logging.getLogger('Pidroid')

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

class MemberLevelInfo:

    def __init__(
        self,
        api: API,
        id: int,
        guild_id: int,
        user_id: int,
        total_xp: int,
        current_xp: int,
        xp_to_level_up: int,
        current_level: int,
        *,
        theme_name: str | None,
        rank: int = -1
    ) -> None:
        super().__init__()
        self.__api = api
        self.__id = id
        self.__guild_id = guild_id
        self.__user_id = user_id
        self.__total_xp = total_xp
        self.__current_xp = current_xp
        self.__xp_to_level_up = xp_to_level_up
        self.__current_level = current_level
        self.__theme_name = theme_name
        self.__rank = rank

    @override
    def __repr__(self) -> str:
        return f'<MemberLevelInfo guild_id={self.__guild_id} user_id={self.__user_id} current_level={self.__current_level}>'

    @classmethod
    def from_table(cls, api: API, table: UserLevels, rank: int = -1) -> MemberLevelInfo:
        """Constructs level information from a UserLevelsTable object."""
        return cls(
            api,
            table.id,
            table.guild_id,
            table.user_id,
            table.total_xp,
            table.current_xp,
            table.xp_to_next_level,
            table.level,
            theme_name=table.theme_name,
            rank=rank
        )

    @property
    def row(self) -> int:
        """Returns the row of the object in the database."""
        return self.__id

    @property
    def guild_id(self) -> int:
        """Returns the ID of the guild the member is in."""
        return self.__guild_id

    @property
    def user_id(self) -> int:
        """Returns the ID of the member this information belongs to."""
        return self.__user_id

    @property
    def rank(self) -> int:
        """Returns the rank of the member.
        
        -1, if not provided."""
        return self.__rank

    @property
    def total_xp(self) -> int:
        """Returns the total amount of XP the member has."""
        return self.__total_xp

    @property
    def current_xp(self) -> int:
        """Returns the current level XP the member has."""
        return self.__current_xp

    @property
    def xp_to_level_up(self) -> int:
        """Returns the required amount of XP to level up."""
        return self.__xp_to_level_up

    @property
    def current_level(self) -> int:
        """Returns the current member level."""
        return self.__current_level

    @property
    def theme_name(self) -> str | None:
        """Returns the name of the theme if available."""
        return self.__theme_name

    def _get_theme_bindings(self) -> tuple[str, str] | None:
        """Returns theme bindings for the current user."""
        if self.__theme_name is None:
            return None
        return COLOUR_BINDINGS.get(self.__theme_name)

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

    async def fetch_member(self) -> Member | None:
        """Fetches the member object associated with this level information."""
        guild = self.__api.client.get_guild(self.__guild_id)
        if guild is None:
            logger.warning(f'Failed to acquire guild {self.__guild_id} while fetching member information from LevelInformation')
            return None
        return await self.__api.client.get_or_fetch_member(guild, self.__user_id)

    async def fetch_eligible_level_rewards(self) -> list[LevelRewards]:
        """Returns a list of eligible level rewards for the user."""
        return await self.__api.fetch_eligible_level_rewards_for_level(self.__guild_id, self.__current_level)

    async def fetch_eligible_level_reward(self) -> LevelRewards | None:
        """Returns the most eligible level reward for the user."""
        return await self.__api.fetch_eligible_level_reward_for_level(self.__guild_id, self.__current_level)

    async def update_theme_name(self, theme_name: str) -> None:
        """Updates the theme name."""
        await self.__api.update_user_level_theme(self.__id, theme_name)
