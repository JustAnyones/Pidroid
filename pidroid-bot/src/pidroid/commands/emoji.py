import re

from discord.emoji import Emoji
from discord.errors import HTTPException
from discord.ext import commands
from discord.ext.commands import BadArgument, Context, MissingRequiredArgument, PartialEmojiConversionFailure
from discord.message import Message
from discord.partial_emoji import PartialEmoji

from pidroid.client import Pidroid
from pidroid.models.categories import UtilityCategory
from pidroid.services.error_handler import notify
from pidroid.utils import http
from pidroid.utils.embeds import PidroidEmbed

EMOJI_FIND_PATTERN = re.compile(r'<(a:.+?:\d+|:.+?:\d+)>')


def get_message_emojis(message: Message) -> list[PartialEmoji]:
    """Returns a list of PartialEmoji found in a message."""
    emojis = get_custom_emojis(message.clean_content)
    if len(emojis) == 0:
        raise BadArgument("I was not able to find any custom emojis in the referenced message!")
    return emojis

def get_custom_emojis(string: str) -> list[PartialEmoji]:
    """Returns a list of PartialEmoji found in a string."""
    emoji_list: list[str] = re.findall(EMOJI_FIND_PATTERN, string)
    if len(emoji_list) == 0:
        return []

    formatted: list[PartialEmoji] = []
    for emoji in emoji_list:
        animated, name, emoji_id = emoji.split(':')
        formatted.append(create_partial_emoji(name, animated == 'a', int(emoji_id)))
    return formatted

def create_partial_emoji(name: str, animated: bool, emoji_id: int) -> PartialEmoji:
    """Creates a PartialEmoji object from passed parameters."""
    return PartialEmoji(name=name, animated=animated, id=emoji_id)

def mention_emoji(emoji: Emoji | PartialEmoji) -> str:
    """Returns a string which can be used to mention an emoji."""
    return f"<{'a' if emoji.animated else ''}:{emoji.name}:{emoji.id}>"

def get_emoji_name(emoji: Emoji | PartialEmoji) -> str:
    """Returns a string which can be used to display emoji name with colons."""
    return f":\N{zero width space}{emoji.name}\N{zero width space}:"


class EmojiCommandCog(commands.Cog):
    """This class implements a cog for dealing with custom emojis."""

    def __init__(self, client: Pidroid):
        super().__init__()
        self.client = client

    @commands.command(
        name="emoji",
        brief='Displays the source image or the GIF of the specified custom emoji.',
        usage='<emoji>',
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def emoji_command(self, ctx: Context[Pidroid], emoji: PartialEmoji):
        embed = PidroidEmbed(title=get_emoji_name(emoji))
        _ = embed.set_image(url=emoji.url)
        return await ctx.reply(embed=embed)

    @emoji_command.error
    async def on_emoji_command_error(self, ctx: Context[Pidroid], error: Exception):
        if isinstance(error, MissingRequiredArgument):
            if error.param.name == "emoji":
                return await notify(ctx, "Please specify a custom emoji you want to view.")
        if isinstance(error, PartialEmojiConversionFailure):
            return await notify(ctx, f'"{error.argument}" is not a valid custom emoji.')
        setattr(error, 'unhandled', True)

    @commands.command(
        name='copy-emoji',
        brief='Retrieves the first emoji from a referenced message and adds it to server custom emoji list.',
        aliases=['steal-emoji', 'clone-emoji'],
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True, manage_emojis=True)
    @commands.has_permissions(manage_emojis=True)
    @commands.guild_only()
    async def copy_emoji_command(self, ctx: Context[Pidroid], message: Message | None, emoji_index: int = -1):
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
            raise BadArgument("Please select the correct index of the emoji you want to copy.")

        # Get emoji picture
        async with await http.get(self.client, str(partial_emoji.url)) as r:
            payload = await r.read()

        try:
            emoji: Emoji = await ctx.guild.create_custom_emoji(
                name=partial_emoji.name, image=payload,
                reason=f"Copied by {str(ctx.author)}"
            )
        except HTTPException as e:
            if e.code == 30008:
                raise BadArgument("The server emote list is full. I can't add more!")
            if e.status == 400:
                raise BadArgument("Error from Discord API:", str(e))
            raise e
        else:
            return await ctx.reply(f"Emoji {mention_emoji(emoji)} has been added!")

    @commands.command(
        name='get-emojis',
        brief='Retrieves all custom emojis from a referenced message.',
        aliases=['get-emoji'],
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def get_emojis_command(self, ctx: Context[Pidroid], message: Message | None, emoji_index: int = -1):
        if ctx.message.reference and ctx.message.reference.message_id:
            message = await ctx.channel.fetch_message(ctx.message.reference.message_id)

        message = message or ctx.message
        emojis = get_message_emojis(message)

        emote_count = len(emojis)
        if emote_count == 1:
            return await ctx.invoke(self.emoji_command, emoji=emojis[0])

        if 1 <= emoji_index <= emote_count:
            return await ctx.invoke(self.emoji_command, emoji=emojis[emoji_index - 1])

        # TODO: look into pagination
        embed = PidroidEmbed(title="Extracted custom emojis")

        for emoji in emojis:
            _ = embed.add_field(name=get_emoji_name(emoji), value=f"[View]({emoji.url})")

        return await ctx.reply(embed=embed)


async def setup(client: Pidroid) -> None:
    await client.add_cog(EmojiCommandCog(client))
