import re

from discord.emoji import Emoji
from discord.errors import HTTPException
from discord.ext import commands
from discord.ext.commands import Context # type: ignore
from discord.ext.commands.errors import BadArgument # type: ignore
from discord.message import Message
from discord.partial_emoji import PartialEmoji
from typing import Optional, Union, List

from pidroid.client import Pidroid
from pidroid.models.categories import UtilityCategory
from pidroid.utils import http
from pidroid.utils.embeds import PidroidEmbed, ErrorEmbed

EMOJI_FIND_PATTERN = re.compile(r'<(a:.+?:\d+|:.+?:\d+)>')


def get_message_emojis(message: Message) -> List[PartialEmoji]:
    """Returns a list of PartialEmoji found in a message."""
    emojis = get_custom_emojis(message.clean_content)
    if len(emojis) == 0:
        raise BadArgument("I was not able to find any custom emojis in the referenced message!")
    return emojis

def get_custom_emojis(string: str) -> List[PartialEmoji]:
    """Returns a list of PartialEmoji found in a string."""
    emoji_list = re.findall(EMOJI_FIND_PATTERN, string)
    if len(emoji_list) == 0:
        return []

    for i, emoji in enumerate(emoji_list):
        animated, name, emoji_id = emoji.split(':')
        emoji_list[i] = create_partial_emoji(name, animated == 'a', emoji_id)
    return emoji_list

def create_partial_emoji(name: str, animated: bool, emoji_id: int) -> PartialEmoji:
    """Creates a PartialEmoji object from passed parameters."""
    return PartialEmoji(name=name, animated=animated, id=emoji_id)

def mention_emoji(emoji: Union[Emoji, PartialEmoji]) -> str:
    """Returns a string which can be used to mention an emoji."""
    return f"<{'a' if emoji.animated else ''}:{emoji.name}:{emoji.id}>"

def get_emoji_name(emoji: Union[Emoji, PartialEmoji]) -> str:
    """Returns a string which can be used to display emoji name with colons."""
    return f":\N{zero width space}{emoji.name}\N{zero width space}:"


class EmojiCommands(commands.Cog): # type: ignore
    """This class implements a cog for dealing with emoji related commands."""

    def __init__(self, client: Pidroid):
        self.client = client

    @commands.command( # type: ignore
        brief='Displays the image or the GIF file of the emoji.',
        usage='<emoji>',
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def emoji(self, ctx: Context, *, emoji: Optional[PartialEmoji]):
        if emoji is None:
            raise BadArgument('Please specify a custom emoji you want to view!')

        embed = PidroidEmbed(title=get_emoji_name(emoji))
        embed.set_image(url=emoji.url)
        await ctx.reply(embed=embed)

    @commands.command( # type: ignore
        name='clone-emoji',
        brief='Retrieves the first emoji from a referenced message and adds it to server custom emoji list.',
        aliases=['steal-emoji', 'stealemoji', 'cloneemoji'],
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True, manage_emojis=True) # type: ignore
    @commands.has_permissions(manage_emojis=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def steal_emoji(self, ctx: Context, message: Optional[Message], emoji_index: int = -1):
        assert ctx.guild is not None
        if ctx.message.reference and ctx.message.reference.message_id:
            message = await ctx.channel.fetch_message(ctx.message.reference.message_id)

        message = message or ctx.message
        emojis = get_message_emojis(message)

        emote_count = len(emojis)
        if emote_count == 1:
            partial_emoji = emojis[0]
        elif 1 <= emoji_index <= emote_count:
            partial_emoji = emojis[emoji_index - 1]
        else:
            raise BadArgument("Please select the correct index of the emoji you want to steal")

        # Get emoji picture
        async with await http.get(self.client, str(partial_emoji.url)) as r:
            payload = await r.read()

        try:
            emoji: Emoji = await ctx.guild.create_custom_emoji(
                name=partial_emoji.name, image=payload,
                reason=f"Stolen by {ctx.author.name}#{ctx.author.discriminator}"
            )
        except HTTPException as e:
            if e.code == 30008:
                return await ctx.reply(embed=ErrorEmbed("The server emote list is full. I can't add more!"))
            raise e
        else:
            await ctx.reply(f"Emoji {mention_emoji(emoji)} has been added!")

    @commands.command( # type: ignore
        name='get-emojis',
        brief='Retrieves all custom emojis from a referenced message.',
        aliases=['getemojis', 'get-emoji', 'getemoji'],
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def get_emojis(self, ctx: Context, message: Optional[Message], emoji_index: int = -1):
        if ctx.message.reference and ctx.message.reference.message_id:
            message = await ctx.channel.fetch_message(ctx.message.reference.message_id)

        message = message or ctx.message
        emojis = get_message_emojis(message)

        emote_count = len(emojis)
        if emote_count == 1:
            await ctx.invoke(self.emoji, emoji=emojis[0])
            return

        if 1 <= emoji_index <= emote_count:
            await ctx.invoke(self.emoji, emoji=emojis[emoji_index - 1])
            return

        # TODO: look into pagination
        embed = PidroidEmbed(title="Extracted custom emojis")

        for emoji in emojis:
            embed.add_field(name=get_emoji_name(emoji), value=f"[View]({emoji.url})")

        await ctx.reply(embed=embed)


async def setup(client: Pidroid) -> None:
    await client.add_cog(EmojiCommands(client))
