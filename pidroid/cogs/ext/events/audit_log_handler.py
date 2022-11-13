import datetime
import discord

from contextlib import suppress
from discord.member import Member
from discord.user import User
from discord.guild import Guild
from discord.embeds import Embed
from discord import RawMemberRemoveEvent
from discord import File, AuditLogAction, AuditLogEntry
from discord.message import Message
from discord.ext import commands # type: ignore
from typing import Optional, Union

from pidroid.client import Pidroid
from pidroid.cogs.utils.time import utcnow
from pidroid.cogs.models.case import Case, Ban, Warning, Jail, Kick, Timeout

class NoIdea(commands.Cog): # type: ignore
    """This class implements a cog for handling invocation of copypastas and other memes invoked by events like on_message."""

    def __init__(self, client: Pidroid):
        self.client = client

        # Register some listeners to punishment events
        self.client.api.add_listener("on_ban_issued", self.on_ban_issued)
        self.client.api.add_listener("on_ban_revoked", self.on_ban_revoked)
        self.client.api.add_listener("on_ban_expired", self.on_ban_expired)
        self.client.api.add_listener("on_jail_issued", self.on_jail_issued)
        self.client.api.add_listener("on_jail_revoked", self.on_jail_revoked)
        self.client.api.add_listener("on_kick_issued", self.on_kick_issued)
        self.client.api.add_listener("on_timeout_issued", self.on_timeout_issued)
        self.client.api.add_listener("on_timeout_revoked", self.on_timeout_revoked)
        self.client.api.add_listener("on_timeout_expired", self.on_timeout_expired)
        self.client.api.add_listener("on_warning_issued", self.on_warning_issued)
        
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
        # First check if we have guild access
        guild = await self._get_or_fetch_guild(guild_id)
        if guild is None:
            return None

        # TODO: fix order of logs
        # if it encounters newer one, quit
        return None
        print(f"Searching 100 audit logs for action: {action}")
        search_time = time_called - datetime.timedelta(seconds=15) # I don't like this
        async for entry in guild.audit_logs(action=action, after=search_time):
            # If target is not a member nor user, ignore that entry
            if not isinstance(entry.target, (Member, User)):
                continue

            # Ignore logs whose target is not who we're searching for
            if entry.target.id != member_id:
                continue
            
            # If for some reason user is none
            if entry.user is None:
                continue
            
            # We ignore audit entries by bots
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
            if log:
                print(after, "was timed out by", log.user, "for the following reason:", log.reason)

        # Detect timeout removal
        if before.is_timed_out() and not after.is_timed_out():
            log = await self.find_recent_audit_log(after.guild.id, after.id, AuditLogAction.member_update, now)
            if log:
                print(after, "time out removed by", log.user, "for the following reason:", log.reason)
        
        # Detect whether roles got changed
        if set(before.roles) == set(after.roles):
            return
        print("Roles have changed:", before.roles, "->", after.roles)
    
    # If user is kicked manually, we just need to store the kick entry to the database
    @commands.Cog.listener()
    async def on_raw_member_remove(self, payload: RawMemberRemoveEvent):
        now = utcnow()
        await self.client.wait_guild_config_cache_ready()
        audit_log = await self.find_recent_audit_log(payload.guild_id, payload.user.id, AuditLogAction.kick, now)
        if audit_log is None:
            return
        
        # We need guild object
        guild = await self._get_or_fetch_guild(payload.guild_id)
        if guild is None:
            return

        assert audit_log.user is not None
        self.client.logger.info(f'{payload.user} was kicked by {audit_log.user} for the following reason: {audit_log.reason}')
        kick = Kick(self.client.api, guild, None, audit_log.user, payload.user)
        kick.reason = audit_log.reason
        await kick.create_entry()
    
    # If user is banned manually, it would make sense to create a ban entry in the database as well
    @commands.Cog.listener()
    async def on_member_ban(self, guild: Guild, user: Union[Member, User]):
        now = utcnow()
        await self.client.wait_guild_config_cache_ready()
        audit_log = await self.find_recent_audit_log(guild.id, user.id, AuditLogAction.ban, now)
        if audit_log is None:
            return
        
        assert audit_log.user is not None
        self.client.logger.info(f'{user} was banned by {audit_log.user} for the following reason: {audit_log.reason}')
        ban = Ban(self.client.api, guild, None, audit_log.user, user)
        ban.reason = audit_log.reason
        await ban.create_entry()

    
    # If user is unbanned manually, it would make sense to revoke it in the database as well
    @commands.Cog.listener()
    async def on_member_unban(self, guild: Guild, user: User):
        now = utcnow()
        await self.client.wait_guild_config_cache_ready()
        audit_log = await self.find_recent_audit_log(guild.id, user.id, AuditLogAction.unban, now)
        if audit_log is None:
            return

        assert audit_log.user is not None
        self.client.logger.info(f'{user} was unbanned by {audit_log.user} for the following reason: {audit_log.reason}')
        ban = Ban(self.client.api, guild, None, audit_log.user, user)
        ban.reason = audit_log.reason
        await ban.revoke_entry()

    async def _message_user(self, user: Union[Member, User], embed: Embed):
        try:
            await user.send(embed=embed)
        except Exception: # nosec
            pass

    # Listeners
    async def on_ban_issued(self, ban: Ban):
        await self._message_user(ban.user, ban.private_message_issue_embed)

    async def on_ban_revoked(self, ban: Ban):
        await self._message_user(ban.user, ban.private_message_revoke_embed)

    async def on_ban_expired(self, ban: Ban):
        pass

    async def on_kick_issued(self, kick: Kick):
        await self._message_user(kick.user, kick.private_message_issue_embed)

    async def on_jail_issued(self, jail: Jail):
        await self._message_user(jail.user, jail.private_message_issue_embed)

    async def on_jail_revoked(self, jail: Jail):
        await self._message_user(jail.user, jail.private_message_revoke_embed)

    async def on_timeout_issued(self, timeout: Timeout):
        await self._message_user(timeout.user, timeout.private_message_issue_embed)

    async def on_timeout_revoked(self, timeout: Timeout):
        await self._message_user(timeout.user, timeout.private_message_revoke_embed)

    async def on_timeout_expired(self, timeout: Timeout):
        pass

    async def on_warning_issued(self, warning: Warning):
        await self._message_user(warning.user, warning.private_message_issue_embed)

async def setup(client: Pidroid) -> None:
    await client.add_cog(NoIdea(client))
