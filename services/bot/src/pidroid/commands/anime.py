import asyncio
import discord
import random
import re

from discord.ext import commands
from discord.ext.commands import BadArgument, Context, MissingRequiredArgument

from pidroid.client import Pidroid
from pidroid.constants import JESSE_ID
from pidroid.models.categories import RandomCategory
from pidroid.services.error_handler import notify
from pidroid.utils import http
from pidroid.utils.decorators import command_checks
from pidroid.utils.embeds import SuccessEmbed
from pidroid.utils.file import Resource

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
    async def neko_image_command(self, ctx: Context[Pidroid], endpoint: str | None):
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
        name="animedia",
        brief="Fetches an anime themed GIF/image file from waifu.pics API.",
        usage="[media type]",
        category=RandomCategory,
    )
    @commands.bot_has_permissions(send_messages=True)
    async def anime_media_command(self, ctx: Context[Pidroid], endpoint: str | None):
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
