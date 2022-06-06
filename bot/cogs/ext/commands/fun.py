import asyncio
import discord
import random

from datetime import datetime
from discord import AllowedMentions
from discord.channel import VoiceChannel
from discord.colour import Color, Colour
from discord.embeds import Embed
from discord.ext import commands
from discord.ext.commands.context import Context # type: ignore
from discord.ext.commands.errors import BadArgument # type: ignore
from discord.voice_client import VoiceClient

from client import Pidroid
from constants import FACTS
from cogs.models.categories import RandomCategory
from cogs.utils.checks import check_bot_channel_permissions
from cogs.utils.decorators import command_checks
from cogs.utils.embeds import PidroidEmbed, ErrorEmbed
from cogs.utils.http import get, Route

CLOAKER_LINES = [
    'cloaker_1', 'cloaker_2', 'cloaker_3',
    'cloaker_4', 'cloaker_5', 'cloaker_6',
    'cloaker_7'
]

PINGU_RESPONSES = [
    ('Ooga booga', './resources/pingutroll.gif'),
    ('I can\'t read lol', './resources/pinguread.gif'),
    ('NOOT NOOT!', './resources/pingunoot.gif'),
    ('Spotify premium be like:', './resources/pingumusic.gif'),
    ('NOOT NOOT', './resources/pingu.png')
]

def colour_from_hex(hex_str: str) -> Colour:
    """Constructs a colour object from a hex string."""
    hex_str = hex_str.replace("#", "")
    if len(hex_str) > 6:
        raise BadArgument("Hex string is too long!")

    # Account for cases where user inputs #FF, etc
    while len(hex_str) < 6:
        hex_str += "0"

    # Looks ugly, idc
    r, g, b = (int(hex_str[i:i + 2], 16) for i in (0, 2, 4))
    return Colour((r << 16) + (g << 8) + b)


