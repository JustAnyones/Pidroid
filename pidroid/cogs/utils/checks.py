from __future__ import annotations

from discord import Member, Thread, User, TextChannel, Guild, VoiceChannel, StageChannel
from discord.ext.commands import BotMissingPermissions, MissingPermissions, Context # type: ignore
from discord.utils import get
from typing import TYPE_CHECKING, Optional, Union

from pidroid.constants import DEVELOPMENT_BOTS, THEOTOWN_DEVELOPERS, THEOTOWN_GUILD, JUSTANYONE_ID, PIDROID_ID, CHEESE_EATERS, BOT_COMMANDS_CHANNEL
from pidroid.cogs.models.exceptions import MissingUserPermissions
from pidroid.cogs.utils.aliases import DiscordUser, GuildChannel, GuildTextChannel, AllChannels

if TYPE_CHECKING:
    from pidroid.client import Pidroid

# Generic permission check functions
def member_has_role(member: Member, role_id: int):
    return get(member.guild.roles, id=role_id) in member.roles

def has_permission(channel: GuildChannel, member: Member, permission: str) -> bool:
    return getattr(channel.permissions_for(member), permission)

def has_guild_permission(member: Member, permission: str) -> bool:
    return getattr(member.guild_permissions, permission)

# Check whether member is above the another user in terms of roles
def member_above_moderator(member: Member, moderator: Member):
    if not hasattr(member, 'top_role'):
        return False
    return member.top_role > moderator.top_role

# Check whether Pidroid is above or below specified user in terms of roles
def member_above_bot(guild: Guild, member: Member):
    return member_above_moderator(member, guild.me)

# Generic raw permission check
def check_permissions(ctx: Context, **perms):
    ch = ctx.channel
    permissions = ch.permissions_for(ctx.author)

    missing = [perm for perm, value in perms.items() if getattr(permissions, perm) != value]

    if missing:
        raise MissingPermissions(missing)
    return True

def check_bot_channel_permissions(channel: Union[TextChannel, VoiceChannel, StageChannel], member: Member, **perms):
    permissions = channel.permissions_for(member)

    missing = [perm for perm, value in perms.items() if getattr(permissions, perm) != value]

    if missing:
        raise BotMissingPermissions(missing)
    return True

def guild_has_configuration(client: Pidroid, guild: Guild) -> bool:
    return client.get_guild_configuration(guild.id) is not None

def is_user_justanyone(user: Union[Member, User]) -> bool:
    """Returns true if specified user is JustAnyone."""
    return user.id == JUSTANYONE_ID

def is_client_development(client: Pidroid) -> bool:
    """Returns true if client user is one of the development bots."""
    assert client.user is not None
    return client.user.id in DEVELOPMENT_BOTS

def is_client_pidroid(client: Pidroid) -> bool:
    """Returns true if client user is Pidroid."""
    assert client.user is not None
    return client.user.id == PIDROID_ID

def is_user_cheese_consumer(user: Union[Member, User]) -> bool:
    """Returns true if specified user is part of cheese eaters."""
    return user.id in CHEESE_EATERS

def is_channel_bot_commands(channel: AllChannels) -> bool:
    return channel.id == BOT_COMMANDS_CHANNEL

def is_guild_theotown(guild: Optional[Guild]) -> bool:
    if guild:
        return guild.id == THEOTOWN_GUILD
    return False


