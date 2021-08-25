from __future__ import annotations

from bson.int64 import Int64
from bson.objectid import ObjectId
from discord.channel import TextChannel
from discord.role import Role
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from client import Pidroid
    from cogs.utils.api import API


class ConfigKeys(Enum):
    jail_role = "jail_role"
    jail_channel = "jail_channel"

    mute_role = "mute_role"


class GuildConfiguration:

    if TYPE_CHECKING:
        _id: ObjectId
        guild_id: int

        jail_channel: int
        jail_role: int

        mute_role: int

    def __init__(self, api: API, data: dict) -> None:
        self.api = api
        self._serialize(data)

    def _serialize(self, c: dict) -> None:
        """Creates GuildConfiguration object from a dictionary."""
        self._id = c["_id"]
        self.guild_id = c["guild_id"]

        self.prefixes = c.get("prefixes", [])

        self.jail_channel = c.get(ConfigKeys.jail_channel.value, None)
        self.jail_role = c.get(ConfigKeys.jail_role.value, None)

        self.mute_role = c.get(ConfigKeys.mute_role.value, None)

    async def update_prefix(self, prefix: str) -> None:
        """Updates the guild bot prefix."""
        self.prefixes = [prefix]
        await self.api.set_guild_config(self._id, "prefixes", self.prefixes)

    async def update_jail_channel(self, channel: TextChannel) -> None:
        """Updates the guild jail text channel."""
        self.jail_channel = channel.id
        key = ConfigKeys.jail_channel.value
        if channel is None:
            return await self.api.unset_guild_config(self._id, key)
        await self.api.set_guild_config(self._id, key, Int64(channel.id))

    async def update_jail_role(self, role: Role) -> None:
        """Updates the guild jail role."""
        self.jail_role = role.id
        key = ConfigKeys.jail_role.value
        if role is None:
            return await self.api.unset_guild_config(self._id, key)
        await self.api.set_guild_config(self._id, key, Int64(role.id))

    async def update_mute_role(self, role: Role) -> None:
        """Updates the guild mute role."""
        self.mute_role = role.id
        key = ConfigKeys.mute_role.value
        if role is None:
            return await self.api.unset_guild_config(self._id, key)
        await self.api.set_guild_config(self._id, key, Int64(role.id))


def setup(client: Pidroid):
    pass

def teardown(client: Pidroid):
    pass
