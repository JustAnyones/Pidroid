from __future__ import annotations

import datetime
import logging
import math
import random

from contextlib import suppress
from discord import Forbidden, Member, Message, User, Object
from discord.ext import commands, tasks
from typing import TYPE_CHECKING, Dict

from pidroid.models.guild_configuration import GuildConfiguration
from pidroid.utils.levels import LevelInformation, LevelReward
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
        return (utcnow().timestamp() - self.__last_earned.timestamp()) >= 60

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
        self.client.api.add_listener('on_member_level_up', self.on_member_level_up)
        #self.client.api.add_listener('on_level_reward_added', self.on_level_reward_added)
        #self.client.api.add_listener('on_level_reward_changed', self.on_level_reward_changed)
        #self.client.api.add_listener('on_level_reward_removed', self.on_level_reward_removed)
        self.renew_role_reward_state.start()

    def cog_unload(self):
        """Ensure that tasks are cancelled on cog unload."""
        self.renew_role_reward_state.stop()

    @tasks.loop(seconds=5)
    async def renew_role_reward_state(self) -> None:
        """Periodically checks for expired punishments to remove."""
        try:
            for guild in self.client.guilds:
                config = await self.client.fetch_guild_configuration(guild.id)
                pass

        except Exception:
            self.client.logger.exception("An exception was encountered while trying to renew role reward state")

    @renew_role_reward_state.before_loop
    async def before_renew_role_reward_state(self) -> None:
        """Runs before renew_role_reward_state task to ensure that the task is allowed to run."""
        await self.client.wait_until_guild_configurations_loaded()

    def get_bucket(self, guild_id: int, user_id: int) -> UserBucket:
        """Returns the user cooldown bucket."""
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

    @commands.Cog.listener() # type: ignore
    async def on_member_join(self, member: Member) -> None:
        """Adds back leveling roles to the member."""
        if member.bot:
            return

        await self.client.wait_until_guild_configurations_loaded()
        config = await self.client.fetch_guild_configuration(member.guild.id)

        if not config.xp_system_active:
            return

        info = await self.client.api.fetch_bare_member_level_info(member.guild.id, member.id)
        if info is None:
            return

        rewards = await self.client.api.fetch_guild_level_rewards(member.guild.id, info.current_level)
        for reward in rewards:
            role = await self.client.get_or_fetch_role(member.guild, reward.role_id)
            if role:
                with suppress(Forbidden):
                    await member.add_roles(role, reason="Added a role level reward")
            if config.stack_level_rewards:
                break

    async def on_member_level_up(self, information: LevelInformation):
        """Called when a member levels up."""
        print(information.user_id, "just leveled up to", information.current_level, f"level in {information.guild_id}!")
        
        # Acquire guild and member objects
        guild = self.client.get_guild(information.guild_id)
        assert guild is not None
        member = await self.client.get_or_fetch_member(guild, information.user_id)
        if member is None:
            return logger.warning(f"Could not resolve member {information.user_id} on member level up in {information.guild_id}")


        rewards = await self.client.api.fetch_guild_level_rewards(information.guild_id, information.current_level)
        config = await self.client.fetch_guild_configuration(information.guild_id)

        # Convert every role to a snowflake representation
        role_snowflakes = [Object(id=r.role_id) for r in rewards]
        if len(role_snowflakes) == 0:
            return

        if config.stack_level_rewards:
            await member.add_roles(*role_snowflakes, reason="Member leveled up")
        else:
            await member.remove_roles(*role_snowflakes, reason="Member leveled up")
            await member.add_roles(role_snowflakes[0], reason="Member leveled up")

    async def on_level_reward_added(self, reward: LevelReward):
        """Called when level reward is added."""
        config = await self.client.fetch_guild_configuration(reward.guild_id)

        if config.stack_level_rewards:
            pass
        else:
            pass


        print("Level reward added:", reward)

    async def on_level_reward_changed(self, before: LevelReward, after: LevelReward):
        """Called when level reward is changed."""
        print("Level reward changed:", before, "->", after)

    async def on_level_reward_removed(self, reward: LevelReward):
        """Called when level reward is removed."""
        guild = self.client.get_guild(reward.guild_id)
        assert guild is not None

        role = await self.client.get_or_fetch_role(guild, reward.role_id)
        # then the role itself was delete and we don't care
        if role is None:
            return
        
        for member in role.members:
            await member.remove_roles(role, reason="Role was removed as reward")

async def setup(client: Pidroid) -> None:
    await client.add_cog(LevelingHandler(client))