class TheoTownChecks:

    @staticmethod
    def is_administrator(member: Member) -> bool:
        return (
            is_user_justanyone(member)
            or member_has_role(member, 415194893917356052)  # City Council
            or member_has_role(member, 365482773206532096)  # Mayor
            or member_has_role(member, 710914534394560544)  # Elder
        )

    @staticmethod
    def is_senior_moderator(member: Member) -> bool:
        return (
            member_has_role(member, 381899421992091669)
            or TheoTownChecks.is_administrator(member)
        )

    @staticmethod
    def is_normal_moderator(member: Member) -> bool:
        return (
            member_has_role(member, 368799288127520769)
            or TheoTownChecks.is_senior_moderator(member)
        )

    @staticmethod
    def is_junior_moderator(member: Member) -> bool:
        return (
            member_has_role(member, 410512375083565066)
            or TheoTownChecks.is_normal_moderator(member)
        )

    @staticmethod
    def is_event_voter(member: Member) -> bool:
        return member_has_role(member, 647443361627766804)

    @staticmethod
    def is_event_manager(member: Member) -> bool:
        return member_has_role(member, 584109249903198210)

    @staticmethod
    def can_use_purge(member: Member) -> bool:
        return TheoTownChecks.is_normal_moderator(member) or TheoTownChecks.is_event_manager(member)

    @staticmethod
    def is_developer(user: Union[Member, User]) -> bool:
        return user.id in THEOTOWN_DEVELOPERS


def is_guild_administrator(guild: Guild, channel: GuildChannel, member: DiscordUser):
    if get(guild.members, id=member.id):
        assert isinstance(member, Member)
        if is_guild_theotown(guild):
            return TheoTownChecks.is_administrator(member)
        return (
            has_permission(channel, member, 'administrator')
            or has_permission(channel, member, 'manage_guild')
        )
    return False

def is_guild_moderator(guild: Guild, channel: AllChannels, member: DiscordUser):
    if get(guild.members, id=member.id):
        assert isinstance(member, Member)
        if is_guild_theotown(guild):
            return (
                TheoTownChecks.is_administrator(member)
                or TheoTownChecks.is_senior_moderator(member)
                or TheoTownChecks.is_normal_moderator(member)
                or TheoTownChecks.is_junior_moderator(member)
            )
        return (
            has_permission(channel, member, 'kick_members')
            or has_permission(channel, member, 'ban_members')
        )
    return False

def has_moderator_permissions(ctx: Context, **perms):
    if is_guild_theotown(ctx.guild):
        return TheoTownChecks.is_junior_moderator(ctx.author)

    # Ugly, I don't care
    try:
        return check_permissions(ctx, **perms)
    except MissingPermissions:
        return False

def can_modify_tags(ctx: Context) -> bool:
    """Returns true whether user can modify guild tags.

    It first checks if public can edit tags, if it can't
    it will resolve to moderators with manage_messages permission."""
    client: Pidroid = ctx.bot
    conf = client.get_guild_configuration(ctx.guild.id)
    if conf:
        if conf.public_tags:
            return True
    return has_moderator_permissions(ctx, manage_messages=True)

def check_junior_moderator_permissions(ctx: Context, **perms):
    if is_guild_theotown(ctx.guild):
        if not TheoTownChecks.is_junior_moderator(ctx.author):
            raise MissingUserPermissions('You need to be at least a junior moderator to run this command!')
        return True
    return check_permissions(ctx, **perms)

def check_normal_moderator_permissions(ctx: Context, **perms):
    if is_guild_theotown(ctx.guild):
        if not TheoTownChecks.is_normal_moderator(ctx.author):
            raise MissingUserPermissions('You need to be at least a moderator to run this command!')
        return True
    return check_permissions(ctx, **perms)

def check_senior_moderator_permissions(ctx: Context, **perms):
    if is_guild_theotown(ctx.guild):
        if not TheoTownChecks.is_senior_moderator(ctx.author):
            raise MissingUserPermissions('You need to be at least a senior moderator to run this command!')
        return True
    return check_permissions(ctx, **perms)

def check_purge_permissions(ctx: Context, **perms):
    if is_guild_theotown(ctx.guild):
        if not TheoTownChecks.can_use_purge(ctx.author):
            raise MissingUserPermissions('You need to be at least a moderator or event organiser to run this command!')
        return True
    return check_permissions(ctx, **perms)
