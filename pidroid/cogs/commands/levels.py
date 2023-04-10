from __future__ import annotations

from discord import Member, User, app_commands
from discord.utils import escape_markdown
from discord.ext import commands # type: ignore
from discord.ext.commands import Context
from discord.ext.commands.errors import BadArgument # type: ignore
from typing import List, Optional, Union
from typing_extensions import Annotated

from pidroid.client import Pidroid
from pidroid.models.categories import OwnerCategory
from pidroid.utils.embeds import PidroidEmbed
from pidroid.utils.levels import LevelInformation
from pidroid.utils.paginators import ListPageSource, PidroidPages

class LeaderboardPaginator(ListPageSource):
    def __init__(self, data: List[LevelInformation]):
        super().__init__(data, per_page=10)
        self.embed = PidroidEmbed(title='Leaderboard rankings')

    async def format_page(self, menu: PidroidPages, data: List[LevelInformation]):
        assert isinstance(menu.ctx.bot, Pidroid)
        self.embed.clear_fields()
        for info in data:
            self.embed.add_field(
                name=f"{info.rank}. {await menu.ctx.bot.get_or_fetch_user(info.user_id)} (lvl. {info.current_level})",
                value=f'{info.total_xp} XP',
                inline=False
            )
        return self.embed

    async def get_page(self, page_number):
        return await super().get_page(page_number)

class LevelCommands(commands.Cog): # type: ignore
    """This class implements a cog for special bot owner only commands."""
    def __init__(self, client: Pidroid) -> None:
        self.client = client

    @commands.hybrid_command( # type: ignore
        name="rank",
        brief="Displays the member level rank.",
        usage="[user/member]",
        category=OwnerCategory
    )
    @app_commands.describe(member="Member or user you to view rank of.")
    @commands.guild_only()
    @commands.bot_has_guild_permissions(send_messages=True)
    async def rank_command(
        self,
        ctx: Context,
        member: Annotated[Optional[Union[Member, User]], Union[Member, User]] = None
    ):
        assert ctx.guild is not None
        member = member or ctx.author
        info = await self.client.api.fetch_member_level_info(ctx.guild.id, member.id)
        if info is None:
            raise BadArgument('The specified member is not yet ranked!')

        embed = PidroidEmbed(title=f'{escape_markdown(str(member))} rank')
        embed.add_field(name='Level', value=info.current_level)
        embed.add_field(name='Rank', value=info.rank)       

        # Create a progress bar
        # https://github.com/KumosLab/Discord-Levels-Bot/blob/b01e22a9213b004eed5f88d68b500f4f4cd04891/KumosLab/Database/Create/RankCard/text.py
        dashes = 10
        current_dashes = int(info.current_xp / int(info.xp_to_level_up / dashes))
        current_prog = '🟦' * current_dashes
        remaining_prog = '⬛' * (dashes - current_dashes)

        embed.add_field(name=f'Level progress ({info.current_xp} / {info.xp_to_level_up} XP)', value=f"{current_prog}{remaining_prog}", inline=False)

        await ctx.reply(embed=embed)
        
    @commands.hybrid_command( # type: ignore
        name="leaderboard",
        brief='Returns the server level system leaderboard.',
        category=OwnerCategory
    )
    @commands.guild_only()
    @commands.bot_has_guild_permissions(send_messages=True) # type: ignore
    async def leaderboard_command(self, ctx: Context):
        assert ctx.guild is not None
        levels = await self.client.api.fetch_guild_levels(ctx.guild.id)
        pages = PidroidPages(LeaderboardPaginator(levels), ctx=ctx)
        return await pages.start()

async def setup(client: Pidroid) -> None:
    await client.add_cog(LevelCommands(client))
