import discord
import typing

from discord.enums import StickerFormatType
from discord.errors import HTTPException
from discord.ext import commands
from discord.ext.commands import Context # type: ignore
from discord.ext.commands.errors import BadArgument # type: ignore
from discord.message import Message
from discord.sticker import GuildSticker, StandardSticker, StickerItem
from io import BytesIO

from pidroid.client import Pidroid
from pidroid.cogs.models.categories import UtilityCategory
from pidroid.cogs.utils.embeds import PidroidEmbed, ErrorEmbed


def get_message_stickers(message: Message) -> typing.List[StickerItem]:
    """Returns a list of StickerItem found in a message."""
    stickers = message.stickers
    if len(stickers) == 0:
        raise BadArgument("I was not able to find any stickers in the message!")
    return stickers


class StickerCommands(commands.Cog): # type: ignore
    """This class implements a cog for dealing with sticker related commands."""

    def __init__(self, client: Pidroid):
        self.client = client

    @commands.command( # type: ignore
        name='clone-sticker',
        brief='Retrieves the sticker from a referenced message and adds it to server sticker list.',
        aliases=['steal-sticker', 'stealsticker', 'clonesticker'],
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True, manage_emojis_and_stickers=True) # type: ignore# type: ignore
    @commands.has_permissions(manage_emojis_and_stickers=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def steal_sticker(self, ctx: Context, message: typing.Optional[Message]):
        assert ctx.guild is not None
        if ctx.message.reference:
            message = await ctx.channel.fetch_message(ctx.message.reference.message_id)

        message = message or ctx.message

        sticker_items = get_message_stickers(message)
        sticker_item = sticker_items[0]

        sticker = await sticker_item.fetch()

        if isinstance(sticker, StandardSticker):
            raise BadArgument("Specified sticker is already in-built. It'd be dumb to add it again.")

        assert isinstance(sticker, GuildSticker)

        b = BytesIO(await sticker.read())
        try:
            # Returns bad request, possible problem with the library, henceforth, the command is disabled
            added_sticker: GuildSticker = await ctx.guild.create_sticker(
                name=sticker.name, description=sticker.description, emoji=sticker.emoji, file=discord.File(b),
                reason=f"Stolen by {ctx.author.name}#{ctx.author.discriminator}"
            )
            b.close()
        except HTTPException as exc:
            if exc.code == 30039:
                return await ctx.reply(embed=ErrorEmbed("The server sticker list is full. I can't add more!"))
            raise exc
        else:
            await ctx.reply(f"Sticker {added_sticker.name} has been added!", stickers=[added_sticker])

    @commands.command( # type: ignore
        name='get-sticker',
        brief='Retrieves a sticker from a referenced message.',
        aliases=['getsticker'],
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def get_sticker(self, ctx: Context, message: typing.Optional[Message]):
        if ctx.message.reference:
            message = await ctx.channel.fetch_message(ctx.message.reference.message_id)

        message = message or ctx.message

        stickers = get_message_stickers(message)
        sticker = stickers[0]

        embed = PidroidEmbed(title=sticker.name)
        if sticker.format == StickerFormatType.lottie:
            embed.description = f"Sticker is a [Lottie](https://lottiefiles.com/what-is-lottie).\n{sticker.url}"
        else:
            embed.description = sticker.url
            embed.set_image(url=sticker.url)

        await ctx.reply(embed=embed)


async def setup(client: Pidroid) -> None:
    await client.add_cog(StickerCommands(client))
