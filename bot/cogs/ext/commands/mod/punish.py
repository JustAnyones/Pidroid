import discord
import typing

from discord.errors import HTTPException
from discord.ext import commands
from discord.ext.commands.context import Context # type: ignore
from typing import Optional

from client import Pidroid
from cogs.models.case import Ban, Kick, Mute, Jail, Warning
from cogs.models.categories import ModerationCategory
from cogs.utils.converters import Duration, MemberOffender, UserOffender
from cogs.utils.decorators import command_checks
from cogs.utils.embeds import error, success
from cogs.utils.getters import get_role, get_channel
from cogs.utils.time import datetime_to_duration

async def is_banned(ctx: Context, user: typing.Union[discord.Member, discord.User]) -> bool:
    """Returns true if user is in guild's ban list."""
    bans = await ctx.guild.bans()
    for entry in bans:
        if entry.user.id == user.id:
            return True
    return False

class ModeratorCommands(commands.Cog):
    """This class implements cog which contains commands for moderation."""

    def __init__(self, client: Pidroid):
        self.client = client
        self.api = self.client.api

    @commands.command(
        brief='Removes a specified amount of messages from the channel.',
        usage='<amount>',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True)
    @command_checks.can_purge()
    @commands.guild_only()
    async def purge(self, ctx: Context, amount: int = 0):
        if amount <= 0:
            return await ctx.reply(embed=error(
                "Please specify an amount of messages to delete!"
            ))

        # Evan proof
        if amount > 1000:
            amount = 1000

        await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f'{amount} messages have been purged!', delete_after=1.5)

    @commands.command(hidden=True)
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, attach_files=True)
    @command_checks.is_junior_moderator(manage_messages=True)
    @commands.guild_only()
    async def deletethis(self, ctx: Context):
        await ctx.message.delete(delay=0)
        await ctx.channel.purge(limit=1)
        await ctx.send(file=discord.File('./resources/delete_this.png'))

    @commands.command(
        brief='Issues a warning to specified member.',
        usage='<member> <warning>',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True)
    @command_checks.is_junior_moderator(kick_members=True)
    @commands.guild_only()
    async def warn(self, ctx: Context, member: MemberOffender, *, warning: str):
        w = Warning(ctx, member)
        await w.issue(warning)
        await ctx.message.delete(delay=0)

    @commands.command(
        brief='Mutes specified member for the specified amount of time and a reason.',
        usage='<member> [duration] [reason]',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, manage_roles=True)
    @command_checks.is_junior_moderator(kick_members=True)
    @command_checks.guild_configuration_exists()
    @commands.guild_only()
    async def mute(self, ctx: Context, member: MemberOffender, duration_datetime: typing.Optional[Duration] = None, *, reason: str = None):
        if not self.client.guild_config_cache_ready:
            return

        c = self.client.get_guild_configuration(ctx.guild.id)
        role = get_role(ctx.guild, c.mute_role)
        if role is None:
            return await ctx.reply(embed=error("Mute role not found!"))

        if discord.utils.get(ctx.guild.roles, id=role.id) in member.roles:
            return await ctx.reply(embed=error("The user is already muted!"))

        m = Mute(ctx, member)
        if duration_datetime is None:
            await m.issue(role, reason=reason)
            return await ctx.message.delete(delay=0)

        if datetime_to_duration(duration_datetime) < 30:
            return await ctx.reply(embed=error(
                'The duration for the mute is too short! Make sure it\'s at least 30 seconds long.'
            ))
        m.length = int(duration_datetime.timestamp())
        await m.issue(role, reason=reason)
        await ctx.message.delete(delay=0)

    @commands.command(
        brief='Unmutes specified member.',
        usage='<member>',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, manage_roles=True)
    @command_checks.is_junior_moderator(kick_members=True)
    @command_checks.guild_configuration_exists()
    @commands.guild_only()
    async def unmute(self, ctx: Context, *, member: MemberOffender):
        if not self.client.guild_config_cache_ready:
            return

        c = self.client.get_guild_configuration(ctx.guild.id)
        role = get_role(ctx.guild, c.mute_role)
        if role is None:
            return await ctx.reply(embed=error("Mute role not found, cannot remove!"))

        if discord.utils.get(ctx.guild.roles, id=role.id) not in member.roles:
            return await ctx.reply(embed=error("The user is not muted!"))

        m = Mute(ctx, member)
        await m.revoke(role)
        await ctx.message.delete(delay=0)

    @commands.command(
        brief='Throws specified member in jail.',
        usage='<member> [reason]',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, manage_roles=True)
    @command_checks.is_junior_moderator(kick_members=True)
    @command_checks.guild_configuration_exists()
    @commands.guild_only()
    async def jail(self, ctx: Context, member: MemberOffender, *, reason: str = None):
        if not self.client.guild_config_cache_ready:
            return

        c = self.client.get_guild_configuration(ctx.guild.id)
        role = get_role(ctx.guild, c.jail_role)
        if role is None:
            return await ctx.reply(embed=error("Jail role not found!"))

        channel = get_channel(ctx.guild, c.jail_channel)
        if channel is None:
            return await ctx.reply(embed=error("Jail channel not found!"))

        if discord.utils.get(ctx.guild.roles, id=role.id) in member.roles:
            return await ctx.reply(embed=error("The user is already jailed!"))

        j = Jail(ctx, member)
        await j.issue(role, reason)
        await ctx.message.delete(delay=0)

    @commands.command(
        brief='Throws specified member in jail.',
        usage='<member> [reason]',
        aliases=['van'],
        category=ModerationCategory,
        hidden=True
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, manage_roles=True)
    @command_checks.is_junior_moderator(kick_members=True)
    @command_checks.guild_configuration_exists()
    @commands.guild_only()
    async def kidnap(self, ctx: Context, member: MemberOffender, *, reason: str = None):
        if not self.client.guild_config_cache_ready:
            return

        c = self.client.get_guild_configuration(ctx.guild.id)
        role = get_role(ctx.guild, c.jail_role)
        if role is None:
            return await ctx.reply(embed=error("Jail role not found!"))

        channel = get_channel(ctx.guild, c.jail_channel)
        if channel is None:
            return await ctx.reply(embed=error("Jail channel not found!"))

        if discord.utils.get(ctx.guild.roles, id=role.id) in member.roles:
            return await ctx.reply(embed=error("The user is already kidnapped, don't you remember?"))

        j = Jail(ctx, member)
        await j.issue(role, reason, True)
        await ctx.message.delete(delay=0)

    @commands.command(
        brief='Releases specified member from jail.',
        usage='<member>',
        aliases=["release"],
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, manage_roles=True)
    @command_checks.is_junior_moderator(kick_members=True)
    @command_checks.guild_configuration_exists()
    @commands.guild_only()
    async def unjail(self, ctx: Context, *, member: MemberOffender):
        if not self.client.guild_config_cache_ready:
            return

        c = self.client.get_guild_configuration(ctx.guild.id)
        role = get_role(ctx.guild, c.jail_role)
        if role is None:
            return await ctx.reply(embed=error("Jail role not found, cannot remove!"))

        if discord.utils.get(ctx.guild.roles, id=role.id) not in member.roles:
            return await ctx.reply(embed=error("The user is not in jail!"))

        j = Jail(ctx, member)
        await j.revoke(role)
        await ctx.message.delete(delay=0)

    @commands.command(
        brief='Kicks the specified member for specified reason.',
        usage='<member> [reason]',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, kick_members=True)
    @command_checks.is_junior_moderator(kick_members=True)
    @commands.guild_only()
    async def kick(self, ctx: Context, member: MemberOffender, *, reason: str = None):
        k = Kick(ctx, member)
        await k.issue(reason)
        await ctx.message.delete(delay=0)

    @commands.command(
        brief='Bans the specified user for specified reason for the specified amount of time.',
        usage='<user> [duration] [reason]',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, ban_members=True)
    @command_checks.is_moderator(ban_members=True)
    @commands.guild_only()
    async def ban(self, ctx: Context, user: UserOffender, duration_datetime: Optional[Duration] = None, *, reason: str = None):
        if await is_banned(ctx, user):
            return await ctx.reply(embed=error("Specified user is already banned!"))

        b = Ban(ctx, user)
        if duration_datetime is None:
            await b.issue(reason=reason)
        else:
            if datetime_to_duration(duration_datetime) < 60:
                return await ctx.reply(embed=error('The duration for the ban is too short! Make sure it\'s at least a minute long.'))
            b.length = int(duration_datetime.timestamp())
            await b.issue(reason=reason)
        await ctx.message.delete(delay=0)

    @commands.command(
        brief='Unbans the specified user.',
        usage='<user ID>',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, ban_members=True)
    @command_checks.is_senior_moderator(administrator=True)
    @commands.guild_only()
    async def unban(self, ctx: Context, *, user: Optional[discord.User]):
        if user is None:
            return await ctx.reply(embed=error("Please specify someone you are trying to unban!"))

        try:
            await ctx.guild.unban(user)
            await ctx.reply(embed=success(f"{str(user)} has been unbanned!"))
        except HTTPException:
            await ctx.reply(embed=error("Specified user could not be unbanned! Perhaps the user is already unbanned?"))


def setup(client: Pidroid):
    client.add_cog(ModeratorCommands(client))
