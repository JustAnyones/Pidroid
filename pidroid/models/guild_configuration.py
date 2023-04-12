from __future__ import annotations

from discord.channel import TextChannel
from discord.role import Role
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from pidroid.utils.api import API, GuildConfigurationTable

class GuildConfiguration:

    if TYPE_CHECKING:
        _id: int
        guild_id: int

        prefixes: List[str]

        jail_channel: Optional[int]
        jail_role: Optional[int]
        log_channel: Optional[int]

        public_tags: bool
        allow_punishing_moderators: bool

        suspicious_usernames: List[str]

        _appeal_url: Optional[str]

    def __init__(self, api: API, data: GuildConfigurationTable) -> None:
        self.api = api
        self._deserialize(data)

    def _deserialize(self, c: GuildConfigurationTable) -> None:
        """Creates a GuildConfiguration object from a table object."""
        self._id = c.id # type: ignore
        self.guild_id = c.guild_id # type: ignore

        self.prefixes = c.prefixes # type: ignore

        self.jail_channel = c.jail_channel # type: ignore
        self.jail_role = c.jail_role # type: ignore
        self.log_channel = c.log_channel # type: ignore

        self.public_tags = c.public_tags # type: ignore
        self.allow_punishing_moderators = c.punishing_moderators # type: ignore

        self.suspicious_usernames = c.suspicious_usernames # type: ignore

        self._appeal_url = c.appeal_url # type: ignore

        # XP system related information
        self.__xp_system_active = c.xp_system_active
        self.__xp_multiplier = c.xp_multiplier
        self.__xp_per_message_min = c.xp_per_message_min
        self.__xp_per_message_max = c.xp_per_message_max
        self.__xp_exempt_roles = c.xp_exempt_roles
        self.__xp_exempt_channels = c.xp_exempt_channels
        self.__stack_level_rewards = c.stack_level_rewards


    async def _update(self) -> None:
        await self.api._update_guild_configuration(
            self._id,
            self.jail_channel, self.jail_role,
            self.log_channel,
            self.prefixes,
            self.suspicious_usernames,
            self.public_tags,
            self.allow_punishing_moderators,
            self._appeal_url
        )

    @property
    def xp_system_active(self) -> bool:
        """Returns true if the XP system is active for the server."""
        return self.__xp_system_active

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

    @property
    def xp_exempt_channels(self) -> List[int]:
        """Returns a list of XP exempt channel IDs."""
        return self.__xp_exempt_channels

    @property
    def stack_level_rewards(self) -> bool:
        """Returns true if level rewards should be stacked."""
        return self.__stack_level_rewards

    @property
    def appeal_url(self) -> Optional[str]:
        """Returns the punishment appeal URL."""
        return self._appeal_url

    async def update_public_tag_permission(self, allow_public: bool) -> None:
        """Updates public tag permission."""
        self.public_tags = allow_public
        await self._update()
        
    async def update_moderator_punishing_permission(self, allow_punishing: bool) -> None:
        """Updates moderator punishing permission."""
        self.allow_punishing_moderators = allow_punishing
        await self._update()

    async def update_prefixes(self, prefix: str) -> None:
        """Updates the guild bot prefixes."""
        self.prefixes = [prefix]
        await self._update()

    async def update_jail_channel(self, channel: Optional[TextChannel]) -> None:
        """Updates the guild jail text channel."""
        if channel is None:
            self.jail_channel = None
        else:
            self.jail_channel = channel.id
        await self._update()

    async def update_jail_role(self, role: Optional[Role]) -> None:
        """Updates the guild jail role."""
        if role is None:
            self.jail_role = None
        else:
            self.jail_role = role.id
        await self._update()

    async def update_log_channel(self, channel: Optional[TextChannel]) -> None:
        """Updates the guild log text channel."""
        if channel is None:
            self.log_channel = None
        else:
            self.log_channel = channel.id
        await self._update()

    async def update_suspicious_users(self, suspicious_users: List[str]) -> None:
        """Updates the suspicious user list."""
        self.suspicious_usernames = suspicious_users
        await self._update()

    async def update_appeal_url(self, appeal_url: Optional[str]) -> None:
        """Updates the appeal URL. If None is specified, the appeal URL is removed."""
        self._appeal_url = appeal_url
        await self._update()
