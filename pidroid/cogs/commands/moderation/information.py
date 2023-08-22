from discord import app_commands, Member, User, Guild
from discord.ext import commands
from discord.ext.commands import BadArgument, Context
from typing import Optional, Union, List
from typing_extensions import Annotated

from pidroid.client import Pidroid
from pidroid.models.categories import ModerationCategory
from pidroid.models.exceptions import GeneralCommandError
from pidroid.models.view import PaginatingView
from pidroid.utils.checks import check_junior_moderator_permissions, check_normal_moderator_permissions
from pidroid.utils.decorators import command_checks
from pidroid.utils.embeds import PidroidEmbed, SuccessEmbed
from pidroid.utils.paginators import CasePaginator, ListPageSource


class GuildPaginator(ListPageSource):
    def __init__(self, title: str, data: List[Guild]):
        super().__init__(data, per_page=20)
        self.embed = PidroidEmbed(title=title)
        self.embed.set_footer(text=f"{len(data)} servers")

    async def format_page(self, menu: PaginatingView, data: List[Guild]):
        offset = menu.current_page * self.per_page + 1
        values = ""
        for i, guild in enumerate(data):
            values += f"{i + offset}. {guild.name} by {guild.owner} (ID: {guild.id})\n"
        self.embed.description = values.strip()
        return self.embed

class ModeratorInfoCommands(commands.Cog):
    """This class implements cog which contains commands for viewing and editing moderation logs and statistics."""

    def __init__(self, client: Pidroid):
        self.client = client

    async def find_guilds(self, user_id: int, argument: str) -> List[Guild]:
        """Attempts to resolve guild by specified argument.

        It only searches guilds where user was punished once
        for privacy reasons."""
        guilds = await self.client.api.fetch_guilds_user_was_punished_in(user_id)

        # Search by ID
        if argument.isdigit():
            argument_as_int = int(argument)
            for guild in guilds:
                if guild.id == argument_as_int:
                    return [guild]

        # If we didn't find by ID, search by name
        found = []
        for guild in guilds:
            if guild.name == argument:
                found.append(guild)

        return found

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

        pages = PaginatingView(
            self.client,
            ctx=ctx,
            source=CasePaginator(f"Displaying warnings for {str(user)}", warnings, compact=True),
        )
        await pages.send()

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

        pages = PaginatingView(
            self.client,
            ctx=ctx,
            source=CasePaginator(f"Displaying warnings for {str(user)}", warnings, compact=True),
        )
        await pages.send()


    @commands.hybrid_group( # type: ignore
        name="modlogs",
        brief='Displays all moderation logs for the specified user.',
        usage='[user]',
        fallback="user",
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

        pages = PaginatingView(
            self.client,
            ctx=ctx,
            source=CasePaginator(f"Displaying moderation logs for {str(user)}", cases),
        )
        await pages.send()

    @moderation_logs_command.command( # type: ignore
        name="server",
        brief='Displays all moderation logs for you in the specified server.',
        usage='[server]',
        category=ModerationCategory
    )
    @app_commands.rename(guild_argument="server")
    @app_commands.describe(guild_argument="Server ID or name to query your modlogs from.")
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def moderation_logs_guild_subcommand(
        self,
        ctx: Context,
        guild_argument: Optional[str]
    ):
        # If guild wasn't provided, list all guilds where user was punished it
        if guild_argument is None:
            guilds = await self.client.api.fetch_guilds_user_was_punished_in(ctx.author.id)
            pages = PaginatingView(
                self.client,
                ctx=ctx,
                source=GuildPaginator("Servers, in which you have been punished", guilds),
            )
            return await pages.send()


        guilds = await self.find_guilds(ctx.author.id, guild_argument)

        # If we found no guilds, explain the user
        if len(guilds) == 0:
            raise BadArgument(
                f"I could not find any servers that would match {guild_argument!r} where you were punished"
            )

        # If we found one guild, choose it
        if len(guilds) == 1:
            guild = guilds[0]

        # Otherwise, list all guilds that got matched
        else:
            pages = PaginatingView(
                self.client,
                ctx=ctx,
                source=GuildPaginator("Servers matching your search", guilds),
            )
            return await pages.send()

        cases = await self.client.fetch_cases(guild.id, ctx.author.id)
        if len(cases) == 0:
            raise GeneralCommandError(f"I could not find any modlogs related to you in the {guild.name} server!")

        pages = PaginatingView(
            self.client,
            ctx=ctx,
            source=CasePaginator(
                f"Displaying moderation logs in {guild.name}",
                cases,
                include_original_user_name=True
            ),
        )
        await pages.send()


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
        embed.add_field(name='Bans', value=f"{data['bans']:,}")
        embed.add_field(name='Kicks', value=f"{data['kicks']:,}")
        embed.add_field(name='Jails', value=f"{data['jails']:,}")
        embed.add_field(name='Warnings', value=f"{data['warnings']:,}")
        embed.add_field(name='Moderator total', value=f"{data['user_total']:,}")
        embed.add_field(name='Server total', value=f"{data['guild_total']:,}")
        await ctx.reply(embed=embed)


    @commands.hybrid_command(
        name="search-cases",
        brief="Returns user IDs of users who have previously been punished in the server by the specified username.",
        usage="<username>",
        category=ModerationCategory
    )
    @app_commands.describe(username="Username of the user that was previously punished.")
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.is_junior_moderator(kick_members=True)
    @commands.guild_only() # type: ignore
    async def search_cases_command(
        self,
        ctx: Context,
        username: str
    ):
        assert ctx.guild is not None

        if len(username) < 2:
            raise BadArgument("Username is too short to search. Make sure it's at least 2 characters long.")

        cases = await self.client.api._fetch_cases_by_username(ctx.guild.id, username)
        if len(cases) == 0:
            raise BadArgument("I could not find any cases that had the specified user as punished.")

        pages = PaginatingView(
            self.client,
            ctx=ctx,
            source=CasePaginator(
                f"Displaying cases matching '{username}' username", cases,
                include_original_user_name=True, compact=True
            ),
        )
        await pages.send()

async def setup(client: Pidroid):
    await client.add_cog(ModeratorInfoCommands(client))
