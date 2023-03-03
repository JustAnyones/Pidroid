import datetime
import discord

from contextlib import suppress
from discord import Object
from discord.member import Member
from discord.user import User
from discord.guild import Guild
from discord.embeds import Embed
from discord import File, AuditLogAction, AuditLogEntry, AuditLogDiff
from discord.ext import commands # type: ignore
from typing import Optional, Union

from pidroid.client import Pidroid
from pidroid.cogs.utils.time import utcnow
from pidroid.cogs.models.case import Case, Ban, Warning, Jail, Kick, Timeout

def _is_timed_out(diff: AuditLogDiff) -> bool:
    if diff.timed_out_until is not None:
        return utcnow() < diff.timed_out_until
    return False

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
    
    async def on_audit_log_entry_create(self, entry: AuditLogEntry):
        await self.client.wait_until_guild_configurations_loaded()
        meths = {
            AuditLogAction.member_update: self.on_audit_log_member_update,
            AuditLogAction.kick: self.on_audit_log_kick,
            AuditLogAction.ban: self.on_audit_log_ban,
            AuditLogAction.unban: self.on_audit_log_unban
        }
        
        self.client.logger.info("???")
        # According to the docs, https://discordpy.readthedocs.io/en/stable/api.html#discord.AuditLogAction
        # entry.target is either a Object, or any specific type.
        assert entry.target is not None
        coroutine = meths.get(entry.action, None)
        if coroutine is None:
            return
        return await coroutine(entry)
    
    async def on_audit_log_member_update(self, entry: AuditLogEntry):
        assert isinstance(entry.target, (Object, Member, User))
        user = await self.client.get_or_fetch_user(entry.target.id)
        
        before = entry.before
        after = entry.after
        
        # Detect timeout
        if not _is_timed_out(before) and _is_timed_out(after):
            print(user, "was timed out by", entry.user, "for the following reason:", entry.reason)

        # Detect timeout removal
        if _is_timed_out(before) and not _is_timed_out(after):
            print(user, "time out removed by", entry.user, "for the following reason:", entry.reason)

        
        # DETECT ROLE CHANGES
        pass
        
    
    async def on_audit_log_kick(self, entry: AuditLogEntry):
        assert isinstance(entry.target, (Object, User))
        user = await self.client.get_or_fetch_user(entry.target.id)
        self.client.logger.info(f'{user} was kicked by {entry.user} for the following reason: {entry.reason}')
        kick = Kick(self.client.api, entry.guild, None, entry.user, user)
        kick.reason = entry.reason
        await kick.create_entry()
    
    
    async def on_audit_log_ban(self, entry: AuditLogEntry):
        assert isinstance(entry.target, (Object, User))
        user = await self.client.get_or_fetch_user(entry.target.id)
        self.client.logger.info(f'{user} was banned by {entry.user} for the following reason: {entry.reason}')
        ban = Ban(self.client.api, entry.guild, None, entry.user, user)
        ban.reason = entry.reason
        await ban.create_entry()
    
    async def on_audit_log_unban(self, entry: AuditLogEntry):
        assert isinstance(entry.target, (Object, User))
        user = await self.client.get_or_fetch_user(entry.target.id)
        self.client.logger.info(f'{user} was unbanned by {entry.user} for the following reason: {entry.reason}')
        ban = Ban(self.client.api, entry.guild, None, entry.user, user)
        ban.reason = entry.reason
        await ban.revoke_entry()
        
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
        await self.client.wait_until_guild_configurations_loaded()
        
        # Detect whether roles got changed
        if set(before.roles) == set(after.roles):
            return
        print("Roles have changed:", before.roles, "->", after.roles)

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
