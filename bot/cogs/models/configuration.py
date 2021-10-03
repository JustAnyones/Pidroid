from __future__ import annotations

from bson.int64 import Int64
from bson.objectid import ObjectId
from discord.channel import TextChannel
from discord.role import Role
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from client import Pidroid
    from cogs.utils.api import API


class GuildConfiguration:

    if TYPE_CHECKING:
        _id: ObjectId
        guild_id: int
        jail_channel: int
        jail_role: int
        mute_role: int
        log_channel: int

        strict_anti_phising: bool
        public_tags: bool

        suspicious_users: List[str]
        banned_exact_words: List[str]

    def __init__(self, api: API, data: dict) -> None:
        self.api = api
        self._serialize(data)

    def _serialize(self, c: dict) -> None:
        """Creates GuildConfiguration object from a dictionary."""
        self._id = c["_id"]
        self.guild_id = c["guild_id"]

        self.prefixes = c.get("prefixes", [])

        self.jail_channel = c.get("jail_role", None)
        self.jail_role = c.get("jail_role", None)
        self.mute_role = c.get("mute_role", None)
        self.log_channel = c.get("log_channel", None)

        self.public_tags = c.get("public_tags", False)
        self.strict_anti_phising = c.get("strict_anti_phising", False)

        self.suspicious_users = c.get("suspicious_users", [])
        self.banned_exact_words = c.get("banned_exact_words", [])

    async def update_public_tag_permission(self, allow_public: bool) -> None:
        """Updates public tag permission."""
        self.public_tags = allow_public
        await self.api.set_guild_config(self._id, "public_tags", allow_public)

    async def update_anti_phising_permission(self, strict: bool) -> None:
        """Updates strict anti-phising permission."""
        self.strict_anti_phising = strict
        await self.api.set_guild_config(self._id, "strict_anti_phising", strict)

    async def update_prefix(self, prefix: str) -> None:
        """Updates the guild bot prefix."""
        self.prefixes = [prefix]
        await self.api.set_guild_config(self._id, "prefixes", self.prefixes)

    async def update_jail_channel(self, channel: TextChannel) -> None:
        """Updates the guild jail text channel."""
        self.jail_channel = channel.id
        if channel is None:
            return await self.api.unset_guild_config(self._id, "jail_channel")
        await self.api.set_guild_config(self._id, "jail_channel", Int64(channel.id))

    async def update_jail_role(self, role: Role) -> None:
        """Updates the guild jail role."""
        self.jail_role = role.id
        if role is None:
            return await self.api.unset_guild_config(self._id, "jail_role")
        await self.api.set_guild_config(self._id, "jail_role", Int64(role.id))

    async def update_mute_role(self, role: Role) -> None:
        """Updates the guild mute role."""
        self.mute_role = role.id
        if role is None:
            return await self.api.unset_guild_config(self._id, "mute_role")
        await self.api.set_guild_config(self._id, "mute_role", Int64(role.id))

    async def update_log_channel(self, channel: TextChannel) -> None:
        """Updates the guild log text channel."""
        self.log_channel = channel.id
        if channel is None:
            return await self.api.unset_guild_config(self._id, "log_channel")
        await self.api.set_guild_config(self._id, "log_channel", Int64(channel.id))

    async def update_suspicious_users(self, suspicious_users: List[str]) -> None:
        """Updates the suspicious user list."""
        self.suspicious_users = suspicious_users
        await self.api.set_guild_config(self._id, "suspicious_users", suspicious_users)

    async def update_banned_exact_words(self, banned_words: List[str]) -> None:
        """Updates the exact banned words list."""
        self.banned_exact_words = banned_words
        await self.api.set_guild_config(self._id, "banned_exact_words", banned_words)


def setup(client: Pidroid):
    pass

def teardown(client: Pidroid):
    pass
