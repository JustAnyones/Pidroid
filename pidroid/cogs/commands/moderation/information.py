from discord import app_commands
from discord.ext import commands
from discord.ext.commands.context import Context # type: ignore
from discord.member import Member
from discord.user import User
from typing import Optional, Union
from typing_extensions import Annotated

from pidroid.client import Pidroid
from pidroid.models.categories import ModerationCategory
from pidroid.models.exceptions import GeneralCommandError
from pidroid.utils.checks import check_junior_moderator_permissions, check_normal_moderator_permissions
from pidroid.utils.decorators import command_checks
from pidroid.utils.embeds import PidroidEmbed, SuccessEmbed
from pidroid.utils.paginators import PidroidPages, CasePaginator


class ModeratorInfoCommands(commands.Cog): # type: ignore
    """This class implements cog which contains commands for viewing and editing moderation logs and statistics."""

    def __init__(self, client: Pidroid):
        self.client = client

    @commands.hybrid_command(
        name="case",
        brief="Displays details for the specified case.\n Cases can be modified by providing a reason argument.",
        usage="<case ID> [reason]",
        category=ModerationCategory
    )
    @app_commands.rename()
    @app_commands.describe(case_id="Numerical case ID.", reason="Updated case reason.")
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.is_junior_moderator(kick_members=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def case_command(self, ctx: Context, case_id: int, *, reason: Optional[str]):
        assert ctx.guild is not None
        case = await self.client.fetch_case(ctx.guild.id, case_id)

        if reason is not None:
            check_normal_moderator_permissions(ctx, kick_members=True)
            await case.update_reason(reason)
            return await ctx.reply("Case details updated successfully!")
        await ctx.reply(embed=case.to_embed())


    @commands.hybrid_command(
        name="invalidate-warning",
        brief="Invalidates a specified warning.",
        usage="<case ID>",
        aliases=['invalidate-warn', 'invalidatewarn', 'invalidatewarning'],
        category=ModerationCategory
    )
    @app_commands.rename()
    @app_commands.describe(case_id="Numerical case ID.")
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.is_senior_moderator(manage_guild=True)
    @commands.guild_only() # type: ignore
    async def invalidate_warning_command(self, ctx: Context, case_id: int):
        assert ctx.guild is not None
        case = await self.client.fetch_case(ctx.guild.id, case_id)
        await case.invalidate()
        await ctx.reply(embed=SuccessEmbed('Warning invalidated successfully!'))


    # Originally hidden due to limitation, now hidden due to making warnings subcommand explicit
    @commands.hybrid_group( # type: ignore
        name="warnings",
        hidden=True
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def warnings_command(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            raise GeneralCommandError("You have to explicitly mention whether you want to display active or all warnings!")

    @warnings_command.command( # type: ignore
        name="active",
        brief="Displays active warnings for the specified user.",
        usage="[user]",
        category=ModerationCategory
    )
    @app_commands.describe(user="Member or user you are trying to query.")
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def warnings_active_command(
        self,
        ctx: Context,
        user: Annotated[Optional[Union[Member, User]], Union[Member, User]] = None
    ):
        assert ctx.guild is not None
        user = user or ctx.author

        error_msg = "I could not find any warnings for you!"
        if user.id != ctx.author.id:
            check_junior_moderator_permissions(ctx, kick_members=True)
            error_msg = "Specified user has no warnings."
        
        warnings = await self.client.fetch_active_warnings(ctx.guild.id, user.id)
        if len(warnings) == 0:
            raise GeneralCommandError(error_msg)

        pages = PidroidPages(
            source=CasePaginator(f"Displaying warnings for {str(user)}", warnings, True),
            ctx=ctx
        )
        await pages.start()

    @warnings_command.command( # type: ignore
        name="all",
        brief="Displays all warnings ever issued for the specified user.",
        usage="[user]",
        category=ModerationCategory
    )
    @app_commands.describe(user="Member or user you are trying to query.")
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def warnings_all_command(
        self,
        ctx: Context,
        user: Annotated[Optional[Union[Member, User]], Union[Member, User]] = None
    ):
        assert ctx.guild is not None
        user = user or ctx.author

        error_msg = "I could not find any warnings for you!"
        if user.id != ctx.author.id:
            check_junior_moderator_permissions(ctx, kick_members=True)
            error_msg = "Specified user has no warnings."
        
        warnings = await self.client.fetch_warnings(ctx.guild.id, user.id)
        if len(warnings) == 0:
            raise GeneralCommandError(error_msg)

        pages = PidroidPages(
            source=CasePaginator(f"Displaying warnings for {str(user)}", warnings, True),
            ctx=ctx
        )
        await pages.start()


    @commands.hybrid_command( # type: ignore
        name="modlogs",
        brief='Displays all moderation logs for the specified user.',
        usage='[user]',
        category=ModerationCategory
    )
    @app_commands.describe(user="Member or user you are trying to query.")
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def moderation_logs_command(
        self,
        ctx: Context,
        user: Annotated[Optional[Union[Member, User]], Union[Member, User]] = None
    ):
        assert ctx.guild is not None
        user = user or ctx.author

        error_msg = "I could not find any modlogs related to you!"
        if user.id != ctx.author.id:
            check_junior_moderator_permissions(ctx, kick_members=True)
            error_msg = "Specified user has no modlogs!"

        cases = await self.client.fetch_cases(ctx.guild.id, user.id)
        if len(cases) == 0:
            raise GeneralCommandError(error_msg)

        pages = PidroidPages(
            source=CasePaginator(f"Displaying moderation logs for {str(user)}", cases),
            ctx=ctx
        )
        await pages.start()


    @commands.hybrid_command(
        name="modstats",
        brief="Displays moderation statistics of the specified member.",
        usage="[member]",
        category=ModerationCategory
    )
    @app_commands.describe(user="Member you are trying to query.")
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.is_junior_moderator(kick_members=True)
    @commands.guild_only() # type: ignore
    async def moderator_statistics_command(
        self,
        ctx: Context,
        user: Annotated[Optional[Member], Member] = None
    ):
        assert ctx.guild is not None
        member = user or ctx.author
        data = await self.client.api.fetch_moderation_statistics(ctx.guild.id, member.id)
        embed = PidroidEmbed(title=f'Displaying moderation statistics for {str(member)}')
        embed.add_field(name='Bans', value=data["bans"])
        embed.add_field(name='Kicks', value=data["kicks"])
        embed.add_field(name='Jails', value=data["jails"])
        embed.add_field(name='Warnings', value=data["warnings"])
        embed.add_field(name='Moderator total', value=data["user_total"])
        embed.add_field(name='Server total', value=data["guild_total"])
        await ctx.reply(embed=embed)


async def setup(client: Pidroid):
    await client.add_cog(ModeratorInfoCommands(client))
