import asyncio
import datetime
import discord

from contextlib import suppress
from discord.member import Member
from discord.user import User
from discord.guild import Guild
from discord import RawMemberRemoveEvent
from discord import File, AuditLogAction, AuditLogEntry
from discord.message import Message
from discord.ext import commands # type: ignore
from random import randint
from typing import Optional, Union

from pidroid.client import Pidroid
from pidroid.cogs.utils.time import utcnow

class NoIdea(commands.Cog): # type: ignore
    """This class implements a cog for handling invocation of copypastas and other memes invoked by events like on_message."""

    def __init__(self, client: Pidroid):
        self.client = client
        
    async def _get_or_fetch_guild(self, guild_id: int) -> Optional[Guild]:
        guild = self.client.get_guild(guild_id)
        if guild is None:
            with suppress(discord.HTTPException):
                return await self.client.fetch_guild(guild_id, with_counts=False)
        return guild
        
    async def find_recent_audit_log(
        self,
        guild_id: int, member_id: int,
        action: AuditLogAction,
        time_called: datetime.datetime
    ) -> Optional[AuditLogEntry]:
        guild = await self._get_or_fetch_guild(guild_id)
        if guild is None:
            return None

        print(f"Searching 100 audit logs for action: {action}")
        search_time = time_called - datetime.timedelta(seconds=15) # I don't like this
        async for entry in guild.audit_logs(action=action, after=search_time):
            # Ignore logs whose target is not who we're searching for
            if entry.target.id != member_id:
                continue
            
            if entry.user.id == self.client.user.id:
                continue
            
            print(time_called, entry.created_at)
            return entry
        return None
        
    #jail
    #unjail
    #timeout
    @commands.Cog.listener()
    async def on_member_update(self, before: Member, after: Member):
        now = utcnow()
        await self.client.wait_guild_config_cache_ready()
        
        # Detect timeout
        if not before.is_timed_out() and after.is_timed_out():
            log = await self.find_recent_audit_log(after.guild.id, after.id, AuditLogAction.member_update, now)
            print(after, "was timed out by", log.user, "for the following reason:", log.reason)
        
        # Detect whether roles got changed
        # TODO: fix
        changed_roles = list(set(before.roles) - set(after.roles)) or None
        if changed_roles is None:
            return
        
        print("Roles have changed:", before.roles, "->", after.roles)
    
    # Detect who kicked the member if they were kicked
    @commands.Cog.listener()
    async def on_raw_member_remove(self, payload: RawMemberRemoveEvent):
        now = utcnow()
        await self.client.wait_guild_config_cache_ready()
        audit_log = await self.find_recent_audit_log(payload.guild_id, payload.user.id, AuditLogAction.kick, now)
        if audit_log is None:
            return
        
        print(payload.user, "was kicked by", audit_log.user, "for the following reason:", audit_log.reason)
    
    # ban
    @commands.Cog.listener()
    async def on_member_ban(self, guild: Guild, user: Union[Member, User]):
        now = utcnow()
        await self.client.wait_guild_config_cache_ready()
        audit_log = await self.find_recent_audit_log(guild.id, user.id, AuditLogAction.ban, now)
        if audit_log is None:
            return
        
        print(user, "was banned by", audit_log.user, "for the following reason:", audit_log.reason)
    
    # unban
    @commands.Cog.listener()
    async def on_member_unban(self, guild: Guild, user: User):
        now = utcnow()
        await self.client.wait_guild_config_cache_ready()
        audit_log = await self.find_recent_audit_log(guild.id, user.id, AuditLogAction.unban, now)
        if audit_log is None:
            return
        
        print(user, "was unbanned by", audit_log.user, "for the following reason:", audit_log.reason)

async def setup(client: Pidroid) -> None:
    await client.add_cog(NoIdea(client))
