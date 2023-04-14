from __future__ import annotations

import datetime
import logging
import math
import random

from contextlib import suppress
from discord import Forbidden, Member, Message, Role, User, Object
from discord.ext import commands, tasks
from typing import TYPE_CHECKING, Dict, List

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

"""
Extremities to consider

* User levels up
* Level reward gets added
- Level reward gets changed
* Level reward gets removed
* User joins
* User joins while bot is offline
* Role gets deleted
* Role gets deleted while bot is offline

"""

class LevelingHandler(commands.Cog):
    """This class implements a cog for handling the leveling system."""
    
    def __init__(self, client: Pidroid):
        self.client = client
        self.cooldown_storage: Dict[int, Dict[int, UserBucket]] = {}
        self.client.api.add_listener('on_member_level_up', self.on_member_level_up)
        self.client.api.add_listener('on_level_reward_added', self.on_level_reward_added)
        #self.client.api.add_listener('on_level_reward_changed', self.on_level_reward_changed)
        self.client.api.add_listener('on_level_reward_removed', self.on_level_reward_removed)

    def get_bucket(self, guild_id: int, user_id: int) -> UserBucket:
        """Returns the user cooldown bucket."""
        guild = self.cooldown_storage.get(guild_id, None)
        if guild is None:
            self.cooldown_storage[guild_id] = {}
            guild = self.cooldown_storage[guild_id]

        if guild.get(user_id, None) is None:
            self.cooldown_storage[guild_id][user_id] = UserBucket(user_id)
        return guild[user_id]

    @commands.Cog.listener() # type: ignore
    async def on_ready(self) -> None:
        await self.client.wait_until_guild_configurations_loaded()
        for guild in self.client.guilds:
            # Delete level rewards for roles that have been deleted
            rewards = await self.client.api.fetch_all_guild_level_rewards(guild.id)
            guild_role_ids = [r.id for r in guild.roles]
            for reward in rewards:
                if reward.role_id not in guild_role_ids:
                    logger.debug(f'Removing {reward.role_id} as a level reward for {guild}')
                    await reward.delete()

            # Check if guild has enabled leveling system
            config = await self.client.fetch_guild_configuration(guild.id)
            if not config.xp_system_active:
                continue
            
            # Go over each level info and add the roles if they don't have them already
            level_infos = await self.client.api.fetch_guild_level_infos(guild.id)
            # Copied from role adding
            for level_info in level_infos:
                
                # Acquire member object
                member = await level_info.fetch_member()
                if member is None:
                    continue

                # Acquire eligible level rewards if they are available
                level_rewards = await level_info.fetch_eligible_level_rewards()
                if len(level_rewards) == 0:
                    continue
                
                # If to stack rewards, add all of them
                if config.stack_level_rewards:
                    for level_reward in level_rewards:
                        role = await level_reward.fetch_role()
                        if role:
                            with suppress(Forbidden):
                                await member.add_roles(role, reason='Re-add level reward on rejoin as sync') # type: ignore
                
                # If only a single role should be given
                else:
                    # the first item in the list is always the topmost role
                    role = await level_rewards[0].fetch_role()
                    if role:
                        with suppress(Forbidden):
                            await member.add_roles(role, reason='Re-add level reward on rejoin as sync') # type: ignore

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
        """Re-adds leveling rewards to the rejoined member."""
        if member.bot:
            return

        await self.client.wait_until_guild_configurations_loaded()
        config = await self.client.fetch_guild_configuration(member.guild.id)

        if not config.xp_system_active:
            return

        # Obtain user information
        bare_info = await self.client.api.fetch_user_level_info(member.guild.id, member.id)
        if bare_info is None:
            return

        # If rewards should be stacked
        if config.stack_level_rewards:
            for level_reward in await bare_info.fetch_eligible_level_rewards():
                role = await level_reward.fetch_role()
                if role:
                    with suppress(Forbidden):
                        await member.add_roles(role, reason='Re-add level reward on rejoin') # type: ignore
            return
            
        # If only a single role should be given
        reward = await bare_info.fetch_eligible_level_reward()
        if reward is None:
            return
        role = await reward.fetch_role()
        if role:
            with suppress(Forbidden):
                await member.add_roles(role, reason='Re-add level reward on rejoin') # type: ignore

    async def on_member_level_up(self, information: LevelInformation):
        """Called when a member levels up."""
        logger.debug(f'{information.user_id} just leveled up to {information.current_level} level in {information.guild_id} guild!')
        
        # Acquire guild and member objects
        guild = self.client.get_guild(information.guild_id)
        assert guild is not None
        member = await self.client.get_or_fetch_member(guild, information.user_id)
        if member is None:
            return logger.warning(f"Could not resolve member {information.user_id} on member level up in {information.guild_id}")


        rewards = await information.fetch_eligible_level_rewards()
        config = await self.client.fetch_guild_configuration(information.guild_id)

        # Convert every role to a snowflake representation
        member_role_ids = [r.id for r in member.roles]
        role_snowflakes = [Object(id=r.role_id) for r in rewards]
        if len(role_snowflakes) == 0:
            return

        if config.stack_level_rewards:
            for snowflake in role_snowflakes:
                # Ignore roles that the member already
                if snowflake.id in member_role_ids:
                    continue
                with suppress(Forbidden):
                    await member.add_roles(*role_snowflakes, reason='Level up reward granted')
        else:
            for snowflake in role_snowflakes:
                if snowflake.id not in member_role_ids:
                    continue
                with suppress(Forbidden):
                    await member.remove_roles(*role_snowflakes, reason='Level up reward granted')
            with suppress(Forbidden):
                await member.add_roles(role_snowflakes[0], reason='Level up reward granted')

    @commands.Cog.listener() # type: ignore
    async def on_guild_role_delete(self, role: Role) -> None:
        """Handles removal of level reward if the said role is removed."""
        await self.client.wait_until_guild_configurations_loaded()
        reward = await self.client.api.fetch_level_reward_by_role(role.guild.id, role.id)
        if reward:
            await reward.delete()

    async def on_level_reward_added(self, reward: LevelReward):
        """Called when level reward is added."""
        config = await self.client.fetch_guild_configuration(reward.guild_id)

        # If level rewards are stacked
        if config.stack_level_rewards:
            level_infos = await self.client.api.fetch_user_level_info_between(reward.guild_id, reward.level, None)
            for level_info in level_infos:
                member = await level_info.fetch_member()
                if member:
                    with suppress(Forbidden):
                        await member.add_roles(Object(id=reward.role_id), reason='Role reward added')
        
        # If they are not stacked
        else:
            
            # get the affected level informations
            level_infos = []
            next = await reward.fetch_next_reward()
            if next:
                level_infos = await self.client.api.fetch_user_level_info_between(reward.guild_id, reward.level, next.level)
            else:
                level_infos = await self.client.api.fetch_user_level_info_between(reward.guild_id, reward.level, None)

            # go over each level information and change roles
            for level_info in level_infos:
                member = await level_info.fetch_member()
                if member:
                    previous = await reward.fetch_previous_reward()
                    with suppress(Forbidden):
                        await member.add_roles(Object(id=reward.role_id), reason='Role reward added')
                        if previous:
                            await member.remove_roles(Object(id=previous.role_id), reason='Role reward added')

    async def on_level_reward_changed(self, before: LevelReward, after: LevelReward):
        """Called when level reward is changed."""
        # TODO: implement
        logger.debug(f"Level reward changed: {before} -> {after}")

    async def on_level_reward_removed(self, reward: LevelReward):
        """Called when level reward is removed."""
        # Acquire the guild configuration
        config = await reward.fetch_guild_configuration()

        # Fetch the role object
        guild = self.client.get_guild(reward.guild_id)
        assert guild is not None
        role = await self.client.get_or_fetch_role(guild, reward.role_id)
        role_exists = role is not None

        # Fetch a list of potentially affected users' level info due to reward removal
        affected_user_level_infos = await self.client.api.fetch_user_level_info_between(reward.guild_id, reward.level, None)


        # If level rewards are stacked
        if config.stack_level_rewards:
            # If role does not exist, we do not care, it is already removed
            if not role_exists:
                return
            
            # If it does exist, remove it from every potentially affected person
            for level_info in affected_user_level_infos:
                member = await level_info.fetch_member()
                if member:
                    with suppress(Forbidden):
                        await member.remove_roles(role, reason='Role is no longer a level reward')
            return


        # If level rewards are NOT stacked
        # If role does not exist, add the next best role, if possible
        if not role_exists:
            for level_info in affected_user_level_infos:
                member = await level_info.fetch_member()
                if member:
                    # we pick the next best role, if available
                    le = await level_info.fetch_eligible_level_reward()
                    if le:
                        # We add member to the role
                        # TODO: ensure that we do not have to check if it exists
                        with suppress(Forbidden):
                            await member.add_roles(Object(id=le.role_id), reason='Next role due to role change')
            return

        # If role does exist, remove it from all eligible members and try to assign them a new role
        for level_info in affected_user_level_infos:
            member = await level_info.fetch_member()
            if member:
                # we remove the role
                with suppress(Forbidden):
                    await member.remove_roles(role, reason='Role is no longer a level reward')
                # we pick the next best role, if available
                le = await level_info.fetch_eligible_level_reward()
                if le:
                    # We add member to the role
                    # TODO: ensure that we do not have to check if it exists
                    with suppress(Forbidden):
                        await member.add_roles(Object(id=le.role_id), reason='Next role due to role change')


async def setup(client: Pidroid) -> None:
    await client.add_cog(LevelingHandler(client))
