from __future__ import annotations

from discord import Guild
from discord.utils import MISSING
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from pidroid.utils.api import API, GuildConfigurationTable

class GuildConfiguration:

    def __init__(self, api: API) -> None:
        self.api = api

    @classmethod
    def from_table(cls: type[GuildConfiguration], api: API, table: GuildConfigurationTable) -> GuildConfiguration:
        """Constructs level reward from a LevelRewardsTable object."""
        obj = cls(api)
        obj.__from_table(table)
        return obj

    def __from_table(self, table: GuildConfigurationTable) -> None:
        """Creates a GuildConfiguration object from a table object."""
        self.__id: int = table.id # type: ignore
        self.__guild_id: int = table.guild_id # type: ignore

        self.__prefixes: List[str] = table.prefixes # type: ignore

        self.__jail_channel_id: Optional[int] = table.jail_channel # type: ignore
        self.__jail_role_id: Optional[int] = table.jail_role # type: ignore
        self.__log_channel_id: Optional[int] = table.log_channel # type: ignore

        self.__public_tags: bool = table.public_tags # type: ignore
        self.__allow_punishing_moderators: bool = table.punishing_moderators # type: ignore

        self.__appeal_url: Optional[str] = table.appeal_url # type: ignore

        # XP system related information
        self.__xp_system_active: bool = table.xp_system_active # type: ignore
        self.__xp_multiplier: float = table.xp_multiplier # type: ignore
        self.__xp_per_message_min: int = table.xp_per_message_min # type: ignore
        self.__xp_per_message_max: int = table.xp_per_message_max # type: ignore
        self.__xp_exempt_roles: List[int] = table.xp_exempt_roles # type: ignore
        self.__xp_exempt_channels: List[int] = table.xp_exempt_channels # type: ignore
        self.__stack_level_rewards: bool = table.stack_level_rewards # type: ignore

        # Suggestion system related information
        self.__suggestion_system_active: bool = table.suggestion_system_active # type: ignore
        self.__suggestion_channel_id: Optional[int] = table.suggestion_channel # type: ignore
        self.__suggestion_threads_enabled: bool = table.suggestion_threads_enabled # type: ignore

    async def _update(self) -> None:
        await self.api._update_guild_configuration(
            self.__id,

            prefixes=self.__prefixes,
            public_tags=self.__public_tags,

            jail_channel=self.__jail_channel_id,
            jail_role=self.__jail_role_id,
            log_channel=self.__log_channel_id,
            punishing_moderators=self.__allow_punishing_moderators,
            appeal_url=self.__appeal_url,

            xp_system_active=self.__xp_system_active,
            xp_multiplier=self.__xp_multiplier,
            xp_exempt_roles=self.__xp_exempt_roles,
            xp_exempt_channels=self.__xp_exempt_channels,
            stack_level_rewards=self.__stack_level_rewards,

            suggestion_system_active=self.__suggestion_system_active,
            suggestion_channel=self.__suggestion_channel_id,
            suggestion_threads_enabled=self.__suggestion_threads_enabled
        )

    @property
    def guild_id(self) -> int:
        """The ID of the guild this configuration belongs to."""
        return self.__guild_id

    @property
    def guild(self) -> Optional[Guild]:
        """The guild this configuration belongs to."""
        return self.api.client.get_guild(self.__guild_id)

    async def edit(
        self,
        *,
        prefixes: List[str] = MISSING,
        public_tags: bool = MISSING,

        jail_channel_id: Optional[int] = MISSING,
        jail_role_id: Optional[int] = MISSING,
        allow_moderator_punishing: bool = MISSING,
        appeal_url: Optional[str] = MISSING,

        xp_system_active: bool = MISSING,
        xp_multiplier: float = MISSING,
        stack_level_rewards: bool = MISSING,

        suggestion_system_active: bool = MISSING,
        suggestion_channel_id: Optional[int] = MISSING,
        suggestion_threads_enabled: bool = MISSING,
    ) -> None:
        """Edits the guild configuration."""

        # General
        if prefixes is not MISSING:
            self.__prefixes = prefixes.copy()

        if public_tags is not MISSING:
            self.__public_tags = public_tags

        # Moderation
        if jail_channel_id is not MISSING:
            self.__jail_channel_id = jail_channel_id

        if jail_role_id is not MISSING:
            self.__jail_role_id = jail_role_id

        if allow_moderator_punishing is not MISSING:
            self.__allow_punishing_moderators = allow_moderator_punishing

        if appeal_url is not MISSING:
            self.__appeal_url = appeal_url

        # XP System
        if xp_system_active is not MISSING:
            self.__xp_system_active = xp_system_active

        if xp_multiplier is not MISSING:
            self.__xp_multiplier = xp_multiplier

        if stack_level_rewards is not MISSING:
            self.__stack_level_rewards = stack_level_rewards

        # Suggestions
        if suggestion_system_active is not MISSING:
            self.__suggestion_system_active = suggestion_system_active

        if suggestion_channel_id is not MISSING:
            self.__suggestion_channel_id = suggestion_channel_id

        if suggestion_threads_enabled is not MISSING:
            self.__suggestion_threads_enabled = suggestion_threads_enabled

        await self._update()

        # Dispatch level stacking change
        if stack_level_rewards is not MISSING:
            self.api.client.dispatch("pidroid_level_stacking_change", self.guild)

        # Update guild prefixes
        if prefixes is not MISSING:
            self.api.client.update_guild_prefixes_from_config(self.guild_id, self)

    async def delete(self) -> None:
        """Deletes the current guild configuration from the database."""
        await self.api.delete_guild_configuration(self.__id)
    
    @property
    def prefixes(self) -> List[str]:
        """Returns guild prefixes."""
        return self.__prefixes.copy()

    @property
    def public_tags(self) -> bool:
        """Returns true if tag system can be management by regular members."""
        return self.__public_tags

    """Moderation related"""

    @property
    def jail_channel_id(self) -> Optional[int]:
        """Returns the ID of the jail channel, if available."""
        return self.__jail_channel_id

    @property
    def jail_role_id(self) -> Optional[int]:
        """Returns the ID of the jail role, if available."""
        return self.__jail_role_id

    @property
    def logging_channel_id(self) -> Optional[int]:
        """Returns the ID of the logging channel if available."""
        return self.__log_channel_id

    @property
    def allow_to_punish_moderators(self) -> bool:
        """Returns true if moderators are allowed to punish lower ranking moderators."""
        return self.__allow_punishing_moderators

    @property
    def appeal_url(self) -> Optional[str]:
        """Returns the ban appeal URL."""
        return self.__appeal_url

    """XP system related"""

    @property
    def xp_system_active(self) -> bool:
        """Returns true if the XP system is active for the server."""
        return self.__xp_system_active # type: ignore

    @property
    def xp_multiplier(self) -> float:
        """Returns the XP multiplier per message."""
        return self.__xp_multiplier
    
    @property
    def xp_per_message_min(self) -> int:
        """Returns the minimum amount of XP that can be received per message."""
        return self.__xp_per_message_min

    @property
    def xp_per_message_max(self) -> int:
        """Returns the maximum amount of XP that can be received per message."""
        return self.__xp_per_message_max

    @property
    def xp_exempt_roles(self) -> List[int]:
        """Returns a list of XP exempt role IDs."""
        return self.__xp_exempt_roles
    
    async def add_xp_exempt_role_id(self, role_id: int) -> None:
        """Adds the specified role ID to the XP exempt role list."""
        if role_id in self.__xp_exempt_roles:
            return
        self.__xp_exempt_roles.append(role_id)
        await self._update()

    async def remove_xp_exempt_role_id(self, role_id: int) -> None:
        """Removes the specified role ID from the XP exempt role list."""
        if role_id not in self.__xp_exempt_roles:
            return
        self.__xp_exempt_roles.remove(role_id)
        await self._update()

    @property
    def xp_exempt_channels(self) -> List[int]:
        """Returns a list of XP exempt channel IDs."""
        return self.__xp_exempt_channels

    async def add_xp_exempt_channel_id(self, channel_id: int) -> None:
        """Adds the specified channel ID to the XP exempt channel list."""
        if channel_id in self.__xp_exempt_channels:
            return
        self.__xp_exempt_channels.append(channel_id)
        await self._update()

    async def remove_xp_exempt_channel_id(self, channel_id: int) -> None:
        """Removes the specified channel ID from the XP exempt channel list."""
        if channel_id not in self.__xp_exempt_channels:
            return
        self.__xp_exempt_channels.remove(channel_id)
        await self._update()

    @property
    def level_rewards_stacked(self) -> bool:
        """Returns true if level rewards obtained from the level system should be stacked."""
        return self.__stack_level_rewards

    """Logging system related"""
    
    @property
    def logging_active(self) -> bool:
        """Returns true if logging system is enabled for the server."""
        return True # TODO: fix


    """Suggestions related"""

    @property
    def suggestion_system_active(self) -> bool:
        """Returns true if suggestion system is enabled for the server."""
        return self.__suggestion_system_active

    @property
    def suggestions_channel_id(self) -> Optional[int]:
        """Returns the ID of the suggestions channel if available."""
        return self.__suggestion_channel_id

    @property
    def suggestion_threads_enabled(self) -> bool:
        """Returns true if expiring thread creation is enabled for the suggestion system."""
        return self.__suggestion_threads_enabled

    async def fetch_all_level_rewards(self):
        """Returns a list of all level rewards in the guild."""
        return await self.api.fetch_all_guild_level_rewards(self.__guild_id)
    
    async def fetch_member_level(self, member_id: int):
        """Returns member level object."""
        return await self.api.fetch_user_level_info(self.__guild_id, member_id)

    async def fetch_all_member_levels(self):
        """Returns a list of member level information for every member in the guild."""
        return await self.api.fetch_guild_level_infos(self.__guild_id)
