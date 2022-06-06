"""Father, forgive me for these sins."""

import asyncio
import discord
import random
import re

from discord.ext import commands
from discord.ext.commands.context import Context # type: ignore
from discord.ext.commands.errors import BadArgument # type: ignore
from typing import List, Union

from client import Pidroid
from constants import JESSE_ID, THEOTOWN_GUILD
from cogs.utils import http
from cogs.utils.embeds import PidroidEmbed, SuccessEmbed, ErrorEmbed
from cogs.utils.paginators import ListPageSource, PidroidPages
from cogs.utils.parsers import truncate_string
from cogs.models.categories import RandomCategory
from cogs.models.exceptions import APIException
from cogs.models.waifulistapi import MyWaifuListAPI, Waifu, WaifuSearchResult

NEKO_API = "https://nekos.life/api/v2"
NEKO_ENDPOINTS = [
    'tickle', 'meow', 'poke', 'kiss',
    '8ball', 'lizard', 'slap', 'cuddle',
    'goose', 'hug', 'smug', 'waifu',
    'gecg', 'pat', 'wallpaper', 'feed',
    'woof', 'baka'
]

WAIFU_PICS_API = "https://api.waifu.pics/sfw"
WAIFU_PICS_ENDPOINTS = [
    "bully", "cuddle", "cry", "hug", "awoo",
    "kiss", "lick", "pat", "smug", # This is good, I allow this
    "bonk", "yeet", "blush", "smile",
    "wave", "highfive", "handhold", "nom",
    "bite", "glomp", "slap", "kill", "kick",
    "happy", "wink", "poke", "dance", "cringe"
]

class WaifuCommandPaginator(ListPageSource):
    def __init__(self, data: List[Union[WaifuSearchResult, Waifu]]):
        super().__init__(data, per_page=1)
        self.embed = PidroidEmbed()

    async def format_page(self, menu: PidroidPages, waifu: Union[Waifu, WaifuSearchResult]):
        self.embed.clear_fields()
        if isinstance(waifu, WaifuSearchResult):
            waifu = await waifu.fetch_waifu()
        if waifu.is_nsfw:
            self.embed.title = waifu.name + " [NSFW]"
            if not menu.ctx.channel.is_nsfw():
                self.embed.set_image(url="")
                self.embed.description = 'This waifu is tagged as NSFW. In order to view the waifu, please use the command in an age-restricted channel.'
                self.embed.url = None
                self.embed.set_footer(text=None)
                return self.embed
        else:
            self.embed.title = waifu.name

        if waifu.description:
            self.embed.description = truncate_string(waifu.description, max_length=600)
        self.embed.url = waifu.url
        self.embed.set_image(url=waifu.display_picture)
        if waifu.series:
            self.embed.set_footer(text='Appears in: ' + waifu.series['name']) # type: ignore
        return self.embed

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

