import discord
import typing

from discord.errors import HTTPException
from discord.ext import commands
from discord.ext.commands.context import Context

from client import Pidroid
from cogs.models.categories import ModerationCategory
from cogs.models.punishments import Ban, Jail, Kidnap, Mute, Kick, Warn
from cogs.utils.converters import Duration, Offender
from cogs.utils.decorators import command_checks
from cogs.utils.embeds import error
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
        async with ctx.typing():
            if amount <= 0:
                await ctx.reply(embed=error(
                    "Please specify an amount of messages to delete!"
                ))
                return
            await ctx.channel.purge(limit=amount + 1)
            await ctx.send(f'{amount} messages have been purged!', delete_after=1.5)

    @commands.command(hidden=True)
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, attach_files=True)
    @command_checks.is_junior_moderator(manage_messages=True)
    @commands.guild_only()
    async def deletethis(self, ctx: Context):
        async with ctx.typing():
            await ctx.message.delete(delay=0)
            await ctx.channel.purge(limit=1)
            await ctx.reply(file=discord.File('./resources/delete_this.png'))

    @commands.command(
        brief='Issues a warning to specified member.',
        usage='<member> <warning>',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True)
    @command_checks.is_junior_moderator(kick_members=True)
    @commands.guild_only()
    async def warn(self, ctx: Context, member: str = None, *, warning: str):
        member = await Offender().convert(ctx, member, True)

        w = Warn(ctx, member, warning)
        await w.issue()
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
    async def mute(self, ctx: Context, member: str = None, duration_datetime: typing.Optional[Duration] = None, *, reason: str = None):
        member = await Offender().convert(ctx, member, True)

        c = await self.client.api.get_guild_configuration(ctx.guild.id)
        role = get_role(ctx.guild, c.get('mute_role', None))
        if role is None:
            await ctx.reply(embed=error("Mute role not found!"))
            return

        if discord.utils.get(ctx.guild.roles, id=role.id) in member.roles:
            await ctx.reply(embed=error("The user is already muted!"))
            return

        m = Mute(ctx, member, role, reason)
        if duration_datetime is None:
            await m.issue()
        else:
            if datetime_to_duration(duration_datetime) < 30:
                await ctx.reply(embed=error(
                    'The duration for the mute is too short! Make sure it\'s at least 30 seconds long.'
                ))
                return
            m.length = int(duration_datetime.timestamp())
            await m.issue()
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
    async def unmute(self, ctx: Context, *, member: str = None):
        member = await Offender().convert(ctx, member, True)

        c = await self.api.get_guild_configuration(ctx.guild.id)
        role = get_role(ctx.guild, c.get('mute_role', None))
        if role is None:
            await ctx.reply(embed=error("Mute role not found, cannot remove!"))
            return

        if discord.utils.get(ctx.guild.roles, id=role.id) not in member.roles:
            await ctx.reply(embed=error("The user is not muted!"))
            return

        m = Mute(ctx, member, role)
        await m.revoke()
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
    async def jail(self, ctx: Context, member: str = None, *, reason: str = None):
        member = await Offender().convert(ctx, member, True)

        c = await self.api.get_guild_configuration(ctx.guild.id)
        role = get_role(ctx.guild, c.get('jail_role', None))
        if role is None:
            await ctx.reply(embed=error("Jail role not found!"))
            return

        channel = get_channel(ctx.guild, c.get('jail_channel', None))
        if channel is None:
            await ctx.reply(embed=error("Jail channel not found!"))
            return

        if discord.utils.get(ctx.guild.roles, id=role.id) in member.roles:
            await ctx.reply(embed=error("The user is already jailed!"))
            return

        j = Jail(ctx, member, role, reason)
        await j.issue()
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
    async def kidnap(self, ctx: Context, member: str = None, *, reason: str = None):
        member = await Offender().convert(ctx, member, True)

        c = await self.api.get_guild_configuration(ctx.guild.id)
        role = get_role(ctx.guild, c.get('jail_role', None))
        if role is None:
            await ctx.reply(embed=error("Jail role not found!"))
            return

        channel = get_channel(ctx.guild, c.get('jail_channel', None))
        if channel is None:
            await ctx.reply(embed=error("Jail channel not found!"))
            return

        if discord.utils.get(ctx.guild.roles, id=role.id) in member.roles:
            await ctx.reply(embed=error("The user is already kidnapped, don't you remember?"))
            return

        j = Kidnap(ctx, member, role, reason)
        await j.issue()
        await ctx.message.delete(delay=0)

    @commands.command(
        brief='Releases specified member from jail.',
        usage='<member>',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, manage_roles=True)
    @command_checks.is_junior_moderator(kick_members=True)
    @command_checks.guild_configuration_exists()
    @commands.guild_only()
    async def unjail(self, ctx: Context, *, member: str = None):
        member = await Offender().convert(ctx, member, True)

        c = await self.api.get_guild_configuration(ctx.guild.id)
        role = get_role(ctx.guild, c.get('jail_role', None))
        if role is None:
            await ctx.reply(embed=error("Jail role not found, cannot remove!"))
            return

        if discord.utils.get(ctx.guild.roles, id=role.id) not in member.roles:
            await ctx.reply(embed=error("The user is not in jail!"))
            return

        j = Jail(ctx, member, role)
        await j.revoke()
        await ctx.message.delete(delay=0)

    @commands.command(
        brief='Kicks the specified member for specified reason.',
        usage='<member> [reason]',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, kick_members=True)
    @command_checks.is_junior_moderator(kick_members=True)
    @commands.guild_only()
    async def kick(self, ctx: Context, member: str = None, *, reason: str = None):
        member = await Offender().convert(ctx, member, True)

        k = Kick(ctx, member, reason)
        await k.issue()
        await ctx.message.delete(delay=0)

    @commands.command(
        brief='Bans the specified user for specified reason for the specified amount of time.',
        usage='<user> [duration] [reason]',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, ban_members=True)
    @command_checks.is_moderator(ban_members=True)
    @commands.guild_only()
    async def ban(self, ctx: Context, user: str = None, duration_datetime: typing.Optional[Duration] = None, *, reason: str = None):
        user = await Offender().convert(ctx, user)

        if await is_banned(ctx, user):
            await ctx.reply(embed=error("Specified user is already banned!"))

        b = Ban(ctx, user, reason)
        if duration_datetime is None:
            await b.issue()
        else:
            if datetime_to_duration(duration_datetime) < 60:
                await ctx.reply(embed=error('The duration for the ban is too short! Make sure it\'s at least a minute long.'))
                return
            b.length = int(duration_datetime.timestamp())
            await b.issue()
        await ctx.message.delete(delay=0)

    @commands.command(
        brief='Unbans the specified user.',
        usage='<user ID>',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, ban_members=True)
    @command_checks.is_senior_moderator(administrator=True)
    @commands.guild_only()
    async def unban(self, ctx: Context, *, user: discord.User = None):
        if user is None:
            await ctx.reply(embed=error("Please specify someone you are trying to unban!"))
            return

        try:
            await ctx.guild.unban(user)
            await ctx.reply(f"{str(user)} has been unbanned!")
        except HTTPException:
            await ctx.reply(embed=error("Specified user could not be unbanned! Perhaps the user is already unbanned?"))


def setup(client):
    client.add_cog(ModeratorCommands(client))
