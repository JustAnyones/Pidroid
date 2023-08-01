from __future__ import annotations

import logging
import random

from typing import TYPE_CHECKING, List, Optional

from discord import Member, Role

from pidroid.models.guild_configuration import GuildConfiguration

logger = logging.getLogger('Pidroid')

if TYPE_CHECKING:
    from pidroid.utils.api import API, UserLevelsTable, LevelRewardsTable

def get_total_xp(level: int) -> float:
    """Returns the total amount of XP required to reach the specified level."""
    return 5 / 6 * level * (2 * level * level + 27 * level + 91)

def get_level_from_xp(xp: int) -> float:
    """Returns the level for the specified total XP."""
    total_xp = 0.0
    level = 0
    while total_xp < xp:
        level += 1
        total_xp = get_total_xp(level)
    previous_lvl_xp = get_total_xp(level - 1)
    return level - 1 + (xp - previous_lvl_xp) / (total_xp - previous_lvl_xp)

class LevelReward:

    def __init__(
        self,
        api: API,
        id: int,
        guild_id: int,
        role_id: int,
        level: int
    ) -> None:
        self.__api = api
        self.__id = id
        self.__guild_id = guild_id
        self.__role_id = role_id
        self.__level = level

    def __repr__(self) -> str:
        return f'<LevelReward id={self.__id} guild_id={self.__guild_id} role_id={self.__role_id} level={self.__level}>'

    @classmethod
    def from_table(cls: type[LevelReward], api: API, table: LevelRewardsTable) -> LevelReward:
        """Constructs level reward from a LevelRewardsTable object."""
        return cls(
            api,
            table.id, # type: ignore
            table.guild_id, # type: ignore
            table.role_id, # type: ignore
            table.level # type: ignore
        )

    @property
    def internal_id(self) -> int:
        """Returns the internal datbase ID associated with the reward."""
        return self.__id

    @property
    def guild_id(self) -> int:
        """Returns the ID of the guild the reward is for."""
        return self.__guild_id

    @property
    def role_id(self) -> int:
        """Returns the ID of the role that is to be rewarded."""
        return self.__role_id

    @property
    def level(self) -> int:
        """Returns the required level to obtain the reward."""
        return self.__level

    async def fetch_guild_configuration(self) -> GuildConfiguration:
        """Returns the guild configuration object associated with the guild this reward is in."""
        return await self.__api.client.fetch_guild_configuration(self.guild_id)

    async def fetch_next_reward(self):
        return await self.__api._fetch_next_level_reward(self.guild_id, self.level)

    async def fetch_previous_reward(self):
        return await self.__api._fetch_previous_level_reward(self.guild_id, self.level)

    async def fetch_role(self) -> Optional[Role]:
        """Fetches the role object associated with this level reward."""
        guild = self.__api.client.get_guild(self.guild_id)
        if guild is None:
            logger.warning(f'Failed to acquire guild {self.guild_id} while fetching role from LevelReward')
            return None
        return await self.__api.client.get_or_fetch_role(guild, self.role_id)

    async def delete(self):
        """Deletes the current level reward from the database."""
        await self.__api._delete_level_reward(self.internal_id)


class MemberLevelInfo:

    def __init__(
        self,
        api: API,
        guild_id: int,
        user_id: int,
        total_xp: int,
        current_xp: int,
        xp_to_level_up: int,
        current_level: int,
        rank: int = -1
    ) -> None:
        self.__api = api
        self.__guild_id = guild_id
        self.__user_id = user_id
        self.__total_xp = total_xp
        self.__current_xp = current_xp
        self.__xp_to_level_up = xp_to_level_up
        self.__current_level = current_level
        self.__rank = rank

    def __repr__(self) -> str:
        return f'<MemberLevelInfo guild_id={self.__guild_id} user_id={self.__user_id} current_level={self.__current_level}>'

    @classmethod
    def from_table(cls: type[MemberLevelInfo], api: API, table: UserLevelsTable, rank: int = -1) -> MemberLevelInfo:
        """Constructs level information from a UserLevelsTable object."""
        return cls(
            api,
            table.guild_id, # type: ignore
            table.user_id, # type: ignore
            table.total_xp, # type: ignore
            table.current_xp, # type: ignore
            table.xp_to_next_level, # type: ignore
            table.level, # type: ignore
            rank
        )

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
    def progress_character(self) -> str:
        """Returns a random character for use in level progression display."""
        # TODO: implement proper way, right now its random
        character = [
            ":blue_square:",
            ":brown_square:",
            ":green_square:",
            ":orange_square:",
            ":purple_square:",
            ":red_square:",
            ":white_large_square:",
            ":yellow_square:"
        ]
        return random.choice(character) # nosec

    async def fetch_member(self) -> Optional[Member]:
        """Fetches the member object associated with this level information."""
        guild = self.__api.client.get_guild(self.__guild_id)
        if guild is None:
            logger.warning(f'Failed to acquire guild {self.__guild_id} while fetching member information from LevelInformation')
            return None
        return await self.__api.client.get_or_fetch_member(guild, self.__user_id)

    async def fetch_eligible_level_rewards(self) -> List[LevelReward]:
        """Returns a list of eligible level rewards for the user."""
        return await self.__api.fetch_eligible_level_rewards_for_level(self.__guild_id, self.__current_level)

    async def fetch_eligible_level_reward(self) -> Optional[LevelReward]:
        """Returns the most eligible level reward for the user."""
        return await self.__api.fetch_eligible_level_reward_for_level(self.__guild_id, self.__current_level)
