from __future__ import annotations

import asyncio
import datetime
import logging
import math
import random

from discord import Guild, Member, Message, MessageType, Role, User
from discord.ext import commands
from typing import TYPE_CHECKING

from pidroid.models.guild_configuration import GuildConfiguration
from pidroid.utils.db.levels import LevelRewards, UserLevels
from pidroid.utils.debouncer import RoleChangeDebouncer, RoleAction
from pidroid.utils.time import utcnow

logger = logging.getLogger('pidroid.leveling')

if TYPE_CHECKING:
    from pidroid.client import Pidroid

class UserBucket:

    def __init__(self, user_id: int) -> None:
        super().__init__()
        self.__id = user_id
        self.__last_earned = datetime.datetime.fromtimestamp(0, tz=datetime.UTC)

    @property
    def user_id(self) -> int:
        """Returns the user ID associated with the bucket."""
        return self.__id

    @property
    def can_earn(self) -> bool:
        """Returns true if user can earn XP again."""
        return (utcnow().timestamp() - self.__last_earned.timestamp()) >= 60

    def cooldown(self) -> None:
        """Sets the bucket on a cooldown."""
        self.__last_earned = utcnow()

def get_random_xp_amount(config: GuildConfiguration) -> int:
    """Returns a random amount of XP as derived from the config."""
    if config.xp_multiplier == 0:
        return 0
    xp_amount = random.randint(config.xp_per_message_min, config.xp_per_message_max)
    return math.floor(xp_amount * config.xp_multiplier)

"""
Guaranteed to work when:

- User rejoined
- User leveled up

- Role is deleted
- Role reward is removed


Should work when:
- User rejoins while bot is offline
- Role gets deleted while bot is offline
- Reward gets added
"""

