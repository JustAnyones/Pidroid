from __future__ import annotations

import datetime
import logging
import math
import random

from discord import Member, Message, Role, User, Object
from discord.abc import Snowflake
from discord.ext import commands, tasks
from typing import TYPE_CHECKING, Dict, List

from pidroid.models.guild_configuration import GuildConfiguration
from pidroid.models.role_changes import RoleAction
from pidroid.utils.levels import MemberLevelInfo, LevelReward
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
        """Sets the bucket on a cooldown."""
        self.__last_earned = utcnow()

def get_random_xp_amount(config: GuildConfiguration) -> int:
    """Returns a random amount of XP as derived from the config."""
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

class LevelingHandler(commands.Cog):
    """This class implements a cog for handling the leveling system related functionality."""
    
    def __init__(self, client: Pidroid):
        self.client = client
        self.__cooldown_storage: Dict[int, Dict[int, UserBucket]] = {}
        self.process_role_queue.start()
        self.sync_role_rewards.start()

    def cog_unload(self):
        """Ensure that all the tasks are stopped and cancelled on cog unload."""
        self.process_role_queue.cancel()
        self.sync_role_rewards.cancel()

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
        await self.client.api.insert_role_change(RoleAction.add, member.guild.id, member.id, role_id)
    
    async def queue_remove(self, member: Member, role_id: int, reason: str):
        # If member doesn't have the role, don't bother
        if not any(r.id == role_id for r in member.roles):
            return
        logger.debug(f"Adding role ({role_id}) removal to queue for {member} in {member.guild}: {reason}")
        await self.client.api.insert_role_change(RoleAction.remove, member.guild.id, member.id, role_id)

    @tasks.loop(seconds=60)
    async def process_role_queue(self) -> None:
        """This task runs periodically to apply role changes to members from a queue."""
        logger.debug("Processing role queue")
        for guild in self.client.guilds:
            # Acquire guild information
            conf = await self.client.fetch_guild_configuration(guild.id)
            if not conf.xp_system_active:
                continue
            
            role_changes = await self.client.api.fetch_role_changes(guild.id)
            logger.debug(f"Managing role changes for {guild}")
            for role_change in role_changes:
                member = guild.get_member(role_change.member_id)
                # If we have the member object
                if member:
                    logger.debug(f"Managing role changes for {member} in {guild}")
                    updated_roles: List[Snowflake] = []

                    # Manage mostly removed roles
                    for role in member.roles:
                        # If the current role in loop is due for removal
                        # Do not add it to the list and continue the loop
                        if any(role.id == removed_role_id for removed_role_id in role_change.roles_removed):
                            continue
                        updated_roles.append(role)

                    # Manage added roles
                    for role_id in role_change.roles_added:
                        # If the current loop role is already in the member roles, ignore
                        if any(role_id == r.id for r in updated_roles):
                            continue
                        updated_roles.append(Object(id=role_id))
                    await member.edit(roles=updated_roles, reason="Pidroid level reward update")

                    await role_change.pop()

    @process_role_queue.before_loop
    async def before_process_role_queue(self) -> None:
        """Runs before process_role_queue task to ensure that the task is ready to run."""
        await self.client.wait_until_guild_configurations_loaded()

    @tasks.loop(seconds=120)
    async def sync_role_rewards(self) -> None:
        """
        This task runs periodically to ensure correct member reward state across all guilds.

        This can handle the following scenarios:
            - new level rewards getting added;
            - user joins or role gets deleted while bot is offline;
            - sync if someone messes with roles manually.
        
        WARNING, THIS DOES NOT HANDLE ROLE REWARDS THAT WERE REMOVED AS PIDROID
        CAN NO LONGER INDENTIFY THEM."""
        for guild in self.client.guilds:
            # Acquire guild information
            conf = await self.client.fetch_guild_configuration(guild.id)

            all_level_rewards = await conf.fetch_all_level_rewards()

            # Remove rewards for roles that no longer exist
            guild_role_ids = [role.id for role in guild.roles]
            for reward in all_level_rewards:
                if reward.role_id not in guild_role_ids:
                    logger.debug(f'Removing {reward.role_id} as a level reward for {guild} since role no longer exists')
                    await reward.delete()

            # If leveling system is not active, we do not need to update member role states
            # for rewards
            if not conf.xp_system_active:
                continue

            # Update every eligible user
            for member_information in await conf.fetch_all_member_levels():
                # Obtain member object, if we can't do that
                # then move onto the next member
                member = await member_information.fetch_member()
                if member is None:
                    continue
                
                # Acquire all rewards that the user is eligible for
                rewards = await member_information.fetch_eligible_level_rewards()

                # If member has no eligible rewards, move onto the next member
                if len(rewards) == 0:
                    continue
                
                # If to stack rewards, add all of them
                if conf.level_rewards_stacked:
                    for reward in rewards:
                        await self.queue_add(member, reward.role_id, "Periodic role reward state sync")
                
                # If only a single role should be given
                else:
                    # the first item in the list is always the topmost role
                    await self.queue_add(member, rewards[0].role_id, "Periodic role reward state sync")
                    # remove all other roles
                    amount_to_remove = len(rewards) - 1
                    if amount_to_remove > 0:
                        for reward in rewards[1:]:
                            await self.queue_remove(member, reward.role_id, "Periodic role reward state sync")

    @sync_role_rewards.before_loop
    async def before_sync_role_rewards(self) -> None:
        """Runs before sync_role_rewards task to ensure that the task is ready to run."""
        await self.client.wait_until_guild_configurations_loaded()

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

        # Save it by a call to the database
        # Award the XP to the specified message
        await self.client.api.award_xp(message, get_random_xp_amount(config))

    @commands.Cog.listener() # type: ignore
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
            level_rewards = await member_level.fetch_eligible_level_rewards()
            for reward in level_rewards:
                await self.queue_add(member, reward.role_id, "Re-add stacked level reward on rejoin")
            return

        # If only a single role reward should be given
        reward = await member_level.fetch_eligible_level_reward()
        if reward is not None:
            await self.queue_add(member, reward.role_id, "Re-add single level reward on rejoin")

    @commands.Cog.listener()
    async def on_pidroid_level_up(self, member: Member, message: Message, information: MemberLevelInfo):
        """Called when a member levels up."""
        logger.debug(f'{member} just leveled up to {information.current_level} level in {information.guild_id} guild!')

        rewards = await information.fetch_eligible_level_rewards()
        config = await self.client.fetch_guild_configuration(information.guild_id)

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
            await reward.delete()

    @commands.Cog.listener()
    async def on_pidroid_level_reward_remove(self, reward: LevelReward):
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
        if config.level_rewards_stacked:
            # If role does not exist, we do not care, it is already removed
            if not role_exists:
                return
            
            # If it does exist, remove it from every potentially affected person
            for level_info in affected_user_level_infos:
                member = await level_info.fetch_member()
                if member:
                    await self.queue_remove(member, role.id, "Role is no longer a level reward")
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
                        await self.queue_add(member, le.role_id, "Next role due to role reward removal")
            return

        # If role does exist, remove it from all eligible members and try to assign them a new role
        for level_info in affected_user_level_infos:
            member = await level_info.fetch_member()
            if member:
                # we remove the role
                await self.queue_remove(member, role.id, "Role is no longer a level reward")
                # we pick the next best role, if available
                le = await level_info.fetch_eligible_level_reward()
                if le:
                    # We add member to the role
                    await self.queue_add(member, le.role_id, "Next role due to role reward removal")


async def setup(client: Pidroid) -> None:
    await client.add_cog(LevelingHandler(client))
