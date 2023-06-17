import datetime
import logging
from typing import TYPE_CHECKING, List, Optional, Union
from discord import Asset, AuditLogEntry, ChannelType, Colour, Object, Permissions, Role

from discord.ext import commands

from pidroid.models.logs import BaseLog

# TODO: All punishments throughout the server (bans, unbans, warns, kicks, jails)
# TODO: Deleted and edited messages - and purges

logger = logging.getLogger('Pidroid')

if TYPE_CHECKING:
    from pidroid.client import Pidroid

class LoggingHandler(commands.Cog):
    """This class implements a cog for handling guild related event logging."""
    
    def __init__(self, client: Pidroid):
        self.client = client
        
    async def acquire_guild_information(self, guild_id: int):
        await self.client.wait_until_guild_configurations_loaded()
        return await self.client.fetch_guild_information(guild_id)    
        
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
        handlers = {
            # Adding, removal and editing of channels
            action.channel_create: self._on_channel_create,
            action.channel_delete: self._on_channel_delete,
            action.channel_update: self._on_channel_update,
            # Channel permission changes
            action.overwrite_create: self._on_overwrite_create,
            action.overwrite_delete: self._on_overwrite_delete,
            action.overwrite_update: self._on_overwrite_update,
            
            # Adding and, removal and editing of roles
            action.role_create: self._on_role_create,
            action.role_delete: self._on_role_delete,
            action.role_update: self._on_role_update,
            
            # Changes in members (Change in server name and roles)
            action.member_update: self._on_member_update,
            action.member_role_update: self._on_member_role_update,

        }
        
        coro = handlers.get(entry.action.value, None)
        if coro is None:
            return
        await coro(entry)
        
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
        pass
    
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
        pass
    
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
        pass
    
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
        guild = entry.guild
        issuer = entry.user
        channel = entry.target
        reason = entry.reason
        role_or_member = entry.extra
        
        id: int = entry.after.id
        type: ChannelType = entry.after.type # The type of channel.
        deny: Permissions = entry.after.deny # The permissions being denied.
        allow: Permissions = entry.after.allow # The permissions being allowed.
    
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
        guild = entry.guild
        issuer = entry.user
        channel = entry.target
        reason = entry.reason
        role_or_member = entry.extra
        
        id: int = entry.before.id
        type: ChannelType = entry.before.type # The type of channel.
        deny: Permissions = entry.before.deny # The permissions being denied.
        allow: Permissions = entry.before.allow # The permissions being allowed.
    
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
        guild = entry.guild
        issuer = entry.user
        channel = entry.target
        reason = entry.reason
        role_or_member = entry.extra
        
        id: int = entry.after.id
        type: ChannelType = entry.after.type # The type of channel.
        deny: Permissions = entry.after.deny # The permissions being denied.
        allow: Permissions = entry.after.allow # The permissions being allowed.
    
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
        guild = entry.guild
        issuer = entry.user
        role = entry.target
        reason = entry.reason
        
        colour: Colour = entry.after.colour
        mentionable: bool = entry.after.mentionable
        hoist: bool = entry.after.hoist
        icon: Asset = entry.after.icon
        unicode_emoji: str = entry.after.unicode_emoji
        name: str = entry.after.name
        permissions: Permissions = entry.after.permissions
    
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
        guild = entry.guild
        issuer = entry.user
        role = entry.target
        reason = entry.reason
        
        colour: Colour = entry.before.colour
        mentionable: bool = entry.before.mentionable
        hoist: bool = entry.before.hoist
        name: str = entry.before.name
        permissions: Permissions = entry.before.permissions
    
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
        guild = entry.guild
        issuer = entry.user
        role = entry.target
        reason = entry.reason
        
        colour: Colour = entry.after.colour
        mentionable: bool = entry.after.mentionable
        hoist: bool = entry.after.hoist
        icon: Asset = entry.after.icon
        unicode_emoji: str = entry.after.unicode_emoji
        name: str = entry.after.name
        permissions: Permissions = entry.after.permissions
    
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
        guild = entry.guild
        issuer = entry.user
        receiver = entry.target
        reason = entry.reason
        
        nick: Optional[str] = entry.after.nick
        mute: bool = entry.after.mute # Whether the member is being server muted.
        deaf: bool = entry.after.deaf # Whether the member is being server deafened.
        timed_out_until: Optional[datetime.datetime] = entry.after.timed_out_until
    
    async def _on_member_role_update(self, entry: AuditLogEntry):
        """
        A member’s role has been updated. This triggers when a member either gains a role or loses a role.

        When this is the action, the type of target is the Member, User, or Object who got the role.

        Possible attributes for AuditLogDiff:
        - roles
        """
        guild = entry.guild
        issuer = entry.user
        receiver = entry.target
        reason = entry.reason
        roles: List[Union[Role, Object]] = entry.after.roles
        
    @commands.Cog.listener()
    async def on_pidroid_log(self, log: BaseLog):
        info = await self.acquire_guild_information(log.guild.id)
        # If logging system is not active, do nothing
        if not info.logging_active:
            return
        # If we don't have a logging channel set
        if info.logging_channel_id is None:
            return
        
        channel = await self.client.get_or_fetch_guild_channel(log.guild, info.logging_channel_id)
        if channel:
            await channel.send(embed=log.as_embed())
        else:
            logger.warning(f"Could not resolve a guild channel {info.logging_channel_id} to send a Pidroid log to")

async def setup(client: Pidroid) -> None:
    await client.add_cog(LoggingHandler(client))