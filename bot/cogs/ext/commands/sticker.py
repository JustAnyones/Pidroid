import discord
import typing

from discord.enums import StickerFormatType
from discord.errors import HTTPException
from discord.ext import commands
from discord.ext.commands import Context
from discord.ext.commands.errors import BadArgument
from discord.message import Message
from discord.sticker import GuildSticker, StandardSticker, StickerItem
from io import BytesIO

from client import Pidroid
from cogs.models.categories import UtilityCategory
from cogs.utils import http
from cogs.utils.embeds import create_embed, error


def get_message_stickers(message: Message) -> typing.List[StickerItem]:
    """Returns a list of StickerItem found in a message."""
    stickers = message.stickers
    if len(stickers) == 0:
        raise BadArgument("I was not able to find any stickers in the message!")
    return stickers


class StickerCommands(commands.Cog):
    """This class implements a cog for dealing with sticker related commands."""

    def __init__(self, client: Pidroid):
        self.client = client

    @commands.command(
        hidden=True,
        name='clone-sticker',
        brief='Retrieves the sticker from a referenced message and adds it to server sticker list.',
        aliases=['steal-sticker', 'stealsticker', 'clonesticker'],
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True, manage_emojis_and_stickers=True)
    @commands.has_permissions(manage_emojis_and_stickers=True)
    @commands.guild_only()
    async def steal_sticker(self, ctx: Context, message: typing.Optional[Message]):
        raise BadArgument("This command is not yet supported.")

        if ctx.message.reference:
            message = await ctx.channel.fetch_message(ctx.message.reference.message_id)

        message = message or ctx.message

        sticker_items = get_message_stickers(message)
        sticker_item = sticker_items[0]

        sticker = await sticker_item.fetch()

        if isinstance(sticker, StandardSticker):
            raise BadArgument("Specified sticker is already in-built. It'd be dumb to add it again.")

        async with await http.get(self.client, str(sticker.url)) as r:
            with BytesIO(await r.read()) as f:
                discord_file = discord.File(f)

        try:
            # Returns bad request, possible problem with the library, henceforth, the command is disabled
            added_sticker: GuildSticker = await ctx.guild.create_sticker(
                name=sticker.name, emoji=sticker.emoji, file=discord_file,
                reason=f"Stolen by {ctx.author.name}#{ctx.author.discriminator}"
            )
        except HTTPException as exc:
            if exc.code == 30039:
                await ctx.reply(embed=error("The server sticker list is full. I can't add more!"))
                return
            raise exc
        else:
            await ctx.reply(f"Sticker {added_sticker.name} has been added!", stickers=[added_sticker])

    @commands.command(
        name='get-sticker',
        brief='Retrieves a sticker from a referenced message.',
        aliases=['getsticker'],
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def get_sticker(self, ctx: Context, message: typing.Optional[Message]):
        if ctx.message.reference:
            message = await ctx.channel.fetch_message(ctx.message.reference.message_id)

        message = message or ctx.message

        stickers = get_message_stickers(message)
        sticker = stickers[0]

        embed = create_embed(title=sticker.name)
        if sticker.format == StickerFormatType.lottie:
            embed.description = f"Sticker is a [Lottie](https://lottiefiles.com/what-is-lottie).\n{sticker.url}"
        else:
            embed.description = sticker.url
            embed.set_image(url=sticker.url)

        await ctx.reply(embed=embed)


def setup(client: Pidroid) -> None:
    client.add_cog(StickerCommands(client))