class FunCommands(commands.Cog): # type: ignore
    """This class implements a cog which contains commands for entertainment."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.api = self.client.api

    @property
    def tenor_token(self) -> str:
        """Returns TENOR GIF API token."""
        try:
            return self.client.config['authentication']['tenor']['token']
        except KeyError:
            raise BadArgument("Credentials for TENOR GIF API could not be found!")

    @commands.command( # type: ignore
        brief='Returns a random color.',
        usage="[hex color]",
        aliases=['colour'],  # Bri'ish spelling
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def color(self, ctx: Context, hex_str: str = None):
        if hex_str is not None:
            try:
                color = colour_from_hex(hex_str)
            except ValueError:
                raise BadArgument("Specified string is not hex!")
        else:
            color = Color.random()
        embed = Embed(title=color.__str__(), color=color)
        await ctx.reply(embed=embed)

    @commands.command( # type: ignore
        brief='Noot noot!',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True, attach_files=True) # type: ignore
    async def pingu(self, ctx: Context):
        async with ctx.typing():
            text, file_path = random.choice(PINGU_RESPONSES) # nosec
            await ctx.reply(text, file=discord.File(file_path))

    @commands.command( # type: ignore
        brief='Summons a very slow creature.',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True, attach_files=True) # type: ignore
    async def sloth(self, ctx: Context):
        async with ctx.typing():
            await ctx.reply(content="M m m m m  y e s . . .\nGIF file loads as fast as what is about to load in.", file=discord.File('./resources/sloth.gif'))

    @commands.command( # type: ignore
        brief='Returns a positive review from TheoTown listing on play store.',
        permissions=["TheoTown developer"],
        category=RandomCategory,
        hidden=True
    )
    @command_checks.is_theotown_developer()
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def happiness(self, ctx: Context):
        res = await self.api.get(Route("/private/review/get"))
        data = res["data"]
        embed = PidroidEmbed(description=data['comment'], timestamp=datetime.fromtimestamp(float(data['comment_time'])))
        embed.set_author(name=data['author'])
        embed.set_footer(text=f"{data['rating']} ⭐")
        await ctx.reply(embed=embed)

    @commands.command( # type: ignore
        brief='I smell fire, do you? In either case, lets call a fireman!',
        category=RandomCategory
    )
    @command_checks.is_theotown_guild()
    @commands.bot_has_permissions(send_messages=True, attach_files=True) # type: ignore
    async def fire(self, ctx: Context):
        async with ctx.typing():
            await ctx.reply(
                content="There's a fire somewhere? Call <@326167365677219840> to the rescue!",
                allowed_mentions=AllowedMentions(users=False),
                file=discord.File('./resources/evan.png')
            )

    @commands.command( # type: ignore
        brief='Queries a GIF from TENOR.',
        usage='<search term>',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def gif(self, ctx: Context, *, query: str):
        async with ctx.typing():
            async with await get(
                self.client,
                f"https://api.tenor.com/v1/search?q={query}&key={self.tenor_token}&limit=30&contentfilter=medium"
            ) as response:
                data = await response.json()
            if 'results' in data:
                if len(data["results"]) > 0:
                    gif = random.choice(data['results']) # nosec
                    return await ctx.reply(gif['url'])
            await ctx.reply(embed=ErrorEmbed("I couldn't find any GIFs for the specified query!"))

    @commands.command( # type: ignore
        brief='Rolls a dice.',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def dice(self, ctx: Context):
        await ctx.reply(f"The dice rolls a {random.randint(1, 6)}!") # nosec

    @commands.command( # type: ignore
        brief='Rolls a random number between 1 and the specified value.\nThe default value is 6.',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def roll(self, ctx: Context, limit: int = 6):
        if limit <= 1:
            raise BadArgument("Limit cannot be 1 or less. It'd be stupid")
        await ctx.reply(f"You rolled a {random.randint(1, limit)}!") # nosec

    @commands.command( # type: ignore
        brief='Asks Pidroid to tell one of his own facts.',
        category=RandomCategory
    )
    @commands.cooldown(rate=2, per=6, type=commands.BucketType.user) # type: ignore
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.client_is_pidroid()
    async def fact(self, ctx: Context):
        await ctx.reply(random.choice(FACTS)) # nosec

    @commands.command( # type: ignore
        brief='Calls a cloaker to kickdrop your friends in a voice channel.',
        usage='<member in voice channel>',
        aliases=['wululu'],
        category=RandomCategory,
        hidden=True
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.guild_only() # type: ignore
    @command_checks.is_cheese_consumer()
    async def cloaker(self, ctx: Context, member: discord.Member):
        voice = ctx.author.voice
        if voice is None:
            return await ctx.reply(embed=ErrorEmbed('You are not in a voice channel!'))

        channel: VoiceChannel = voice.channel
        if member not in channel.members:
            return await ctx.reply(embed=ErrorEmbed('Specified user is not in the voice channel!'))

        if self.client.user in channel.members:
            return await ctx.reply(embed=ErrorEmbed('Bro, I am already in that channel. What do you want me to do?'))

        check_bot_channel_permissions(channel, ctx.me, move_members=True, speak=True, connect=True)

        try:
            vc: VoiceClient = await channel.connect(reconnect=False)
        except discord.errors.ClientException:
            return await ctx.reply(embed=ErrorEmbed('I\'m already inside a voice channel!'))

        audio_source = discord.FFmpegPCMAudio('./resources/cloaked.mp3')
        vc.play(audio_source)
        while vc.is_playing():
            await asyncio.sleep(0.01)
        await member.edit(voice_channel=None)
        await ctx.reply(f'{member.name}#{member.discriminator} has been cloaked!')
        audio_source = discord.FFmpegPCMAudio(f'./resources/{random.choice(CLOAKER_LINES)}.mp3') # nosec
        vc.play(audio_source)
        while vc.is_playing():
            await asyncio.sleep(0.01)
        await vc.disconnect()

async def setup(client: Pidroid) -> None:
    await client.add_cog(FunCommands(client))
