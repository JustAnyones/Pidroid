import discord
import typing

from discord.ext import commands
from discord.ext.commands.context import Context

from client import Pidroid
from cogs.models.categories import ModerationCategory
from cogs.utils.checks import check_junior_moderator_permissions
from cogs.utils.decorators import command_checks
from cogs.utils.embeds import build_embed, error
from cogs.utils.getters import get_all_warnings, get_case, get_modlogs, get_warnings
from cogs.utils.paginators import MenuPages, ModLogPaginator, WarningPaginator


class ModeratorInfoCommands(commands.Cog):
    """This class implements cog which contains commands for viewing and editing moderation logs and statistics."""

    def __init__(self, client: Pidroid):
        self.client = client
        self.api = self.client.api

    @commands.command(
        brief='Displays details for the specified case.\nCases can be modified by providing a reason parameter.',
        usage='<case ID> [reason]',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.is_junior_moderator(kick_members=True)
    @commands.guild_only()
    async def case(self, ctx: Context, case_id: str, *, reason: str = None):
        case = await get_case(ctx, case_id)

        if reason is not None:
            await case.update(reason)
            await ctx.reply("Case details updated successfully!")
            return

        await ctx.reply(embed=case.to_embed())

    @commands.command(
        name='invalidate-warning',
        brief='Invalidates specified warning.',
        usage='<case ID>',
        aliases=['invalidate-warn', 'invalidatewarn', 'invalidatewarning'],
        category=ModerationCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.is_senior_moderator(ban_members=True)
    @commands.guild_only()
    async def invalidatewarning(self, ctx: Context, case_id: str):
        case = await get_case(ctx, case_id)
        await case.invalidate()
        await ctx.reply('Warning invalidated successfully!')

    @commands.command(
        brief='Displays all active warnings for the specified user.',
        usage='[user] [all]',
        aliases=['warns'],
        category=ModerationCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def warnings(self, ctx: Context, user: typing.Union[discord.Member, discord.User] = None, amount: str = 'none'):
        user = user or ctx.author

        error_msg = "I could not find any warnings for you!"
        if user.id != ctx.author.id:
            check_junior_moderator_permissions(ctx, kick_members=True)
            error_msg = "Specified user has no warnings."

        if amount.lower() == 'all':
            warnings = await get_all_warnings(ctx, user)
        else:
            warnings = await get_warnings(ctx, user)

        if len(warnings) == 0:
            await ctx.reply(embed=error(error_msg))
            return

        pages = MenuPages(
            source=WarningPaginator(f"Displaying warnings for {str(user)}", warnings),
            clear_reactions_after=True
        )
        await pages.start(ctx)

    @commands.command(
        brief='Displays all moderation logs for the specified user.',
        usage='[user]',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def modlogs(self, ctx: Context, *, user: typing.Union[discord.Member, discord.User] = None):
        user = user or ctx.author

        error_msg = "I could not find any modlogs related to you!"
        if user.id != ctx.author.id:
            check_junior_moderator_permissions(ctx, kick_members=True)
            error_msg = "Specified user has no modlogs!"

        cases = await get_modlogs(ctx, user)

        if len(cases) == 0:
            await ctx.reply(embed=error(error_msg))
            return

        pages = MenuPages(
            source=ModLogPaginator(f"Displaying moderation logs for {str(user)}", cases),
            clear_reactions_after=True
        )
        await pages.start(ctx)

    @commands.command(
        brief='Displays moderation statistics for the specified member.',
        usage='[member]',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.is_junior_moderator(kick_members=True)
    @commands.guild_only()
    async def modstats(self, ctx: Context, *, member: discord.Member = None):
        member = member or ctx.author
        bans = kicks = jails = warnings = 0
        user_data, guild_total = await self.api.get_moderation_statistics(ctx.guild.id, member.id)
        user_total = len(user_data)
        for row in user_data:
            punishment = row['type']
            if punishment == 'ban': bans += 1         # noqa: E701
            if punishment == 'kick': kicks += 1       # noqa: E701
            if punishment == 'jail': jails += 1       # noqa: E701
            if punishment == 'warning': warnings += 1 # noqa: E701

        embed = build_embed(title=f'Displaying moderation statistics for {str(member)}')
        embed.add_field(name='Bans', value=bans)
        embed.add_field(name='Kicks', value=kicks)
        embed.add_field(name='Jails', value=jails)
        embed.add_field(name='Warns', value=warnings)
        embed.add_field(name='Total', value=user_total)
        embed.add_field(name='Guild total', value=guild_total)
        await ctx.reply(embed=embed)


def setup(client: Pidroid):
    client.add_cog(ModeratorInfoCommands(client))
