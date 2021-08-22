from discord import Member, User, TextChannel, Guild, Client
from discord.ext.commands import MissingPermissions, Context
from discord.utils import get
from typing import Union

from constants import DEVELOPMENT_BOTS, THEOTOWN_DEVELOPERS, THEOTOWN_GUILD, JUSTANYONE_ID, PIDROID_ID, CHEESE_EATERS, BOT_COMMANDS_CHANNEL
from client import Pidroid
from cogs.models.exceptions import MissingUserPermissions

# Generic permission check functions
def member_has_role(member: Member, role_id: int):
    return get(member.guild.roles, id=role_id) in member.roles

def member_has_permission(channel: TextChannel, member: Member, permission: str):
    return getattr(channel.permissions_for(member), permission)

def member_has_guild_permission(member: Member, permission: str):
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

def check_guild_permissions(ctx: Context, **perms):
    permissions = ctx.author.guild_permissions

    missing = [perm for perm, value in perms.items() if getattr(permissions, perm) != value]

    if missing:
        raise MissingPermissions(missing)
    return True

def is_valid_duration(duration):
    if is_number(duration):
        return int(duration) > 0
    return False

def is_number(string: str):
    """Checks whether specified string is a number."""
    try:
        int(string)
        return True
    except ValueError:
        return False


def is_justanyone(user: Union[Member, User]):
    return user.id == JUSTANYONE_ID

def is_client_development(client: Pidroid):
    return client.user.id in DEVELOPMENT_BOTS

def is_client_pidroid(client: Client):
    return client.user.id == PIDROID_ID

def client_is_pidroid(user: User):
    return user.id == PIDROID_ID

def is_theotown_developer(user: User):
    return user.id in THEOTOWN_DEVELOPERS

def is_theotown_guild(guild: Guild):
    return guild.id == THEOTOWN_GUILD

def is_event_voter(member: Member):
    return member_has_role(member, 647443361627766804)

def is_event_manager(member: Member):
    return member_has_role(member, 584109249903198210)


def can_purge(member: Member):
    return is_normal_moderator(member) or is_event_manager(member)

async def guild_has_configuration(client: Pidroid, guild: Guild):
    return await client.api.get_guild_configuration(guild.id) is not None


def is_administrator(member: Member):
    return (
        is_justanyone(member)
        or member_has_role(member, 415194893917356052)  # City Council
        or member_has_role(member, 365482773206532096)  # Mayor
        or member_has_role(member, 710914534394560544)  # Elder
    )

def is_senior_moderator(member: Member):
    return (
        member_has_role(member, 381899421992091669)
        or is_administrator(member)
    )

def is_normal_moderator(member: Member):
    return (
        member_has_role(member, 368799288127520769)
        or is_senior_moderator(member)
    )

def is_junior_moderator(member: Member):
    return (
        member_has_role(member, 410512375083565066)
        or is_normal_moderator(member)
    )

def is_guild_administrator(guild: Guild, channel: TextChannel, member: Member):
    member = guild.get_member(member.id)
    if member is not None:
        if member in guild.members:
            if is_theotown_guild(guild):
                return is_administrator(member)
            return (
                member_has_permission(channel, member, 'administrator')
                or member_has_permission(channel, member, 'manage_guild')
            )
    return False

def is_guild_moderator(guild: Guild, channel: TextChannel, member: Member):
    member = guild.get_member(member.id)
    if member is not None:
        if member in guild.members:
            if is_theotown_guild(guild):
                return (
                    is_administrator(member)
                    or is_senior_moderator(member)
                    or is_normal_moderator(member)
                    or is_junior_moderator(member)
                )
            return (
                member_has_permission(channel, member, 'kick_members')
                or member_has_permission(channel, member, 'ban_members')
            )
    return False


def is_cheese_consumer(user):
    return user.id in CHEESE_EATERS

def is_bot_commands(channel):
    return channel.id == BOT_COMMANDS_CHANNEL


def check_junior_moderator_permissions(ctx: Context, **perms):
    if is_theotown_guild(ctx.guild):
        if not is_junior_moderator(ctx.author):
            raise MissingUserPermissions('You need to be at least a junior moderator to run this command!')
        return True
    return check_permissions(ctx, **perms)

def check_normal_moderator_permissions(ctx: Context, **perms):
    if is_theotown_guild(ctx.guild):
        if not is_normal_moderator(ctx.author):
            raise MissingUserPermissions('You need to be at least a moderator to run this command!')
        return True
    return check_permissions(ctx, **perms)

def check_senior_moderator_permissions(ctx: Context, **perms):
    if is_theotown_guild(ctx.guild):
        if not is_senior_moderator(ctx.author):
            raise MissingUserPermissions('You need to be at least a senior moderator to run this command!')
        return True
    return check_permissions(ctx, **perms)


def setup(client):
    pass

def teardown(client):
    pass
