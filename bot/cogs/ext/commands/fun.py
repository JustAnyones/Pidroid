import asyncio
import discord
import os
import random

from datetime import datetime
from discord import AllowedMentions
from discord.channel import VoiceChannel
from discord.colour import Color, Colour
from discord.ext import commands
from discord.ext.commands.context import Context
from discord.ext.commands.errors import BadArgument
from discord.voice_client import VoiceClient

from client import Pidroid
from constants import FACTS
from cogs.models.categories import RandomCategory
from cogs.utils.decorators import command_checks
from cogs.utils.embeds import build_embed, error
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


class FunCommands(commands.Cog):
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

    @commands.command(
        brief='Returns a random color.',
        usage="[hex color]",
        aliases=['colour'],  # Bri'ish spelling
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def color(self, ctx: Context, hex_str: str = None):
        if hex_str is not None:
            try:
                color = colour_from_hex(hex_str)
            except ValueError:
                raise BadArgument("Specified string is not hex!")
        else:
            color = Color.random()
        embed = build_embed(title=color.__str__(), color=color)
        await ctx.reply(embed=embed)

    @commands.command(
        brief='Noot noot!',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True, attach_files=True)
    async def pingu(self, ctx: Context):
        async with ctx.typing():
            text, file_path = random.choice(PINGU_RESPONSES) # nosec
            await ctx.reply(text, file=discord.File(file_path))

    @commands.command(
        brief='Summons a very slow creature.',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True, attach_files=True)
    async def sloth(self, ctx: Context):
        async with ctx.typing():
            await ctx.reply(content="M m m m m  y e s . . .\nGIF file loads as fast as what is about to load in.", file=discord.File('./resources/sloth.gif'))

    @commands.command(
        brief='Returns a positive review from TheoTown listing on play store.',
        permissions=["TheoTown developer"],
        category=RandomCategory,
        hidden=True
    )
    @command_checks.is_theotown_developer()
    @commands.bot_has_permissions(send_messages=True)
    async def happiness(self, ctx: Context):
        data = await self.api.get(Route("/private/review/get"))
        embed = build_embed(description=data['comment'], timestamp=datetime.fromtimestamp(float(data['comment_time'])))
        embed.set_author(name=data['author'])
        embed.set_footer(text=f"{data['rating']} ⭐")
        await ctx.reply(embed=embed)

    @commands.command(
        brief='I smell fire, do you? In either case, lets call a fireman!',
        category=RandomCategory
    )
    @command_checks.is_theotown_guild()
    @commands.bot_has_permissions(send_messages=True, attach_files=True)
    async def fire(self, ctx: Context):
        async with ctx.typing():
            await ctx.reply(
                content="There's a fire somewhere? Call <@326167365677219840> to the rescue!",
                allowed_mentions=AllowedMentions(users=False),
                file=discord.File('./resources/evan.png')
            )

    @commands.command(
        brief='Queries a GIF from TENOR.',
        usage='<search term>',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True)
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
                    await ctx.reply(gif['url'])
                    return
            await ctx.reply(embed=error("I couldn't find any GIFs for the specified query!"))

    @commands.command(
        brief='Summon putin to apologize for something.',
        usage='[what are you sorry for?]',
        category=RandomCategory,
        hidden=True
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True, attach_files=True)
    async def sorry(self, ctx: Context, *, reason: str):
        async with ctx.typing():
            await ctx.reply(content=f"I am sincerely sorry for {reason}!", file=discord.File('./resources/sorry.png'))

    @commands.command(
        brief='Asks Pidroid to tell one of his own facts.',
        category=RandomCategory
    )
    @commands.cooldown(rate=2, per=6, type=commands.BucketType.user)
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.client_is_pidroid()
    async def fact(self, ctx: Context):
        await ctx.reply(random.choice(FACTS)) # nosec

    @commands.command(
        brief='Calls a cloaker to kickdrop your friends in a voice channel.',
        usage='<member in voice channel>',
        aliases=['wululu'],
        category=RandomCategory,
        hidden=True
    )
    @commands.bot_has_permissions(send_messages=True, move_members=True, speak=True, connect=True)
    @commands.guild_only()
    @command_checks.is_cheese_consumer()
    async def cloaker(self, ctx: Context, member: discord.Member):
        async with ctx.typing():
            voice = ctx.author.voice
            if voice is None:
                return await ctx.reply(embed=error('You are not in a voice channel!'))

            channel: VoiceChannel = voice.channel
            if member not in channel.members:
                return await ctx.reply(embed=error('Specified user is not in the voice channel!'))

            if self.client.user in channel.members:
                return await ctx.reply(embed=error('Bro, I am already in that channel. What do you want me to do?'))

            try:
                vc: VoiceClient = await channel.connect(reconnect=False)
            except discord.errors.ClientException:
                return await ctx.reply(embed=error('I\'m already inside a voice channel!'))

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

    @commands.command(
        brief='Submits a shitpost idea for ocassional Pidroid shitposts.',
        usage='[shitpost message]',
        category=RandomCategory,
        hidden=True
    )
    @commands.bot_has_permissions(send_messages=True)  # kind of obsolete too
    @commands.cooldown(rate=1, per=25, type=commands.BucketType.user)
    async def suggestshit(self, ctx: Context, *, text: str = None):
        async with ctx.typing():
            if text is None:
                text = '*Suggestor provided no description!*'

            if len(text) > 2048:
                await ctx.reply(embed=error('Man, your shitpost is longer than my copypastas, let\'s trim it down next time, eh?'))
                self.suggestshit.reset_cooldown(ctx)
                return

            channel = self.client.get_channel(826456482262024242)
            embed = build_embed(description=text)
            embed.set_author(name=ctx.author, icon_url=ctx.author.avatar.url)

            attachments = ctx.message.attachments
            shitpost_file = None
            if attachments:

                if len(attachments) > 1:
                    await ctx.reply(embed=error("I will only accept one file attached at a time!"))
                    self.suggestshit.reset_cooldown(ctx)
                    return

                attachment = attachments[0]
                if attachment.size >= 7000000:
                    await ctx.reply(embed=error('Your attachment is over 7 MB big! I can\'t use that!'))
                    self.suggestshit.reset_cooldown(ctx)
                    return

                filename = attachment.filename
                extension = os.path.splitext(filename)[1]
                if extension.lower() not in ['.png', '.jpg', '.jpeg', '.gif', '.mp4', '.mov', '.webp', '.webm']:
                    await ctx.reply(
                        embed=error('Could not submit a your shitpost, because provided shitpost was in an unsupported file extension.')
                    )
                    self.suggestshit.reset_cooldown(ctx)
                    return

                shitpost_file = await attachment.to_file() or None

            await channel.send(embed=embed, file=shitpost_file)
            await ctx.reply('Your shitpost idea has been successfully submitted!')


def setup(client: Pidroid) -> None:
    client.add_cog(FunCommands(client))
