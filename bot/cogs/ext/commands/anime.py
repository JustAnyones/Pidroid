"""Father, forgive me for these sins."""

import asyncio
import discord
import random
import re

from discord.ext import commands
from discord.ext.commands.context import Context
from discord.ext.commands.errors import BadArgument
from lxml import etree
from io import StringIO

from constants import JESSE_ID, THEOTOWN_GUILD
from cogs.models.categories import RandomCategory
from cogs.models.waifuListApi import MyWaifuListAPI
from cogs.utils import http
from cogs.utils.embeds import build_embed, error
from cogs.utils.parsers import truncate_string

NEKO_API = "https://nekos.life/api/v2"
NEKO_ENDPOINTS = [
    'tickle', 'meow', 'poke', 'kiss',
    '8ball', 'lizard', 'slap', 'cuddle',
    'goose', 'hug', 'smug', 'waifu',
    'gecg', 'pat', 'wallpaper', 'feed',
    'woof', 'baka'
]

# It's lazy, but I don't care
MYWAIFULIST_DATA = {
    'rem': 41,
    'best girl': 41,
    'astolfo': 2022,
    'monika': 8142,
    'ganyu': 33593,
    'miku': 11896
}

WAIFU_PICS_API = "https://api.waifu.pics/sfw"
WAIFU_PICS_ENDPOINTS = [
    "bully", "cuddle", "cry", "hug", "awoo",
    "kiss", "lick", "pat", "smug", # This is good, I allow this
    "bonk", "yeet", "blush", "smile",
    "wave", "highfive", "handhold", "nom",
    "bite", "glomp", "slap", "kill", "kick",
    "happy", "wink", "poke", "dance", "cringe"
]

def get_owo(text: str) -> str:
    """Returns the input text in owo format."""

    faces = ["owo", "UwU", ">w<", "^w^"]
    v = text
    r = re.sub('[rl]', "w", v)
    r = re.sub('[RL]', "W", r)
    r = re.sub('ove', 'uv', r)
    r = re.sub('n', 'ny', r)
    r = re.sub('N', 'NY', r)
    r = re.sub('[!]', " " + random.choice(faces) + " ", r) # nosec
    return r

class AnimeCommands(commands.Cog):
    """This class implements cog which contains commands for anime related APIs."""

    def __init__(self, client):
        self.client = client

    @commands.command(
        brief='Don\'t ask.',
        category=RandomCategory,
        hidden=True
    )
    @commands.is_owner()
    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True, attach_files=True)
    async def yourebanned(self, ctx: Context):
        async with ctx.typing():
            await ctx.reply(file=discord.File('./resources/you_were_banned.mp4'))

    @commands.group(
        brief='It\'s a gamble, really.',
        category=RandomCategory,
        hidden=True,
        invoke_without_command=True
    )
    @commands.bot_has_permissions(send_messages=True)
    async def cancer(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.reply("Why are we still here? Just to suffer?")

    @cancer.command(
        name='fact',
        brief='Tells a random fact.',
        category=RandomCategory,
        hidden=True
    )
    @commands.bot_has_permissions(send_messages=True)
    async def cancer_fact(self, ctx: Context):
        async with await http.get(self.client, f"{NEKO_API}/fact") as r:
            data = await r.json()
        await ctx.reply(data["fact"])

    @cancer.command(
        name='name',
        brief='Returns a random name.',
        category=RandomCategory,
        hidden=True
    )
    @commands.bot_has_permissions(send_messages=True)
    async def cancer_name(self, ctx: Context):
        async with await http.get(self.client, f"{NEKO_API}/name") as r:
            data = await r.json()
        await ctx.reply(data["name"])

    @cancer.command(
        name='why',
        brief='Questions the life itself.',
        category=RandomCategory,
        hidden=True
    )
    @commands.bot_has_permissions(send_messages=True)
    async def cancer_why(self, ctx: Context):
        async with await http.get(self.client, f"{NEKO_API}/why") as r:
            data = await r.json()
        await ctx.reply(data["why"])

    @cancer.command(
        name='image',
        brief='Returns an image for the specified category.',
        usage='[image type]',
        category=RandomCategory,
        hidden=True
    )
    @commands.bot_has_permissions(send_messages=True)
    async def cancer_image(self, ctx: Context, endpoint: str = None):
        async with ctx.typing():
            if endpoint is None:
                endpoint = random.choice(NEKO_ENDPOINTS) # nosec
            endpoint = endpoint.lower()
            if endpoint in NEKO_ENDPOINTS:
                async with await http.get(self.client, f"{NEKO_API}/img/{endpoint}") as r:
                    data = await r.json()
                await ctx.reply(data["url"])
            else:
                await ctx.reply(embed=error(
                    'Wrong type specified. The allowed types are: `' + ', '.join(NEKO_ENDPOINTS) + '`.'
                ))

    @cancer.command(
        name='owo',
        brief='Returns the original input text, but in owo format.',
        usage='<text to be owoified>',
        category=RandomCategory,
        hidden=True
    )
    @commands.bot_has_permissions(send_messages=True)
    async def cancer_owo(self, ctx: Context, *, text: str = None):
        if text is None:
            return await ctx.reply(embed=error("UwU, what do you want to owoify?")) # I apologize
        await ctx.reply(get_owo(text))

    @commands.command(
        brief='Gets a random waifu from mywaifulist.',
        category=RandomCategory,
        hidden=True,
        enabled=False
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.cooldown(rate=1, per=3.5, type=commands.BucketType.user)
    @commands.max_concurrency(number=1, per=commands.BucketType.user)
    async def waifu(self, ctx: Context, *, selection: str = None):
        async with ctx.typing():
            api = MyWaifuListAPI()
            api.reauthorize()
            waifu_data = None

            if selection is not None:
                waifu_id = MYWAIFULIST_DATA.get(selection.lower(), None)
                waifu_data = api.fetch_waifu(waifu_id)

            if waifu_id is None:
                waifu_data = api.fetch_random_waifu()

            if waifu_data['nsfw']:
                await ctx.reply(embed=error("Found waifu was NSFW!"))
                return

            embed = build_embed(title=waifu_data['name'], description=truncate_string(waifu_data['description']), url=waifu_data['url'])
            embed.set_image(url=waifu_data['display_picture'])
            await ctx.reply(embed=embed)

    @commands.command(
        name="animedia",
        brief="Fetches an anime themed GIF/image file from an API for the specified purpose.",
        category=RandomCategory,
        hidden=True
    )
    @commands.bot_has_permissions(send_messages=True)
    async def anime_media(self, ctx: Context, endpoint: str = None):
        if endpoint is not None:
            endpoint = endpoint.lower().strip()
            if endpoint not in WAIFU_PICS_ENDPOINTS:
                raise BadArgument("WRONG!!!")
        else:
            endpoint = random.choice(WAIFU_PICS_ENDPOINTS) # nosec
        async with await http.get(self.client, f"{WAIFU_PICS_API}/{endpoint}") as r:
            data = await r.json()

        embed = build_embed()
        embed.title = f"Endpoint: {endpoint}"
        embed.set_image(url=data["url"])
        await ctx.reply(embed=embed)

    @commands.command(
        category=RandomCategory,
        hidden=True
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.max_concurrency(number=1, per=commands.BucketType.guild, wait=True)
    async def weeb(self, ctx: Context):
        if ctx.guild.id == THEOTOWN_GUILD:
            for _ in range(7):
                await asyncio.sleep(random.randint(2, 5)) # nosec
                await ctx.send(f"<@{JESSE_ID}>, you asked for it")


def setup(client):
    client.add_cog(AnimeCommands(client))