class AnimeCommands(commands.Cog): # type: ignore
    """This class implements cog which contains commands for anime related APIs."""

    def __init__(self, client):
        self.client = client
        self.waifu_list_api = MyWaifuListAPI()

    @commands.command( # type: ignore
        brief='Don\'t ask.',
        category=RandomCategory,
        hidden=True
    )
    @commands.is_owner() # type: ignore
    @commands.guild_only() # type: ignore
    @commands.bot_has_permissions(send_messages=True, attach_files=True) # type: ignore
    async def yourebanned(self, ctx: Context):
        async with ctx.typing():
            await ctx.reply(file=discord.File('./resources/you_were_banned.mp4'))

    @commands.group( # type: ignore
        category=RandomCategory,
        hidden=True,
        invoke_without_command=True
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def neko(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            raise BadArgument((
                "Invalid neko subcommand specified. "
                "Please consult the help command."
            ))

    @neko.command(
        name='fact',
        brief='Tells a random fact as provided by the API.',
        category=RandomCategory,
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def neko_fact(self, ctx: Context):
        async with await http.get(self.client, f"{NEKO_API}/fact") as r:
            data = await r.json()
        await ctx.reply(embed=SuccessEmbed(data["fact"]))

    @neko.command(
        name='name',
        brief='Generates a random name from the API.',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def neko_name(self, ctx: Context):
        async with await http.get(self.client, f"{NEKO_API}/name") as r:
            data = await r.json()
        await ctx.reply(embed=SuccessEmbed(data["name"]))

    @neko.command(
        name='why',
        brief='Questions that make you think as provided by the API.',
        category=RandomCategory,
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def neko_why(self, ctx: Context):
        async with await http.get(self.client, f"{NEKO_API}/why") as r:
            data = await r.json()
        await ctx.reply(embed=SuccessEmbed(data["why"]))

    @neko.command(
        name='image',
        brief='Fetches an image for the specified type as provided by the API.',
        usage='[image type]',
        category=RandomCategory,
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def neko_image(self, ctx: Context, endpoint: str = None):
        if endpoint is None:
            endpoint = random.choice(NEKO_ENDPOINTS) # nosec

        endpoint = endpoint.lower()
        if endpoint in NEKO_ENDPOINTS:
            async with await http.get(self.client, f"{NEKO_API}/img/{endpoint}") as r:
                data = await r.json()
            embed = SuccessEmbed()
            embed.set_image(url=data["url"])
            embed.set_footer(text=endpoint)
            return await ctx.reply(embed=embed)

        raise BadArgument(
            'Wrong image type specified. The allowed types are: `' + ', '.join(NEKO_ENDPOINTS) + '`.'
        )

    @commands.command( # type: ignore
        brief='Returns the original input text, but in owo format.',
        usage='<text to be converted>',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def owo(self, ctx: Context, *, text: str = None):
        if text is None:
            raise BadArgument("UwU, what do you want to owoify?") # I apologize
        await ctx.reply(embed=SuccessEmbed(get_owo(text)))

    @commands.command( # type: ignore
        brief='Returns a random waifu from MyWaifuList.',
        usage='[waifu to search]',
        category=RandomCategory,
        enabled=False
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.cooldown(rate=1, per=3.5, type=commands.BucketType.user) # type: ignore
    @commands.max_concurrency(number=1, per=commands.BucketType.user) # type: ignore
    async def waifu(self, ctx: Context, *, selection: str = None):
        api = self.waifu_list_api

        waifus = []
        if selection is not None:
            if len(selection) < 2:
                return await ctx.reply(embed=ErrorEmbed("Your selection must be at least 2 characters long!"))

            if selection.lower() == "best girl":
                waifus.append(await api.fetch_waifu_by_id(41))

            else:
                search_data = api.search_cache.get(selection)
                if search_data is None:
                    async with ctx.typing():
                        try:
                            search_data = await api.search(selection)
                        except APIException as e:
                            return await ctx.reply(embed=ErrorEmbed(str(e)))

                for search in search_data:
                    if isinstance(search, WaifuSearchResult):
                        waifus.append(search)

                if len(waifus) == 0:
                    return await ctx.reply(embed=ErrorEmbed("Search did not find any waifus!"))
                waifus.sort(key=lambda w: w.likes, reverse=True)
        else:
            waifus.append(await api.fetch_random_waifu())

        pages = PidroidPages(WaifuCommandPaginator(waifus), ctx=ctx)
        return await pages.start()

    @commands.command( # type: ignore
        name="animedia",
        brief="Fetches an anime themed GIF/image file from waifu.pics API.",
        usage="[media type]",
        category=RandomCategory,
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def anime_media(self, ctx: Context, endpoint: str = None):
        if endpoint is not None:
            endpoint = endpoint.lower().strip()
            if endpoint not in WAIFU_PICS_ENDPOINTS:
                raise BadArgument((
                    'Wrong media type specified. '
                    'The allowed types are: `' + ', '.join(WAIFU_PICS_ENDPOINTS) + '`.'
                ))
        else:
            endpoint = random.choice(WAIFU_PICS_ENDPOINTS) # nosec
        async with await http.get(self.client, f"{WAIFU_PICS_API}/{endpoint}") as r:
            data = await r.json()

        embed = SuccessEmbed()
        embed.set_image(url=data["url"])
        embed.set_footer(text=endpoint)
        await ctx.reply(embed=embed)

    @commands.command( # type: ignore
        category=RandomCategory,
        hidden=True
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.max_concurrency(number=1, per=commands.BucketType.guild, wait=True) # type: ignore
    async def weeb(self, ctx: Context):
        if ctx.guild.id == THEOTOWN_GUILD:
            for _ in range(7):
                await asyncio.sleep(random.randint(2, 5)) # nosec
                await ctx.send(f"<@{JESSE_ID}>, you asked for it")


async def setup(client: Pidroid):
    await client.add_cog(AnimeCommands(client))
