from __future__ import annotations

import logging

from discord import AuditLogDiff, AuditLogEntry, Member, Object, Role, User, abc, AuditLogAction
from discord.ext import commands
from typing import TYPE_CHECKING, Any

from pidroid.models.logs import _ChannelData, _OverwriteData, _MemberRoleUpdateData, _MemberUpdateData, _RoleUpdateData, ChannelCreateData, ChannelCreateLog, ChannelDeleteData, ChannelDeleteLog, ChannelUpdateData, ChannelUpdateLog, MemberRoleUpdateData, MemberRoleUpdateLog, MemberUpdateData, MemberUpdateLog, OverwriteCreateData, OverwriteCreateLog, OverwriteDeleteData, OverwriteDeleteLog, OverwriteUpdateData, OverwriteUpdateLog, PidroidLog, RoleCreateData, RoleCreateLog, RoleDeleteData, RoleDeleteLog, RoleUpdateData, RoleUpdateLog

# TODO: All punishments throughout the server (bans, unbans, warns, kicks, jails)
# TODO: Deleted and edited messages - and purges

if TYPE_CHECKING:
    from pidroid.client import Pidroid

logger = logging.getLogger('Pidroid')

class AuditLogDiffWrapper:
    def __init__(self, diff: AuditLogDiff, *, log: bool = False) -> None:
        super().__init__()
        self.__dict = diff.__dict__
        self.__logging_on = log

    def __getattr__(self, item: str) -> Any:
        val = self.__dict.get(item, None)
        if self.__logging_on:
            logger.debug(f"Asking for attribute {item} ({type(val)}): {val}")
        return val


