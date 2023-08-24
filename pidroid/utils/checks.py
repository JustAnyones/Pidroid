from __future__ import annotations

from discord import Member, User, Guild, GroupChannel
from discord.ext.commands import BotMissingPermissions, MissingPermissions, Context
from discord.flags import flag_value
from discord.utils import get
from typing import TYPE_CHECKING, Optional, Union

from pidroid.constants import THEOTOWN_DEVELOPERS, THEOTOWN_GUILD, PIDROID_ID
from pidroid.models.exceptions import MissingUserPermissions
from pidroid.utils.aliases import GuildChannel

if TYPE_CHECKING:
    from pidroid.client import Pidroid

"""These are helper utilities to be used only within this scope."""

def _member_has_role(member: Member, role_id: int) -> bool:
    """Returns true if member has the specified role by ID."""
    return get(member.guild.roles, id=role_id) in member.roles

def member_has_guild_permission(member: Member, permission: Union[str, flag_value]) -> bool:
    """Returns true if member has the specified guild permission.
    
    This only takes into consideration the guild permissions and
    not most of the implied permissions or any of the channel permission overwrites.
    For 100% accurate permission calculation, please use member_has_channel_permission.

    This does take into consideration guild ownership,
    the administrator implication, and whether the member is timed out."""
    permissions = member.guild_permissions
    if isinstance(permission, flag_value):
        return permissions.value & permission.flag != 0
    return getattr(permissions, permission)

def member_has_channel_permission(channel: GuildChannel, member: Member, permission: Union[str, flag_value]) -> bool:
    """Returns true if member has the specified channel permission.
    
    This function takes into consideration the following cases:

    - Guild owner
    - Guild roles
    - Channel overrides
    - Member overrides
    - Member timeout"""
    permissions = channel.permissions_for(member)
    if isinstance(permission, flag_value):
        return permissions.value & permission.flag != 0
    return getattr(permissions, permission)



def check_guild_permissions(ctx: Context, **perms) -> bool:
    """Checks message author permissions for the guild.
    
    This only takes into consideration the guild permissions and
    not most of the implied permissions or any of the channel permission overwrites.
    For 100% accurate permission calculation, please use member_has_channel_permission.

    This does take into consideration guild ownership,
    the administrator implication, and whether the member is timed out.
    """
    assert isinstance(ctx.author, Member)

    permissions = ctx.author.guild_permissions

    missing = [perm for perm, value in perms.items() if getattr(permissions, perm) != value]

    if missing:
        raise MissingPermissions(missing)
    return True

def check_channel_permissions(ctx: Context, **perms) -> bool:
    """Checks message author permissions for the channel.
    
    This function takes into consideration the following cases:

    - Guild owner
    - Guild roles
    - Channel overrides
    - Member overrides
    - Member timeout"""
    assert isinstance(ctx.author, Member)
    assert not isinstance(ctx.channel, (GroupChannel))

    permissions = ctx.channel.permissions_for(ctx.author)

    missing = [perm for perm, value in perms.items() if getattr(permissions, perm) != value]

    if missing:
        raise MissingPermissions(missing)
    return True

def check_bot_channel_permissions(bot: Member, channel: GuildChannel, **perms) -> bool:
    """Checks bot permissions for the channel.
    
    This function takes into consideration the following cases:

    - Guild owner
    - Guild roles
    - Channel overrides
    - Member overrides
    - Member timeout"""
    permissions = channel.permissions_for(bot)

    missing = [perm for perm, value in perms.items() if getattr(permissions, perm) != value]

    if missing:
        raise BotMissingPermissions(missing)
    return True




def is_client_pidroid(client: Pidroid) -> bool:
    """Returns true if the current client user is Pidroid."""
    assert client.user is not None
    return client.user.id == PIDROID_ID

def is_guild_theotown(guild: Optional[Guild]) -> bool:
    """Returns true if the specified guild is the TheoTown guild."""
    if guild:
        return guild.id == THEOTOWN_GUILD
    return False




class TheoTownChecks:
    """This class implements role-based checks for TheoTown guild."""

    @staticmethod
    def is_developer(user: Union[Member, User]) -> bool:
        """Returns true if the member is a developer."""
        return user.id in THEOTOWN_DEVELOPERS

    @staticmethod
    def is_administrator(member: Member) -> bool:
        """Returns true if the member is considered to be at least an administrator on TheoTown guild."""
        return (
            TheoTownChecks.is_developer(member)              # Any TheoTown developer that is hardcoded
            or _member_has_role(member, 415194893917356052)  # City Council
            or _member_has_role(member, 365482773206532096)  # Mayor
            or _member_has_role(member, 710914534394560544)  # Elder
        )

    @staticmethod
    def is_senior_moderator(member: Member) -> bool:
        """Returns true if the member is considered to be at least a senior moderator on TheoTown guild."""
        return (
            _member_has_role(member, 381899421992091669)
            or TheoTownChecks.is_administrator(member)
        )

    @staticmethod
    def is_normal_moderator(member: Member) -> bool:
        """Returns true if the member is considered to be at least a normal moderator on TheoTown guild."""
        return (
            _member_has_role(member, 368799288127520769)
            or TheoTownChecks.is_senior_moderator(member)
        )

    @staticmethod
    def is_junior_moderator(member: Member) -> bool:
        """Returns true if the member is considered to be at least a junior moderator on TheoTown guild."""
        return (
            _member_has_role(member, 410512375083565066)
            or TheoTownChecks.is_normal_moderator(member)
        )

    @staticmethod
    def is_event_manager(member: Member) -> bool:
        """Returns true if the member is considered to be an event manager."""
        return _member_has_role(member, 584109249903198210)

    @staticmethod
    def is_event_voter(member: Member) -> bool:
        """Returns true if the member is authorized to vote in events."""
        return _member_has_role(member, 647443361627766804)




