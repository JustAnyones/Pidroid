from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pidroid.utils.api import API, UserLevelsTable

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

class LevelInformation:

    def __init__(self, api: API, table: UserLevelsTable, rank: int) -> None:
        self.__api = api
        self.__guild_id = table.guild_id
        self.__user_id = table.user_id
        self.__rank = rank
        self.__total_xp = table.total_xp
        self.__current_xp = table.current_xp
        self.__xp_to_level_up = table.xp_to_next_level
        self.__current_level = table.level

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
        """Returns the rank of the member."""
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
