from __future__ import annotations

from bson.int64 import Int64 # type: ignore
from bson.objectid import ObjectId # type: ignore
from discord.channel import TextChannel
from discord.role import Role
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from cogs.utils.api import API

class GuildConfiguration:

    if TYPE_CHECKING:
        _id: ObjectId
        guild_id: int

        prefixes: List[str]

        jail_channel: Optional[int]
        jail_role: Optional[int]
        mute_role: Optional[int]
        log_channel: Optional[int]

        suggestion_channel: Optional[int]
        use_suggestion_threads: bool

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

        self.jail_channel = c.get("jail_channel", None)
        self.jail_role = c.get("jail_role", None)
        self.mute_role = c.get("mute_role", None)
        self.log_channel = c.get("log_channel", None)

        self.suggestion_channel = c.get("suggestion_channel", None)
        self.use_suggestion_threads = c.get("use_suggestion_threads", False)

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

    async def update_jail_channel(self, channel: Optional[TextChannel]) -> None:
        """Updates the guild jail text channel."""
        if channel is None:
            self.jail_channel = None
            return await self.api.unset_guild_config(self._id, "jail_channel")
        self.jail_channel = channel.id
        await self.api.set_guild_config(self._id, "jail_channel", Int64(channel.id))

    async def update_jail_role(self, role: Optional[Role]) -> None:
        """Updates the guild jail role."""
        if role is None:
            self.jail_role = None
            return await self.api.unset_guild_config(self._id, "jail_role")
        self.jail_role = role.id
        await self.api.set_guild_config(self._id, "jail_role", Int64(role.id))

    async def update_mute_role(self, role: Optional[Role]) -> None:
        """Updates the guild mute role."""
        if role is None:
            self.mute_role = None
            return await self.api.unset_guild_config(self._id, "mute_role")
        self.mute_role = role.id
        await self.api.set_guild_config(self._id, "mute_role", Int64(role.id))

    async def update_log_channel(self, channel: Optional[TextChannel]) -> None:
        """Updates the guild log text channel."""
        if channel is None:
            self.log_channel = None
            return await self.api.unset_guild_config(self._id, "log_channel")
        self.log_channel = channel.id
        await self.api.set_guild_config(self._id, "log_channel", Int64(channel.id))

    async def update_suggestion_channel(self, channel: Optional[TextChannel]) -> None:
        """Updates the guild suggestion text channel."""
        if channel is None:
            self.suggestion_channel = None
            return await self.api.unset_guild_config(self._id, "suggestion_channel")
        self.suggestion_channel = channel.id
        await self.api.set_guild_config(self._id, "suggestion_channel", Int64(channel.id))

    async def update_suggestion_threads(self, use_threads: bool):
        """Updates use of suggestion threads."""
        self.use_suggestion_threads = use_threads
        await self.api.set_guild_config(self._id, "use_suggestion_threads", use_threads)

    async def update_suspicious_users(self, suspicious_users: List[str]) -> None:
        """Updates the suspicious user list."""
        self.suspicious_users = suspicious_users
        await self.api.set_guild_config(self._id, "suspicious_users", suspicious_users)

    async def update_banned_exact_words(self, banned_words: List[str]) -> None:
        """Updates the exact banned words list."""
        self.banned_exact_words = banned_words
        await self.api.set_guild_config(self._id, "banned_exact_words", banned_words)
