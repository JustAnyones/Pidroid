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
from cogs.utils.embeds import SuccessEmbed, ErrorEmbed
from cogs.utils.getters import get_role, get_channel
from cogs.utils.time import datetime_to_duration

async def is_banned(ctx: Context, user: typing.Union[discord.Member, discord.User]) -> bool:
    """Returns true if user is in guild's ban list."""
    try:
        await ctx.guild.fetch_ban(user)
        return True
    except Exception:
        return False

class OldModeratorCommands(commands.Cog): # type: ignore
    """This class implements cog which contains commands for moderation."""

    def __init__(self, client: Pidroid):
        self.client = client

    @commands.command( # type: ignore
        brief='DEPRECATED: Issues a warning to specified member.',
        usage='<member> <warning>',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True) # type: ignore
    @command_checks.is_junior_moderator(kick_members=True)
    @commands.guild_only() # type: ignore
    async def warn(self, ctx: Context, member: MemberOffender, *, warning: str):
        w = Warning(ctx, member)
        w.reason = warning
        await w.issue()
        await ctx.message.delete(delay=0)

    @commands.command( # type: ignore
        brief='DEPRECATED: Unmutes specified member.',
        usage='<member>',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, manage_roles=True) # type: ignore
    @command_checks.is_junior_moderator(kick_members=True)
    @command_checks.guild_configuration_exists()
    @commands.guild_only() # type: ignore
    async def unmute(self, ctx: Context, *, member: MemberOffender):
        c = self.client.get_guild_configuration(ctx.guild.id)
        assert c is not None

        role = get_role(ctx.guild, c.mute_role)
        if role is None:
            return await ctx.reply(embed=ErrorEmbed("Mute role not found, cannot remove!"))

        if discord.utils.get(ctx.guild.roles, id=role.id) not in member.roles:
            return await ctx.reply(embed=ErrorEmbed("The user is not muted!"))

        m = Mute(ctx, member)
        await m.revoke(role)
        await ctx.message.delete(delay=0)

    @commands.command( # type: ignore
        brief='DEPRECATED: Throws specified member in jail.',
        usage='<member> [reason]',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, manage_roles=True) # type: ignore
    @command_checks.is_junior_moderator(kick_members=True)
    @command_checks.guild_configuration_exists()
    @commands.guild_only() # type: ignore
    async def jail(self, ctx: Context, member: MemberOffender, *, reason: str = None):
        c = self.client.get_guild_configuration(ctx.guild.id)
        assert c is not None

        role = get_role(ctx.guild, c.jail_role)
        if role is None:
            return await ctx.reply(embed=ErrorEmbed("Jail role not found!"))

        channel = get_channel(ctx.guild, c.jail_channel)
        if channel is None:
            return await ctx.reply(embed=ErrorEmbed("Jail channel not found!"))

        if discord.utils.get(ctx.guild.roles, id=role.id) in member.roles:
            return await ctx.reply(embed=ErrorEmbed("The user is already jailed!"))

        j = Jail(ctx, member)
        j.reason = reason
        await j.issue(role)
        await ctx.message.delete(delay=0)

    @commands.command( # type: ignore
        brief='DEPRECATED: Throws specified member in jail.',
        usage='<member> [reason]',
        aliases=['van'],
        category=ModerationCategory,
        hidden=True
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, manage_roles=True) # type: ignore
    @command_checks.is_junior_moderator(kick_members=True)
    @command_checks.guild_configuration_exists()
    @commands.guild_only() # type: ignore
    async def kidnap(self, ctx: Context, member: MemberOffender, *, reason: str = None):
        c = self.client.get_guild_configuration(ctx.guild.id)
        assert c is not None

        role = get_role(ctx.guild, c.jail_role)
        if role is None:
            return await ctx.reply(embed=ErrorEmbed("Jail role not found!"))

        channel = get_channel(ctx.guild, c.jail_channel)
        if channel is None:
            return await ctx.reply(embed=ErrorEmbed("Jail channel not found!"))

        if discord.utils.get(ctx.guild.roles, id=role.id) in member.roles:
            return await ctx.reply(embed=ErrorEmbed("The user is already kidnapped, don't you remember?"))

        j = Jail(ctx, member)
        j.reason = reason
        await j.issue(role, True)
        await ctx.message.delete(delay=0)

    @commands.command( # type: ignore
        brief='DEPRECATED: Releases specified member from jail.',
        usage='<member>',
        aliases=["release"],
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, manage_roles=True) # type: ignore
    @command_checks.is_junior_moderator(kick_members=True)
    @command_checks.guild_configuration_exists()
    @commands.guild_only() # type: ignore
    async def unjail(self, ctx: Context, *, member: MemberOffender):
        c = self.client.get_guild_configuration(ctx.guild.id)
        assert c is not None

        role = get_role(ctx.guild, c.jail_role)
        if role is None:
            return await ctx.reply(embed=ErrorEmbed("Jail role not found, cannot remove!"))

        if discord.utils.get(ctx.guild.roles, id=role.id) not in member.roles:
            return await ctx.reply(embed=ErrorEmbed("The user is not in jail!"))

        j = Jail(ctx, member)
        await j.revoke(role, f"Released by {str(ctx.author)}")
        await ctx.message.delete(delay=0)

    @commands.command( # type: ignore
        brief='DEPRECATED: Kicks the specified member for specified reason.',
        usage='<member> [reason]',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, kick_members=True) # type: ignore
    @command_checks.is_junior_moderator(kick_members=True)
    @commands.guild_only() # type: ignore
    async def kick(self, ctx: Context, member: MemberOffender, *, reason: str = None):
        k = Kick(ctx, member)
        k.reason = reason
        await k.issue()
        await ctx.message.delete(delay=0)

    @commands.command( # type: ignore
        brief='DEPRECATED: Bans the specified user for specified reason for the specified amount of time.',
        usage='<user> [duration] [reason]',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, ban_members=True) # type: ignore
    @command_checks.is_moderator(ban_members=True)
    @commands.guild_only() # type: ignore
    async def ban(self, ctx: Context, user: UserOffender, duration_datetime: Optional[Duration] = None, *, reason: str = None):
        if await is_banned(ctx, user):
            return await ctx.reply(embed=ErrorEmbed("Specified user is already banned!"))

        b = Ban(ctx, user)
        b.reason = reason
        if duration_datetime is not None:
            if datetime_to_duration(duration_datetime) < 60:
                return await ctx.reply(embed=ErrorEmbed('The duration for the ban is too short! Make sure it\'s at least a minute long.'))
            b.length = int(duration_datetime.timestamp())
        await b.issue()
        await ctx.message.delete(delay=0)

    @commands.command( # type: ignore
        brief='DEPRECATED: Unbans the specified user.',
        usage='<user ID>',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, ban_members=True) # type: ignore
    @command_checks.is_senior_moderator(administrator=True)
    @commands.guild_only() # type: ignore
    async def unban(self, ctx: Context, *, user: Optional[discord.User]):
        if user is None:
            return await ctx.reply(embed=ErrorEmbed("Please specify someone you are trying to unban!"))

        try:
            await ctx.guild.unban(user)
            await ctx.reply(embed=SuccessEmbed(f"{str(user)} has been unbanned!"))
        except HTTPException:
            await ctx.reply(embed=ErrorEmbed("Specified user could not be unbanned! Perhaps the user is already unbanned?"))


async def setup(client: Pidroid):
    await client.add_cog(OldModeratorCommands(client))