class LevelingService(commands.Cog):
    """This class implements a cog for handling the leveling system related functionality."""
    
    def __init__(self, client: Pidroid):
        super().__init__()
        self.client = client
        self.__cooldown_storage: dict[int, dict[int, UserBucket]] = {}
        self.__startup_sync_finished = asyncio.Event()
        self.__role_debouncer = RoleChangeDebouncer(client, 20)

    def get_bucket(self, guild_id: int, user_id: int) -> UserBucket:
        """Returns the user cooldown bucket."""
        guild = self.__cooldown_storage.get(guild_id, None)
        if guild is None:
            self.__cooldown_storage[guild_id] = {}
            guild = self.__cooldown_storage[guild_id]

        if guild.get(user_id, None) is None:
            self.__cooldown_storage[guild_id][user_id] = UserBucket(user_id)
        return guild[user_id]
    
    async def queue_add(self, member: Member, role_id: int, reason: str):
        # If member already has the role, don't queue it up
        if any(r.id == role_id for r in member.roles):
            return
        logger.debug(f"Adding role ({role_id}) add to queue for {member} in {member.guild}: {reason}")
        await self.__role_debouncer.update_user_role(
            RoleAction.add, member.guild.id, member.id, role_id
        )
    
    async def queue_remove(self, member: Member, role_id: int, reason: str, bypass_cache: bool = False):
        # If member doesn't have the role, don't bother
        if not bypass_cache and not any(r.id == role_id for r in member.roles):
            return
        logger.debug(f"Adding role ({role_id}) removal to queue for {member} in {member.guild}: {reason}")
        await self.__role_debouncer.update_user_role(
            RoleAction.remove, member.guild.id, member.id, role_id
        )

    async def _sync_guild_state(self, guild: Guild, reason: str) -> None:
        """An expensive method that syncs guild level reward state."""
        logger.debug(f"Syncing {guild} level rewards")
        # Acquire guild information
        conf = await self.client.fetch_guild_configuration(guild.id)

        all_level_rewards = await conf.fetch_all_level_rewards()

        # Remove rewards for roles that no longer exist
        guild_role_ids = [role.id for role in guild.roles]
        for reward in all_level_rewards:
            if reward.role_id not in guild_role_ids:
                logger.debug(f'Removing {reward.role_id} as a level reward for {guild} since role no longer exists')
                await self.client.api.delete_level_reward(reward.id)

        # If leveling system is not active, we do not need to update member role states
        # for rewards
        if not conf.xp_system_active:
            return

        # Update every eligible user
        logger.debug(f"Syncing {guild} member levels")
        for member_information in await conf.fetch_all_member_levels():
            # Obtain member object, if we can't do that
            # then move onto the next member

            if self.client.debugging:
                logger.debug(f"Fetching member information for {member_information.user_id}")

            member = guild.get_member(member_information.user_id)
            if member is None:
                continue
                
            # Acquire all rewards that the user is eligible for
            rewards = await self.client.api.fetch_eligible_level_rewards_for_level(
                member_information.guild_id, member_information.level
            )

            # If member has no eligible rewards, move onto the next member
            if len(rewards) == 0:
                continue
                
            # If to stack rewards, add all of them
            if conf.level_rewards_stacked:
                for reward in rewards:
                    await self.queue_add(member, reward.role_id, reason)
                
            # If only a single role should be given
            else:
                # the first item in the list is always the topmost role
                await self.queue_add(member, rewards[0].role_id, reason)
                # remove all other roles
                amount_to_remove = len(rewards) - 1
                if amount_to_remove > 0:
                    for reward in rewards[1:]:
                        await self.queue_remove(member, reward.role_id, reason, bypass_cache=False)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """
        This task runs on start-up to ensure correct member reward state across all guilds.

        This can handle the following scenarios:
            - new level rewards getting added;
            - user joins or role gets deleted while bot is offline;
        """
        await self.client.wait_until_guild_configurations_loaded()
        logger.info("Syncing level reward state")
        for guild in self.client.guilds:
            await self._sync_guild_state(guild, "Start-up role reward state sync")
        logger.info("Level reward state synced")
        self.__startup_sync_finished.set()

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        await self.client.wait_until_guild_configurations_loaded()

        if not message.guild or message.author.bot:
            return
        
        # Auto moderation action messages have authors set as the people
        # who are responsible for the infraction
        if message.type == MessageType.auto_moderation_action:
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

        # Save it by a call to the database
        # Award the XP to the specified message
        await self.client.api.award_xp(message, get_random_xp_amount(config))

    @commands.Cog.listener()
    async def on_member_join(self, member: Member) -> None:
        """Re-adds leveling rewards to the rejoined member."""
        if member.bot:
            return

        await self.client.wait_until_guild_configurations_loaded()

        conf = await self.client.fetch_guild_configuration(member.guild.id)

        # If XP system is not active, don't give the rewards
        if not conf.xp_system_active:
            return

        # Obtain member level information, if it doesn't exist - stop
        member_level = await conf.fetch_member_level(member.id)
        if member_level is None:
            return

        # If rewards should be stacked
        if conf.level_rewards_stacked:
            level_rewards = await self.client.api.fetch_eligible_level_rewards_for_level(
                member_level.guild_id, member_level.level
            )
            for reward in level_rewards:
                await self.queue_add(member, reward.role_id, "Re-add stacked level reward on rejoin")
            return

        # If only a single role reward should be given
        level_reward = await self.client.api.fetch_eligible_level_reward_for_level(
            member_level.guild_id, member_level.level
        )
        if level_reward is not None:
            await self.queue_add(member, level_reward.role_id, "Re-add single level reward on rejoin")

    @commands.Cog.listener()
    async def on_pidroid_level_up(self, member: Member, message: Message, info_before: UserLevels, info_after: UserLevels):
        """Called when a member levels up."""
        assert message.guild
        logger.debug(
            f'{member} just leveled up to {info_after.level} level in {message.guild} ({message.guild.id}) guild!'
        )

        rewards = await self.client.api.fetch_eligible_level_rewards_for_level(
            info_after.guild_id, info_after.level
        )
        config = await self.client.fetch_guild_configuration(info_after.guild_id)

        if len(rewards) == 0:
            return

        if config.level_rewards_stacked:
            # Add all roles
            for reward in rewards:
                await self.queue_add(member, reward.role_id, "Level up stacked reward granted")
        else:
            # Remove all roles except the first one in the list
            for reward in rewards[1:]:
                await self.queue_remove(member, reward.role_id, "Level up reward granted")
            # Add the first role
            await self.queue_add(member, rewards[0].role_id, "Level up reward granted")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: Role) -> None:
        """Handles removal of level reward if the said role is removed."""
        await self.client.wait_until_guild_configurations_loaded()
        reward = await self.client.api.fetch_level_reward_by_role(role.guild.id, role.id)
        if reward:
            await self.client.api.delete_level_reward(reward.id)

    @commands.Cog.listener()
    async def on_pidroid_level_reward_add(self, reward: LevelRewards):
        """Called when level reward is added."""
        config = await self.client.fetch_guild_configuration(reward.guild_id)

        # Fetch the role object
        guild = self.client.get_guild(reward.guild_id)
        assert guild is not None

        # If level rewards are stacked
        if config.level_rewards_stacked:
            level_infos = await self.client.api.fetch_user_level_info_between(reward.guild_id, reward.level, None)
            for level_info in level_infos:
                member = await self.client.get_or_fetch_member(guild, level_info.user_id)
                if member:
                    await self.queue_add(member, reward.role_id, "Role reward created")

        # If they are not stacked
        else:
            # get the affected level informations
            level_infos = []
            next = await self.client.api.fetch_next_level_reward(reward.guild_id, reward.level)
            if next:
                level_infos = await self.client.api.fetch_user_level_info_between(reward.guild_id, reward.level, next.level)
            else:
                level_infos = await self.client.api.fetch_user_level_info_between(reward.guild_id, reward.level, None)

            # go over each level information and change roles
            for level_info in level_infos:
                member = await self.client.get_or_fetch_member(guild, level_info.user_id)
                if member:
                    previous = await self.client.api.fetch_previous_level_reward(reward.guild_id, reward.level)
                    await self.queue_add(member, reward.role_id, "Role reward created")
                    if previous:
                        await self.queue_remove(member, previous.role_id, "Role reward created")

    @commands.Cog.listener()
    async def on_pidroid_level_reward_remove(self, reward: LevelRewards):
        """Called when level reward is removed."""
        # Acquire the guild configuration
        config = await self.client.fetch_guild_configuration(reward.guild_id)

        # Fetch the role object
        guild = self.client.get_guild(reward.guild_id)
        assert guild is not None
        role = guild.get_role(reward.role_id)
        role_exists = role is not None

        # Fetch a list of potentially affected users' level info due to reward removal
        affected_user_level_infos = await self.client.api.fetch_user_level_info_between(reward.guild_id, reward.level, None)

        

        # If level rewards are stacked
        if config.level_rewards_stacked:
            # If role does not exist, we do not care, it is already removed
            if not role_exists:
                return
            
            # If it does exist, remove it from every potentially affected person
            assert role
            for level_info in affected_user_level_infos:
                member = await self.client.get_or_fetch_member(guild, level_info.user_id)
                if member:
                    await self.queue_remove(member, role.id, "Role is no longer a level reward")
            return


        # If level rewards are NOT stacked
        # If role does not exist, add the next best role, if possible
        if not role_exists:
            for level_info in affected_user_level_infos:
                member = await self.client.get_or_fetch_member(guild, level_info.user_id)
                if member:
                    # we pick the next best role, if available
                    le = await self.client.api.fetch_eligible_level_reward_for_level(
                        level_info.guild_id, level_info.level
                    )
                    if le:
                        # We add member to the role
                        await self.queue_add(member, le.role_id, "Next role due to role reward removal")
            return

        # If role does exist, remove it from all eligible members and try to assign them a new role
        assert role
        for level_info in affected_user_level_infos:
            member = await self.client.get_or_fetch_member(guild, level_info.user_id)
            if member:
                # we remove the role
                await self.queue_remove(member, role.id, "Role is no longer a level reward")
                # we pick the next best role, if available


                le = await self.client.api.fetch_eligible_level_reward_for_level(
                    level_info.guild_id, level_info.level
                )
                if le:
                    # We add member to the role
                    await self.queue_add(member, le.role_id, "Next role due to role reward removal")

    async def on_pidroid_level_stacking_change(self, guild: Guild):
        """Called when there's a level stacking setting changed."""
        logger.debug(f"Level stacking setting was changed for {guild}")
        await self._sync_guild_state(guild, "Level stacking setting change")


async def setup(client: Pidroid) -> None:
    await client.add_cog(LevelingService(client))
