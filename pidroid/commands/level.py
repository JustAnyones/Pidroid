from __future__ import annotations

from discord import Guild, app_commands, Role
from discord.ext import commands
from discord.ext.commands import Context
from discord.ext.commands.errors import BadArgument, BadUnionArgument, MemberNotFound, MissingRequiredArgument
from discord.utils import escape_markdown
from typing import override, Annotated

from pidroid.client import Pidroid
from pidroid.models.categories import LevelCategory
from pidroid.models.view import PaginatingView
from pidroid.services.error_handler import notify
from pidroid.utils.aliases import DiscordUser
from pidroid.utils.db.levels import UserLevels, COLOUR_BINDINGS
from pidroid.utils.embeds import PidroidEmbed, SuccessEmbed
from pidroid.utils.paginators import ListPageSource

class LeaderboardPaginator(ListPageSource):
    def __init__(self, data: list[UserLevels]):
        super().__init__(data, per_page=10)
        self.embed = PidroidEmbed(title='Leaderboard rankings')

    @override
    async def format_page(self, menu: PaginatingView, page: list[UserLevels]):
        assert isinstance(menu.ctx.bot, Pidroid)
        _ = self.embed.clear_fields()
        for i, info in enumerate(page):
            user = menu.ctx.bot.get_user(info.user_id)
            _ = self.embed.add_field(
                name=f"{(i + 1) + self.per_page * menu.current_page}. {user if user else info.user_id} (lvl. {info.level})",
                value=f'{info.total_xp:,} XP',
                inline=False
            )
        return self.embed