def is_guild_administrator(member: Member) -> bool:
    """Returns true if a member is considered to be a guild adminstrator by Pidroid.
    
    Pidroid only considers members with guild level administrator or manage_guild permissions
    to be guild administrators.
    
    This should not be used for anything except for a very generic check
    to see if a member is definitely an administrator."""
    if is_guild_theotown(member.guild):
        return TheoTownChecks.is_administrator(member)

    return (
        member_has_guild_permission(member, 'administrator')
        or member_has_guild_permission(member, 'manage_guild')
    )

def is_guild_moderator(member: Member) -> bool:
    """Returns true if a member is considered to be a guild moderator by Pidroid.
    
    Pidroid only considers members with guild level kick_members, ban_members or moderate_members permissions
    to be guild moderators. It also checks if the member is a guild administrator.
    
    This should not be used for anything except for a very generic check
    to see if a member is definitely a moderator."""
    if is_guild_theotown(member.guild):
        return TheoTownChecks.is_junior_moderator(member) # Junior moderator by design can be considered to be a minimal moderation role
    
    return (
        is_guild_administrator(member)
        or member_has_guild_permission(member, 'kick_members')
        or member_has_guild_permission(member, 'ban_members')
        or member_has_guild_permission(member, 'moderate_members')
    )



def has_moderator_guild_permissions(ctx: Context, **perms) -> bool:
    """Returns true if the author is a moderator and has the specified guild permissions."""
    assert isinstance(ctx.author, Member)
    if is_guild_theotown(ctx.guild):
        return TheoTownChecks.is_junior_moderator(ctx.author)

    # Ugly, I don't care
    try:
        return check_guild_permissions(ctx, **perms)
    except MissingPermissions:
        return False




async def check_can_modify_tags(ctx: Context):
    """Checks whether author has the permission to modify tags.

    It first checks if public can edit tags,
    if they can't it will resolve to moderators with manage_messages permission.
    
    Raises exception on failure."""
    assert ctx.guild is not None
    assert isinstance(ctx.author, Member)

    client: Pidroid = ctx.bot
    conf = await client.fetch_guild_configuration(ctx.guild.id)
    if conf.public_tags:
        return True

    if is_guild_theotown(ctx.guild):
        if not TheoTownChecks.is_junior_moderator(ctx.author):
            raise MissingUserPermissions('You need to be at least a junior moderator to run this command!')
        return True
    return check_guild_permissions(ctx, manage_messages=True)

def check_junior_moderator_permissions(ctx: Context, **perms) -> bool:
    """Checks whether author has junior moderator permissions in TheoTown guild channel
    or the equivalent permissions in other guild channels.
    
    Raises exception on failure."""
    assert isinstance(ctx.author, Member)
    if is_guild_theotown(ctx.guild):
        if not TheoTownChecks.is_junior_moderator(ctx.author):
            raise MissingUserPermissions('You need to be at least a junior moderator to run this command!')
        return True
    return check_channel_permissions(ctx, **perms)

def check_normal_moderator_permissions(ctx: Context, **perms) -> bool:
    """Checks whether author has normal moderator permissions in TheoTown guild channel
    or the equivalent permissions in other guild channels.
    
    Raises exception on failure."""
    assert isinstance(ctx.author, Member)
    if is_guild_theotown(ctx.guild):
        if not TheoTownChecks.is_normal_moderator(ctx.author):
            raise MissingUserPermissions('You need to be at least a moderator to run this command!')
        return True
    return check_channel_permissions(ctx, **perms)

def check_senior_moderator_permissions(ctx: Context, **perms) -> bool:
    """Checks whether author has senior moderator permissions in TheoTown guild channel
    or the equivalent permissions in other guild channels.
    
    Raises exception on failure."""
    assert isinstance(ctx.author, Member)
    if is_guild_theotown(ctx.guild):
        if not TheoTownChecks.is_senior_moderator(ctx.author):
            raise MissingUserPermissions('You need to be at least a senior moderator to run this command!')
        return True
    return check_channel_permissions(ctx, **perms)