class LoggingService(commands.Cog):
    """This class implements a cog for handling guild related event logging."""
    
    def __init__(self, client: Pidroid):
        super().__init__()
        self.client = client
        
    async def acquire_guild_conf(self, guild_id: int):
        await self.client.wait_until_guild_configurations_loaded()
        return await self.client.fetch_guild_configuration(guild_id)    
        
    @commands.Cog.listener() 
    async def on_audit_log_entry_create(self, entry: AuditLogEntry):
        """
        Called when a Guild gets a new audit log entry. Must have view_audit_log permission in the guild to receive this.

        This requires Intents.moderation to be enabled.

        Audit log entries received through the gateway are subject to data retrieval from cache rather than REST.
        This means that some data might not be present when you expect it to be.
        For example, the AuditLogEntry.target attribute will usually be a discord.Object and the AuditLogEntry.user attribute will depend on user and member cache.

        To get the user ID of entry, AuditLogEntry.user_id can be used instead.
        """
        action = entry.action

        # This dictionary defines all specific action handlers
        handlers = {
            # Adding, removal and editing of channels
            #AuditLogAction.channel_create: self._on_channel_create,
            #AuditLogAction.channel_delete: self._on_channel_delete,
            #AuditLogAction.channel_update: self._on_channel_update,
            # Channel permission changes
            #AuditLogAction.overwrite_create: self._on_overwrite_create,
            #AuditLogAction.overwrite_delete: self._on_overwrite_delete,
            #AuditLogAction.overwrite_update: self._on_overwrite_update,
            
            # Adding, removal and editing of roles
            AuditLogAction.role_create: self._on_role_create,
            AuditLogAction.role_delete: self._on_role_delete,
            AuditLogAction.role_update: self._on_role_update,
            
            # Changes in members such as their roles, usernames and status
            # in voice channels
            AuditLogAction.member_update: self._on_member_update,
            AuditLogAction.member_role_update: self._on_member_role_update,
            AuditLogAction.member_move: None,
            AuditLogAction.member_disconnect: None,

            # Member management related
            AuditLogAction.kick: None,
            AuditLogAction.member_prune: None,
            AuditLogAction.ban: None,
            AuditLogAction.unban: None,

            # No idea
            AuditLogAction.message_delete: None,      # Would rather implement as event
            AuditLogAction.message_bulk_delete: None, # Would rather implement as event
            AuditLogAction.thread_create: None,
            AuditLogAction.thread_delete: None,
            AuditLogAction.thread_update: None,
        }
        coro = handlers.get(action, None)
        if coro is None:
            return
        try:
            await coro(entry)
        except Exception as e:
            logger.exception(e)
    

    async def _on_channel_create(self, entry: AuditLogEntry):
        """
        A new channel was created.

        When this is the action, the type of target is either a abc.GuildChannel or Object with an ID.

        A more filled out object in the Object case can be found by using after.

        Possible attributes for AuditLogDiff:
        - name
        - type
        - overwrites
        """
        diff_after = AuditLogDiffWrapper(entry.after, log=True)
        assert isinstance(entry.target, (abc.GuildChannel, Object))
        data = ChannelCreateData(
            guild=entry.guild, user=entry.user,
            channel=entry.target,
            reason=entry.reason,created_at=entry.created_at,
            name=diff_after.name,
            type=diff_after.type,
            overwrites=diff_after.overwrites
        )
        self.client.dispatch('pidroid_log', ChannelCreateLog(data))
    

    async def _on_channel_delete(self, entry: AuditLogEntry):
        """
        A channel was deleted.

        When this is the action, the type of target is an Object with an ID.

        A more filled out object can be found by using the before object.

        Possible attributes for AuditLogDiff:
        - name
        - type
        - overwrites
        - flags
        - nsfw
        - slowmode_delay
        """
        diff_before = AuditLogDiffWrapper(entry.before, log=True)
        assert isinstance(entry.target, (abc.GuildChannel, Object))
        data = ChannelDeleteData(
            guild=entry.guild, user=entry.user,
            channel=entry.target,
            reason=entry.reason,created_at=entry.created_at,

            name=diff_before.name,
            type=diff_before.type,
            overwrites=diff_before.overwrites,
            flags=diff_before.flags,
            nsfw=diff_before.nsfw,
            slowmode_delay=diff_before.slowmode_delay
        )
        self.client.dispatch('pidroid_log', ChannelDeleteLog(data))
    

    async def _on_channel_update(self, entry: AuditLogEntry):
        """
        A channel was updated. Things that trigger this include:
        - The channel name or topic was changed
        - The channel bitrate was changed

        When this is the action, the type of target is the abc.GuildChannel or Object with an ID.

        A more filled out object in the Object case can be found by using after or before.

        Possible attributes for AuditLogDiff:
        - name
        - type
        - position
        - overwrites
        - topic
        - bitrate
        - rtc_region
        - video_quality_mode
        - default_auto_archive_duration
        - nsfw
        - slowmode_delay
        - user_limit
        """
        diff_before = AuditLogDiffWrapper(entry.before, log=True)
        diff_after = AuditLogDiffWrapper(entry.after, log=True)
        assert isinstance(entry.target, (abc.GuildChannel, Object))
        before = _ChannelData(
            name=diff_before.name,
            type=diff_before.type,
            position=diff_before.position,
            overwrites=diff_before.overwrites,
            topic=diff_before.topic,
            bitrate=diff_before.bitrate,
            rtc_region=diff_before.rtc_region,
            video_quality_mode=diff_before.video_quality_mode,
            default_auto_archive_duration=diff_before.default_auto_archive_duration,
            nsfw=diff_before.nsfw,
            slowmode_delay=diff_before.slowmode_delay,
            user_limit=diff_before.user_limit
        )
        after = _ChannelData(
            name=diff_after.name,
            type=diff_after.type,
            position=diff_after.position,
            overwrites=diff_after.overwrites,
            topic=diff_after.topic,
            bitrate=diff_after.bitrate,
            rtc_region=diff_after.rtc_region,
            video_quality_mode=diff_after.video_quality_mode,
            default_auto_archive_duration=diff_after.default_auto_archive_duration,
            nsfw=diff_after.nsfw,
            slowmode_delay=diff_after.slowmode_delay,
            user_limit=diff_after.user_limit
        )
        data = ChannelUpdateData(
            guild=entry.guild, user=entry.user,
            channel=entry.target,
            reason=entry.reason,created_at=entry.created_at,
            before=before,
            after=after
        )
        self.client.dispatch('pidroid_log', ChannelUpdateLog(data))
    

    async def _on_overwrite_create(self, entry: AuditLogEntry):
        """
        A channel permission overwrite was created.

        When this is the action, the type of target is the abc.GuildChannel or Object with an ID.

        When this is the action, the type of extra is either a Role or Member. If the object is not found then it is a Object with an ID being filled, a name, and a type attribute set to either 'role' or 'member' to help dictate what type of ID it is.

        Possible attributes for AuditLogDiff:
        - deny
        - allow
        - id
        - type
        """
        assert isinstance(entry.target, (abc.GuildChannel, Object))
        assert isinstance(entry.extra, (Role, Member, Object))
        diff_after = AuditLogDiffWrapper(entry.after, log=True)
        data = OverwriteCreateData(
            guild=entry.guild, user=entry.user,
            channel=entry.target, role_or_user=entry.extra,
            reason=entry.reason, created_at=entry.created_at,

            id=diff_after.id,
            type=diff_after.type,
            deny=diff_after.deny,
            allow=diff_after.allow
        )
        self.client.dispatch('pidroid_log', OverwriteCreateLog(data))
    

    async def _on_overwrite_delete(self, entry: AuditLogEntry):
        """
        A channel permission overwrite was deleted.

        See _on_overwrite_create for more information on how the target and extra fields are set.

        Possible attributes for AuditLogDiff:
        - deny
        - allow
        - id
        - type
        """
        assert isinstance(entry.target, (abc.GuildChannel, Object))
        assert isinstance(entry.extra, (Role, Member, Object))
        diff_before = AuditLogDiffWrapper(entry.before, log=True)
        data = OverwriteDeleteData(
            guild=entry.guild, user=entry.user,
            channel=entry.target, role_or_user=entry.extra,
            reason=entry.reason, created_at=entry.created_at,

            id=diff_before.id,
            type=diff_before.type,
            deny=diff_before.deny,
            allow=diff_before.allow
        )
        self.client.dispatch('pidroid_log', OverwriteDeleteLog(data))
    

    async def _on_overwrite_update(self, entry: AuditLogEntry):
        """
        A channel permission overwrite was changed, this is typically when the permission values change.

        See overwrite_create for more information on how the target and extra fields are set.

        Possible attributes for AuditLogDiff:
        - deny
        - allow
        - id
        - type
        """
        assert isinstance(entry.target, (abc.GuildChannel, Object))
        assert isinstance(entry.extra, (Role, Member, Object))
        diff_before = AuditLogDiffWrapper(entry.before, log=True)
        diff_after = AuditLogDiffWrapper(entry.after, log=True)
        before = _OverwriteData(
            id=diff_before.id, type=diff_before.type,
            deny=diff_before.deny, allow=diff_before.allow
        )
        after = _OverwriteData(
            id=diff_after.id, type=diff_after.type,
            deny=diff_after.deny, allow=diff_after.allow
        )
        data = OverwriteUpdateData(
            guild=entry.guild, user=entry.user,
            channel=entry.target, role_or_user=entry.extra,
            reason=entry.reason, created_at=entry.created_at,
            before=before, after=after
        )
        self.client.dispatch('pidroid_log', OverwriteUpdateLog(data))

    async def _on_role_create(self, entry: AuditLogEntry):
        """
        A new role was created.

        When this is the action, the type of target is the Role or a Object with the ID.

        Possible attributes for AuditLogDiff:
        - colour
        - mentionable
        - hoist
        - icon
        - unicode_emoji
        - name
        - permissions
        """
        assert isinstance(entry.target, (Role, Object))
        diff_after = AuditLogDiffWrapper(entry.after, log=True)
        data = RoleCreateData(
            guild=entry.guild,
            user=entry.user, role=entry.target, reason=entry.reason,
            created_at=entry.created_at,

            colour=diff_after.colour, mentionable=diff_after.mentionable,
            hoist=diff_after.hoist, icon=diff_after.icon,
            unicode_emoji=diff_after.unicode_emoji, name=diff_after.name,
            permissions=diff_after.permissions
        )
        self.client.dispatch('pidroid_log', RoleCreateLog(data))
    

    async def _on_role_delete(self, entry: AuditLogEntry):
        """
        A role was deleted.

        When this is the action, the type of target is the Role or a Object with the ID.

        Possible attributes for AuditLogDiff:
        - colour
        - mentionable
        - hoist
        - name
        - permissions
        """
        assert isinstance(entry.target, (Role, Object))
        diff_before = AuditLogDiffWrapper(entry.before, log=True)
        data = RoleDeleteData(
            guild=entry.guild,
            user=entry.user, role=entry.target, reason=entry.reason,
            created_at=entry.created_at,

            colour=diff_before.colour, mentionable=diff_before.mentionable,
            hoist=diff_before.hoist,
            name=diff_before.name,
            permissions=diff_before.permissions
        )
        self.client.dispatch('pidroid_log', RoleDeleteLog(data))
    

    async def _on_role_update(self, entry: AuditLogEntry):
        """
        A role was updated. This triggers in the following situations:
        - The name has changed
        - The permissions have changed
        - The colour has changed
        - The role icon (or unicode emoji) has changed
        - Its hoist/mentionable state has changed

        When this is the action, the type of target is the Role or a Object with the ID.

        Possible attributes for AuditLogDiff:
        - colour
        - mentionable
        - hoist
        - icon
        - unicode_emoji
        - name
        - permissions
        """
        assert isinstance(entry.target, (Role, Object))
        diff_before = AuditLogDiffWrapper(entry.before, log=True)
        diff_after = AuditLogDiffWrapper(entry.after, log=True)
        before = _RoleUpdateData(
            colour=diff_before.colour, mentionable=diff_before.mentionable,
            hoist=diff_before.hoist, icon=diff_before.icon,
            unicode_emoji=diff_before.unicode_emoji, name=diff_before.name,
            permissions=diff_before.permissions
        )
        after = _RoleUpdateData(
            colour=diff_after.colour, mentionable=diff_after.mentionable,
            hoist=diff_after.hoist, icon=diff_after.icon,
            unicode_emoji=diff_after.unicode_emoji, name=diff_after.name,
            permissions=diff_after.permissions
        )
        data = RoleUpdateData(
            guild=entry.guild,
            user=entry.user, role=entry.target, reason=entry.reason,
            created_at=entry.created_at,
            before=before, after=after
        )
        self.client.dispatch('pidroid_log', RoleUpdateLog(data))
    

    async def _on_member_update(self, entry: AuditLogEntry):
        """
        A member has updated. This triggers in the following situations:
        - A nickname was changed
        - They were server muted or deafened (or it was undo’d)

        When this is the action, the type of target is the Member, User, or Object who got updated.

        Possible attributes for AuditLogDiff:
        - nick
        - mute
        - deaf
        - timed_out_until
        """
        assert isinstance(entry.target, (Member, User, Object))
        diff_before = AuditLogDiffWrapper(entry.before, log=True)
        diff_after = AuditLogDiffWrapper(entry.after, log=True)
        before = _MemberUpdateData(nick=diff_before.nick, mute=diff_before.mute, deaf=diff_before.deaf, timed_out_until=diff_before.timed_out_until)
        after = _MemberUpdateData(nick=diff_after.nick, mute=diff_after.mute, deaf=diff_after.deaf, timed_out_until=diff_after.timed_out_until)
        data = MemberUpdateData(
            guild=entry.guild, user=entry.user, reason=entry.reason, created_at=entry.created_at,
            member=entry.target, before=before, after=after
        )
        self.client.dispatch('pidroid_log', MemberUpdateLog(data))
    

    async def _on_member_role_update(self, entry: AuditLogEntry):
        """
        A member’s role has been updated. This triggers when a member either gains a role or loses a role.

        When this is the action, the type of target is the Member, User, or Object who got the role.

        Possible attributes for AuditLogDiff:
        - roles
        """
        assert isinstance(entry.target, (Member, User, Object))
        diff_before = AuditLogDiffWrapper(entry.before)
        diff_after = AuditLogDiffWrapper(entry.after)
        before = _MemberRoleUpdateData(roles=diff_before.roles)
        after = _MemberRoleUpdateData(roles=diff_after.roles)
        data = MemberRoleUpdateData(
            guild=entry.guild, user=entry.user, reason=entry.reason, created_at=entry.created_at,
            member=entry.target, before=before, after=after
        )
        self.client.dispatch('pidroid_log', MemberRoleUpdateLog(data))
    
    
    @commands.Cog.listener()
    async def on_pidroid_log(self, log: PidroidLog):
        logger.debug(f"Log received: {type(log)}")
        conf = await self.acquire_guild_conf(log.guild.id)
        # If logging system is not active, do nothing
        if not conf.logging_active:
            return
        
        # If we don't have a logging channel set
        # TODO: consider migrating to allow to set custom channels for different logs
        if conf.logging_channel_id is None:
            return
        
        channel = await self.client.get_or_fetch_guild_channel(log.guild, conf.logging_channel_id)
        if channel:
            await self.client.queue(channel, log.as_embed())
        else:
            logger.warning(f"Could not resolve a guild channel {conf.logging_channel_id} to send a Pidroid log to")

async def setup(client: Pidroid) -> None:
    await client.add_cog(LoggingService(client))