class LevelCommandCog(commands.Cog):
    """This class implements a cog for special bot owner only commands."""
    def __init__(self, client: Pidroid) -> None:
        super().__init__()
        self.client = client

    async def assert_system_enabled(self, guild: Guild):
        """Checks if the XP system is enabled in the specified guild.
        
        Raises BadArgument if system is not enabled."""
        info = await self.client.fetch_guild_configuration(guild.id)
        if not info.xp_system_active:
            raise BadArgument('XP system is not enabled in this server!')
        return

    @commands.hybrid_command(
        name="level",
        brief="Displays the member level rank.",
        usage="[user/member]",
        category=LevelCategory
    )
    @app_commands.describe(member="Member or user you to view rank of.")
    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    async def level_command(
        self,
        ctx: Context[Pidroid],
        member: Annotated[DiscordUser | None, DiscordUser] = None
    ):
        assert ctx.guild is not None
        await self.assert_system_enabled(ctx.guild)
        member = member or ctx.author
        info = await self.client.api.fetch_ranked_user_level_info(ctx.guild.id, member.id)
        if info is None:
            raise BadArgument('The specified member is not yet ranked!')

        embed = PidroidEmbed(title=f'{escape_markdown(str(member))} rank')
        avatar = member.avatar or member.default_avatar
        _ = embed.set_thumbnail(url=avatar.url)
        _ = embed.add_field(name='Level', value=info.level)
        async with self.client.api.session() as session:
            _ = embed.add_field(name='Rank', value=f'#{await info.calculate_rank(session):,}')       

        # Select the colour to use
        embed.colour = info.default_embed_colour
        if info.embed_colour:
            embed.colour = info.embed_colour

        _ = embed.add_field(
            name=f'Level progress ({info.current_xp:,} / {info.xp_to_next_level:,} XP)',
            value=f"{info.get_progress_bar()}", inline=False
        )

        return await ctx.reply(embed=embed)
        
    @level_command.error
    async def on_level_command_error(self, ctx: Context[Pidroid], error: Exception):
        if isinstance(error, BadUnionArgument):
            if error.param.name == "member":
                for _err in error.errors:
                    if isinstance(_err, MemberNotFound):
                        return await notify(ctx, str(_err))
        setattr(error, 'unhandled', True)

    @commands.hybrid_command(
        name='leaderboard',
        brief='Returns the server level leaderboard.',
        category=LevelCategory
    )
    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    async def leaderboard_command(self, ctx: Context[Pidroid]):
        assert ctx.guild is not None
        await self.assert_system_enabled(ctx.guild)
        levels = await self.client.api.fetch_guild_level_rankings(ctx.guild.id, limit=100)
        pages = PaginatingView(self.client, ctx, source=LeaderboardPaginator(levels))
        await pages.send()

    @commands.hybrid_group(
        name='rewards',
        brief='Returns the server level rewards.',
        category=LevelCategory,
        invoke_without_command=True,
        fallback='list'
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def rewards_command(self, ctx: Context[Pidroid]):
        if ctx.invoked_subcommand is None:
            assert ctx.guild is not None
            await self.assert_system_enabled(ctx.guild)
            conf = await self.client.fetch_guild_configuration(ctx.guild.id)
            rewards = await conf.fetch_all_level_rewards()
            if len(rewards) == 0:
                raise BadArgument('This server does not have any level rewards!')
            
            embed = PidroidEmbed(title='Server level rewards')
            embed.description = ""
            # TODO: ensure there is no overflow
            for reward in rewards:
                role = ctx.guild.get_role(reward.role_id)
                role_name = role.mention if role else reward.role_id
                assert isinstance(embed.description, str)
                embed.description += f"{reward.level}: {role_name}\n"
            return await ctx.reply(embed=embed)

    @rewards_command.command(
        name='add',
        brief='Adds the specified role as a level reward.',
        usage='<role> <level>',
        category=LevelCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def rewards_add_command(self, ctx: Context[Pidroid], role: Role, level: int):
        assert ctx.guild is not None
        await self.assert_system_enabled(ctx.guild)
        if level > 1000:
            raise BadArgument('You cannot set level requirement higher than 1000!')
        if level <= 0:
            raise BadArgument('You cannot set level requirement to be 0 or less.')

        reward = await self.client.api.fetch_guild_level_reward_by_level(ctx.guild.id, level)
        if reward is not None:
            raise BadArgument('A role reward already exists for the specified level.')

        reward = await self.client.api.fetch_level_reward_by_role(ctx.guild.id, role.id)
        if reward is not None:
            raise BadArgument('Specified role already belongs to a reward.')

        _ = await self.client.api.insert_level_reward(ctx.guild.id, role.id, level)
        return await ctx.reply(embed=SuccessEmbed(
            'Role reward added successfully! Please note that it will take some time for changes to take effect.'
        ))

    @rewards_add_command.error
    async def on_rewards_add_command_error(self, ctx: Context[Pidroid], error: Exception):
        if isinstance(error, MissingRequiredArgument):
            if error.param.name == "role":
                return await notify(ctx, "Please specify the role.")
            if error.param.name == "level":
                return await notify(ctx, "Please specify the level.")
        setattr(error, 'unhandled', True)

    @rewards_command.command(
        name='remove',
        brief='Removes the specified role as a level reward.',
        usage='<role>',
        category=LevelCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def rewards_remove_command(self, ctx: Context[Pidroid], role: Role):
        assert ctx.guild is not None
        await self.assert_system_enabled(ctx.guild)
        reward = await self.client.api.fetch_level_reward_by_role(ctx.guild.id, role.id)
        if reward is None:
            raise BadArgument('Specified role does not belong to any rewards.')

        await self.client.api.delete_level_reward(reward.id)
        return await ctx.reply(embed=PidroidEmbed.from_success(
            'Role reward removed successfully! Please note that it will take some time for changes to take effect.'
        ))

    @rewards_remove_command.error
    async def on_rewards_remove_command_error(self, ctx: Context[Pidroid], error: Exception):
        if isinstance(error, MissingRequiredArgument):
            if error.param.name == "role":
                return await notify(ctx, "Please specify the role.")
        setattr(error, 'unhandled', True)


    @commands.command(
        name="level-card",
        brief="Sets the custom level theme in the level card.",
        usage="<theme name>",
        category=LevelCategory,
        aliases=['rank-card']
    )
    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    async def level_card_command(self, ctx: Context[Pidroid], theme: str):
        assert ctx.guild is not None
        await self.assert_system_enabled(ctx.guild)
        info = await self.client.api.fetch_ranked_user_level_info(ctx.guild.id, ctx.author.id)
        if info is None:
            raise BadArgument("You are not yet ranked, I cannot set the theme.")
        
        cleaned_theme = theme.strip().lower()
        bindings = COLOUR_BINDINGS.get(cleaned_theme, None)
        if bindings is None:
            raise BadArgument(
                f"Specified theme does not exist. It must be one of {', '.join(COLOUR_BINDINGS.keys())}"
            )
        
        await self.client.api.update_user_level_theme(info.id, cleaned_theme)
        return await ctx.reply(embed=PidroidEmbed.from_success("Level card theme has been updated."))

    @level_card_command.error
    async def on_level_card_command_error(self, ctx: Context[Pidroid], error: Exception):
        if isinstance(error, MissingRequiredArgument):
            if error.param.name == "theme":
                return await notify(ctx, "Please specify the theme you want to set.")
        setattr(error, 'unhandled', True)

async def setup(client: Pidroid) -> None:
    await client.add_cog(LevelCommandCog(client))
