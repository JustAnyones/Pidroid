import datetime

from asyncio import exceptions
from discord import utils
from discord.channel import TextChannel
from discord.ext import commands # type: ignore
from discord.ext.commands.context import Context # type: ignore
from discord.ext.commands.converter import TextChannelConverter # type: ignore
from discord.ext.commands.errors import BadArgument # type: ignore
from discord.message import Message

from pidroid.client import Pidroid
from pidroid.cogs.models.categories import UtilityCategory
from pidroid.cogs.utils.converters import Duration
from pidroid.cogs.utils.embeds import PidroidEmbed
from pidroid.cogs.utils.time import datetime_to_duration

GIVEAWAY_TIMEOUT = 180

class GiveawayCommand(commands.Cog): # type: ignore
    """This class implements a cog with commands for dealing with giveaway creation."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client

    async def await_response(self, ctx: Context) -> Message:
        """Awaits message from user."""
        msg = await self.client.wait_for('message', check=lambda message: message.author == ctx.author, timeout=GIVEAWAY_TIMEOUT)
        return msg

    async def parse_prize(self, ctx: Context) -> str:
        """Awaits for prize from user."""
        msg = await self.await_response(ctx)
        return msg.content

    async def parse_winners(self, ctx: Context) -> int:
        """Awaits winner count from user."""
        msg = await self.await_response(ctx)
        try:
            winners = int(msg.content)
        except ValueError:
            raise BadArgument("Incorrect winner range specified. It must be between 1 and 30!")
        if not 31 > winners > 0:
            raise BadArgument("Incorrect winner range specified. It must be between 1 and 30!")
        return winners

    async def parse_channel(self, ctx: Context) -> TextChannel:
        """Awaits channel from user."""
        msg = await self.await_response(ctx)
        return await TextChannelConverter().convert(ctx, msg.content)

    async def parse_duration(self, ctx: Context) -> datetime.datetime:
        """Awaits duration from user."""
        msg = await self.await_response(ctx)
        datetime = await Duration().convert(ctx, msg.content)
        duration = datetime_to_duration(datetime)
        if duration < 60:
            raise BadArgument("Giveaway duration is too short! Make sure it's at least a minute long.")
        if duration > 2678400:
            raise BadArgument("I can't count higher than 31 days, can we go a little lower?")
        return datetime

    @commands.command( # type: ignore
        brief='An experimental command for possible inclusion of the giveaway system.',
        category=UtilityCategory,
        hidden=True
    )
    @commands.is_owner() # type: ignore
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def giveaway(self, ctx: Context):
        await ctx.reply((
            ":tada: Alright, let's begin!\n\n"
            "First, what do you want to give away?\n"
            "``Not documented.``"
        ))
        try:
            # Prize
            prize = await self.parse_prize(ctx)

            # Winners
            await ctx.reply((
                f":tada: Ok, we'll give away '{prize}'!\n\n"
                "How many winners would you like to have?\n"
                "``Choose a number between 1 and 30.``"
            ))
            winners = await self.parse_winners(ctx)

            winner_text = "winners"
            if winners == 1:
                winner_text = "winner"

            # Channel where the giveaway will be hosted
            await ctx.reply((
                f":tada: {winners} {winner_text} it is!\n\n"
                "What channel would you like me to use to host the giveaway?\n"
                "``Mention or provide the name of the channel.``"
            ))
            channel = await self.parse_channel(ctx)

            # The duration of the giveaway
            await ctx.reply((
                f":tada: We'll host the giveaway in {channel.mention} channel!\n\n"
                "Lastly, how long would you like the giveaway to last?\n"
                "``Not documented.``"
            ))
            datetime = await self.parse_duration(ctx)

            # TODO: add database table for holding giveaway data
            # TODO: add handlers for giveaways ending
            # TODO: implement permission checks for giveaway channel

            description = ''
            description += 'React with :tada: to enter!\n'
            description += f'Ends in: {utils.format_dt(datetime, "R")}\n'
            description += f'Hosted by: {ctx.author.mention}'
            embed = PidroidEmbed(title=prize, description=description, timestamp=datetime)
            await ctx.reply(f'Beginning the giveaway in {channel.mention}')
            msg = await channel.send(content=':tada: **GIVEAWAY** :tada:', embed=embed)
            await msg.add_reaction("🎉")
        except exceptions.TimeoutError:
            await ctx.reply('Giveaway creation failed: timeout!')


async def setup(client: Pidroid) -> None:
    await client.add_cog(GiveawayCommand(client))
