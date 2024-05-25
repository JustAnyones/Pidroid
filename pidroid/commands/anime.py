import asyncio
import discord
import random
import re

from discord import DMChannel, GroupChannel, PartialMessageable
from discord.ext import commands
from discord.ext.commands import BadArgument, Context, MissingRequiredArgument
from typing import Optional, override

from pidroid.client import Pidroid
from pidroid.constants import JESSE_ID
from pidroid.models.categories import RandomCategory
from pidroid.models.exceptions import APIException
from pidroid.models.view import PaginatingView
from pidroid.models.waifulistapi import MyWaifuListAPI, Waifu, WaifuSearchResult
from pidroid.services.error_handler import notify
from pidroid.utils import http, truncate_string
from pidroid.utils.decorators import command_checks
from pidroid.utils.embeds import PidroidEmbed, SuccessEmbed, ErrorEmbed
from pidroid.utils.file import Resource
from pidroid.utils.paginators import ListPageSource

NEKO_API = "https://nekos.life/api/v2"
NEKO_ENDPOINTS = [
    # Animals
    'goose', 'lizard', 'meow', 'woof',

    # Images
    'waifu', '8ball', 'gecg', 'avatar',
    'fox_girl', 'neko', 'wallpaper',

    # GIFs
    'slap', 'pat', 'feed', 'cuddle', 'hug',
    'tickle', 'smug', 'kiss',
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
    def __init__(self, data: list[WaifuSearchResult | Waifu]):
        super().__init__(data, per_page=1)
        self.embed = PidroidEmbed()

    @override
    async def format_page(self, menu: PaginatingView, waifu: WaifuSearchResult | Waifu):
        self.embed.clear_fields()
        assert not isinstance(menu.ctx.channel, PartialMessageable)
        if isinstance(waifu, WaifuSearchResult):
            waifu = await waifu.fetch_waifu()
        if waifu.is_nsfw:
            show_nsfw = isinstance(menu.ctx.channel, (DMChannel, GroupChannel)) or menu.ctx.channel.is_nsfw()
            self.embed.title = waifu.name + " [NSFW]"
            if not show_nsfw:
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
            self.embed.set_footer(text='Appears in: ' + waifu.series['name'])
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

class AnimeCommandCog(commands.Cog):
    """This class implements cog which contains commands for anime related APIs."""

    def __init__(self, client: Pidroid):
        super().__init__()
        self.client = client
        self.waifu_list_api = MyWaifuListAPI()

    @commands.command(
        name="yourebanned",
        category=RandomCategory,
        hidden=True
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True, attach_files=True)
    async def yourebanned_command(self, ctx: Context[Pidroid]):
        async with ctx.typing():
            return await ctx.reply(file=discord.File(Resource('you_were_banned.mp4')))

    @commands.group(
        name="neko",
        category=RandomCategory,
        hidden=True,
        invoke_without_command=True
    )
    @commands.bot_has_permissions(send_messages=True)
    async def neko_command(self, ctx: Context[Pidroid]):
        if ctx.invoked_subcommand is None:
            raise BadArgument((
                "Invalid neko subcommand specified. "
                "Please consult the help command."
            ))

    @neko_command.command(
        name='fact',
        brief='Tells a random fact as provided by the API.',
        category=RandomCategory,
    )
    @commands.bot_has_permissions(send_messages=True)
    async def neko_fact_command(self, ctx: Context[Pidroid]):
        async with await http.get(self.client, f"{NEKO_API}/fact") as r:
            data: dict[str, str] = await r.json()
        return await ctx.reply(embed=SuccessEmbed(data["fact"]))

    @neko_command.command(
        name='name',
        brief='Generates a random name from the API.',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def neko_name_command(self, ctx: Context[Pidroid]):
        async with await http.get(self.client, f"{NEKO_API}/name") as r:
            data: dict[str, str] = await r.json()
        return await ctx.reply(embed=SuccessEmbed(data["name"]))

    @neko_command.command(
        name='why',
        brief='Questions that make you think as provided by the API.',
        category=RandomCategory,
    )
    @commands.bot_has_permissions(send_messages=True)
    async def neko_why_command(self, ctx: Context[Pidroid]):
        async with await http.get(self.client, f"{NEKO_API}/why") as r:
            data: dict[str, str] = await r.json()
        return await ctx.reply(embed=SuccessEmbed(data["why"]))

    @neko_command.command(
        name='image',
        brief='Fetches an image for the specified type as provided by the API.',
        usage='[image type]',
        category=RandomCategory,
    )
    @commands.bot_has_permissions(send_messages=True)
    async def neko_image_command(self, ctx: Context[Pidroid], endpoint: Optional[str]):
        if endpoint is None:
            endpoint = random.choice(NEKO_ENDPOINTS) # nosec

        endpoint = endpoint.lower()
        if endpoint in NEKO_ENDPOINTS:
            async with await http.get(self.client, f"{NEKO_API}/img/{endpoint}") as r:
                data: dict[str, str] = await r.json()
            embed = SuccessEmbed()
            embed.set_image(url=data["url"])
            embed.set_footer(text=endpoint)
            return await ctx.reply(embed=embed)

        raise BadArgument(
            'Wrong image type specified. The allowed types are: `' + ', '.join(NEKO_ENDPOINTS) + '`.'
        )

    @commands.command(
        name="owo",
        brief='Returns the original input text, but in owo format.',
        usage='<text to be converted>',
        category=RandomCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def owo_command(self, ctx: Context[Pidroid], *, text: str):
        owo = get_owo(text)
        if len(owo) > 4096:
            raise BadArgument('The text is too long!')
        _ = await ctx.reply(embed=SuccessEmbed(owo))

    @owo_command.error
    async def on_owo_error(self, ctx: Context[Pidroid], error: Exception):
        if isinstance(error, MissingRequiredArgument):
            if error.param.name == "text":
                return await notify(ctx, "UwU, what do you want to owoify?")
        setattr(error, 'unhandled', True)

    @commands.command(
        brief='Returns a random waifu from MyWaifuList.',
        usage='[waifu to search]',
        category=RandomCategory,
        enabled=False,
        hidden=True
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.cooldown(rate=1, per=3.5, type=commands.BucketType.user)
    @commands.max_concurrency(number=1, per=commands.BucketType.user)
    async def waifu(self, ctx: Context[Pidroid], *, selection: Optional[str]):
        api = self.waifu_list_api

        waifus: list[Waifu] = []
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

        pages = PaginatingView(self.client, ctx=ctx, source=WaifuCommandPaginator(waifus))
        return await pages.send()

    @commands.command(
        name="animedia",
        brief="Fetches an anime themed GIF/image file from waifu.pics API.",
        usage="[media type]",
        category=RandomCategory,
    )
    @commands.bot_has_permissions(send_messages=True)
    async def anime_media_command(self, ctx: Context[Pidroid], endpoint: Optional[str]):
        if endpoint is None:
            endpoint = random.choice(WAIFU_PICS_ENDPOINTS) # nosec

        endpoint = endpoint.lower().strip()
        if endpoint not in WAIFU_PICS_ENDPOINTS:
            raise BadArgument((
                'Wrong media type specified. '
                'The allowed types are: `' + ', '.join(WAIFU_PICS_ENDPOINTS) + '`.'
            ))
        async with await http.get(self.client, f"{WAIFU_PICS_API}/{endpoint}") as r:
            data: dict[str, str] = await r.json()

        embed = SuccessEmbed()
        embed.set_image(url=data["url"])
        embed.set_footer(text=endpoint)
        await ctx.reply(embed=embed)

    @commands.command(
        name="weeb",
        category=RandomCategory,
        hidden=True
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.max_concurrency(number=1, per=commands.BucketType.guild, wait=True)
    @command_checks.is_theotown_guild()
    @commands.guild_only()
    async def weeb_command(self, ctx: Context[Pidroid]):
        for _ in range(7):
            await asyncio.sleep(random.randint(2, 5)) # nosec
            _ = await ctx.send(f"<@{JESSE_ID}>, you asked for it")


async def setup(client: Pidroid):
    await client.add_cog(AnimeCommandCog(client))
