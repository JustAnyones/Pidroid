from __future__ import annotations

import datetime
import logging
import math
import random

from discord import Message, User
from discord.ext import commands
from typing import TYPE_CHECKING, Dict

from pidroid.models.guild_configuration import GuildConfiguration
from pidroid.utils.time import utcnow

logger = logging.getLogger('Pidroid')

if TYPE_CHECKING:
    from pidroid.client import Pidroid

class UserBucket:

    def __init__(self, user_id: int) -> None:
        self.__id = user_id
        self.__last_earned = datetime.datetime.utcfromtimestamp(0)

    @property
    def user_id(self) -> int:
        """Returns the user ID associated with the bucket."""
        return self.__id

    @property
    def can_earn(self) -> bool:
        """Returns true if user can earn XP again."""
        return (utcnow().timestamp() - self.__last_earned.timestamp()) >= 1 # TODO: change

    def cooldown(self) -> None:
        """Sets the bucket on a 60 second cooldown."""
        self.__last_earned = utcnow()

def get_random_xp_amount(config: GuildConfiguration) -> int:
    """Returns a random amount of XP as derived from the config."""
    xp_amount = random.randint(config.xp_per_message_min, config.xp_per_message_max)
    return math.floor(xp_amount * config.xp_multiplier)

class LevelingHandler(commands.Cog):
    """This class implements a cog for handling the leveling system."""
    def __init__(self, client: Pidroid):
        self.client = client
        self.cooldown_storage: Dict[int, Dict[int, UserBucket]] = {}

    def get_bucket(self, guild_id: int, user_id: int) -> UserBucket:
        guild = self.cooldown_storage.get(guild_id, None)
        if guild is None:
            self.cooldown_storage[guild_id] = {}
            guild = self.cooldown_storage[guild_id]

        if guild.get(user_id, None) is None:
            self.cooldown_storage[guild_id][user_id] = UserBucket(user_id)
        return guild[user_id]

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        await self.client.wait_until_guild_configurations_loaded()

        if not message.guild or message.author.bot:
            return

        if isinstance(message.author, User):
            return

        # Might want to cache this
        config = await self.client.fetch_guild_configuration(message.guild.id)
        if not config.xp_system_active:
            return

        # Ignore if called in an XP exempt channel
        if message.channel.id in config.xp_exempt_channels:
            return

        # if sets intersect, i.e, have a XP exempt role
        if not set([r.id for r in message.author.roles]).isdisjoint(config.xp_exempt_roles):
            return

        bucket = self.get_bucket(message.guild.id, message.author.id)
        if not bucket.can_earn:
            return

        # Immediately put it on cooldown
        bucket.cooldown()

        xp = get_random_xp_amount(config)

        # Save it by a call to the database
        await self.client.api.increment_member_xp(message.guild.id, message.author.id, xp)

async def setup(client: Pidroid) -> None:
    await client.add_cog(LevelingHandler(client))
