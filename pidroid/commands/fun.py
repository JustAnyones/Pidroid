import asyncio
import discord
import random

from datetime import datetime
from discord import AllowedMentions
from discord.channel import VoiceChannel, StageChannel
from discord.colour import Color, Colour
from discord.embeds import Embed
from discord.ext import commands
from discord.ext.commands import BadArgument, Context, MissingRequiredArgument
from discord.voice_client import VoiceClient
from typing import Optional

from pidroid.client import Pidroid
from pidroid.models.categories import RandomCategory
from pidroid.services.error_handler import notify
from pidroid.utils.checks import assert_bot_channel_permissions
from pidroid.utils.decorators import command_checks
from pidroid.utils.embeds import PidroidEmbed, ErrorEmbed
from pidroid.utils.file import Resource
from pidroid.utils.http import get, Route

CLOAKER_LINES = [
    'cloaker_1', 'cloaker_2', 'cloaker_3',
    'cloaker_4', 'cloaker_5', 'cloaker_6',
    'cloaker_7'
]

PINGU_RESPONSES = [
    ('Ooga booga', Resource('pingutroll.gif')),
    ('I can\'t read lol', Resource('pinguread.gif')),
    ('NOOT NOOT!', Resource('pingunoot.gif')),
    ('Spotify premium be like:', Resource('pingumusic.gif')),
    ('NOOT NOOT',  Resource('pingu.png'))
]

FUN_FACTS = [
    'Javascript isn\'t the greatest programming language in the world, but at least it counts its arrays from 0 unlike some other languages...',
    'RemainsStay is a lovely sloth administrator of TheoTown server.',
    'Ene7 is our detective pingu.',
    'Evan? Oh, you mean that helpful firetruck. Yeah, he\'s awesome.',
    'Lobby is an entranceway or foyer in a building. What? That\'s not what Lobby is?',
    'I\'ve heard a user by the name of The26 likes ducks. I suggest you send them a duck picture.',
    'Yo, Q||_REMOVED_||02, do you know where I can get some of them wide monitors you have?',
    'KolaKattz? Nope, never heard of him. Have you?',
    'I have multiple brothers, one of them is named Pidroid Beta. Perhaps you\'ve met him already?',
    'This bot is built using discord.py wrapper made by an awesome guy called Rapptz.',
    'Man, the other day I was searching for some medic bags and I couldn\'t find any. They are all gone!',
    'Yes, *kentucky* fried chicken is indeed my good friend',
    'Did I ever tell you the definition of insanity? No? Welp, I can\'t just do it now!',
    'Lucas King is a great musician with the great soundtrack he made for the game.',
    'NOLOGIC? ah, it is a secret gamemode which is broken in every way possible. It very familiar to sandbox mode.',
    'This fact feature was introduced in version 2.8.0 of Pidroid, with later versions expanding the facts.',
    'January 15th is Fire Truck Appreciation Day!',
    'Jesse does indeed like to talk, he doesn\'t like starting the conversation though.',
    'The name of DSA agency has no meaning.',
    'The name Theo comes from a previous developer of the game named theotheoderich.',
    'Ever wanted to reset your in-game progress and get an achievement for that? Just open the developer console of the game and run ``rm -rf /theotown``'
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


class FunCommandCog(commands.Cog):
    """This class implements a cog which contains commands for entertainment."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client

    @property
    def tenor_token(self) -> str:
        """Returns TENOR GIF API token."""
        try:
            return self.client.config['tenor_api_key']
        except KeyError:
            raise BadArgument("Credentials for TENOR GIF API could not be found!")

    @commands.command(
        name="color",
        brief='Returns a random color.',
        usage="[hex color]",
        aliases=['colour'],  # Bri'ish spelling
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def color_command(self, ctx: Context, hex_str: Optional[str]):        
        if hex_str is not None:
            try:
                color = colour_from_hex(hex_str)
            except ValueError:
                raise BadArgument("Specified string is not a valid hexadecimal value!")
        else:
            color = Color.random()
        embed = Embed(title=color.__str__(), color=color)
        await ctx.reply(embed=embed)

    @commands.command(
        name="pingu",
        brief='Noot noot!',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True, attach_files=True)
    async def pingu_command(self, ctx: Context):
        async with ctx.typing():
            text, file_path = random.choice(PINGU_RESPONSES) # nosec
            await ctx.reply(text, file=discord.File(file_path))

    @commands.command(
        name="sloth",
        brief='Summons a very slow creature.',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True, attach_files=True)
    async def sloth_command(self, ctx: Context):
        async with ctx.typing():
            await ctx.reply(content="The myth, the legend.", file=discord.File(Resource('sloth.gif')))

    @commands.command(
        name="happiness",
        brief='Returns a positive review from TheoTown listing on play store.',
        permissions=["TheoTown developer"],
        category=RandomCategory,
        hidden=True
    )
    @command_checks.is_theotown_developer()
    @commands.bot_has_permissions(send_messages=True)
    async def happiness_command(self, ctx: Context):
        res = await self.client.api.get(Route("/private/review/fetch_random"))
        data = res["data"]
        embed = PidroidEmbed(description=data['comment'], timestamp=datetime.fromtimestamp(float(data['comment_time'])))
        embed.set_author(name=data['author'])
        embed.set_footer(text=f"{data['rating']} ⭐")
        await ctx.reply(embed=embed)

    @commands.command(
        name="fire",
        brief='I smell fire, do you? In either case, lets call a fireman!',
        category=RandomCategory
    )
    @command_checks.is_theotown_guild()
    @commands.bot_has_permissions(send_messages=True, attach_files=True)
    async def fire_command(self, ctx: Context):
        async with ctx.typing():
            await ctx.reply(
                content="There's a fire somewhere? Call <@326167365677219840> to the rescue!",
                allowed_mentions=AllowedMentions(users=False),
                file=discord.File(Resource('evan.png'))
            )

    @commands.command(
        name="gif",
        brief='Queries a GIF from TENOR.',
        usage='<search term>',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def gif_command(self, ctx: Context, *, query: str):
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

    @gif_command.error
    async def on_gif_command_error(self, ctx: Context, error):
        if isinstance(error, MissingRequiredArgument):
            if error.param.name == "query":
                return await notify(ctx, "Please specify a value to query GIFs with.")
        setattr(error, 'unhandled', True)

    @commands.command(
        name="dice",
        brief='Rolls a dice.',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def dice_command(self, ctx: Context):
        await ctx.reply(f"The dice rolls a {random.randint(1, 6)}!") # nosec

    @commands.command(
        name="roll",
        brief='Rolls a random number between 1 and the specified value.\nThe default value is 6.',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def roll_command(self, ctx: Context, limit: int = 6):
        if limit <= 1:
            raise BadArgument("Limit cannot be 1 or less. It'd be stupid")
        await ctx.reply(f"You rolled a {random.randint(1, limit)}!") # nosec

    @commands.command(
        name="fact",
        brief='Asks Pidroid to tell one of his own facts.',
        category=RandomCategory
    )
    @commands.cooldown(rate=2, per=6, type=commands.BucketType.user)
    @commands.bot_has_permissions(send_messages=True)
    async def fact_command(self, ctx: Context):
        await ctx.reply(random.choice(FUN_FACTS)) # nosec

    @commands.command(
        name="cloaker",
        brief='Calls a cloaker to kickdrop your friends in a voice channel.',
        usage='<member in voice channel>',
        aliases=['wululu'],
        category=RandomCategory,
        hidden=True
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @command_checks.is_cheese_consumer()
    async def cloaker_command(self, ctx: Context, member: discord.Member):
        assert isinstance(ctx.author, discord.Member)
        voice = ctx.author.voice
        if voice is None:
            raise BadArgument("You are not in a voice channel!")

        channel = voice.channel
        assert isinstance(channel, (VoiceChannel, StageChannel))
        if member not in channel.members:
            raise BadArgument("Specified user is not in the voice channel!")

        if self.client.user in channel.members:
            raise BadArgument("Bro, I am already in that channel. What do you want me to do?")

        assert isinstance(ctx.me, discord.Member)
        assert_bot_channel_permissions(ctx.me, channel, move_members=True, speak=True, connect=True)

        try:
            vc: VoiceClient = await channel.connect(reconnect=False)
        except discord.errors.ClientException:
            raise BadArgument("I\'m already inside a voice channel!")

        audio_source = discord.FFmpegPCMAudio(Resource('cloaked.mp3'))
        
        vc.play(audio_source)
        while vc.is_playing():
            await asyncio.sleep(0.01)
        await member.edit(voice_channel=None)
        await ctx.reply(f'{str(member)} has been cloaked!')
        audio_source = discord.FFmpegPCMAudio(Resource(f'{random.choice(CLOAKER_LINES)}.mp3')) # nosec
        vc.play(audio_source)
        while vc.is_playing():
            await asyncio.sleep(0.01)
        await vc.disconnect()

    @cloaker_command.error
    async def on_cloaker_command_error(self, ctx: Context, error):
        if isinstance(error, MissingRequiredArgument):
            if error.param.name == "member":
                return await notify(ctx, "Please specify the member to be cloaked.")
        setattr(error, 'unhandled', True)

async def setup(client: Pidroid) -> None:
    await client.add_cog(FunCommandCog(client))
