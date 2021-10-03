import discord

from discord.abc import User
from discord.embeds import Embed, EmptyEmbed
from discord.member import Member
from typing import Union

from discord.message import Message
from discord.utils import escape_markdown


class BaseLog:

    def __init__(self) -> None:
        self.type = "Base log"
        self.embed = Embed(color=discord.Color.red())

    def __str__(self) -> str:
        return self.__class__.__name__

    def __repr__(self) -> Embed:
        return self.as_embed()

    def set_title(self, title: str) -> None:
        """Sets embed title."""
        self.embed.title = title

    def set_description(self, description: str) -> None:
        """Sets embed description."""
        self.embed.description = description

    def add_field(self, name: str, value: str, inline: bool = True) -> None:
        """Adds an embed field."""
        self.embed.add_field(name=name, value=value, inline=inline)

    def set_footer(self, text: str = EmptyEmbed, icon_url: str = EmptyEmbed) -> None:
        """Sets embed footer."""
        self.embed.set_footer(text=text, icon_url=icon_url)

    def set_type(self, log_type: str) -> None:
        """Sets log type. An alias for set_title."""
        self.set_title(log_type)

    def set_author(self, name: str, icon_url: str = EmptyEmbed) -> None:
        """Sets embed author."""
        self.embed.set_author(name=name, icon_url=icon_url)

    def put_author(self, user: Union[Member, User]) -> None:
        """Sets embed author and specifies the user ID in the footer."""
        self.set_author(str(user), user.avatar.url)
        self.embed.set_footer(text=f"User ID: {user.id}")

    def as_embed(self) -> Embed:
        """Returns embed representation of the object."""
        return self.embed

class SuspiciousUserLog(BaseLog):

    def __init__(self, member: Member, trigger_word: str) -> None:
        super().__init__()
        self.set_type("Suspicious member")
        self.put_author(member)
        self.embed.description = (
            f"A potentially suspicious user by the name of {member.mention} (ID: {member.id}) has joined the server.\n"
            "Due to a possibility of accidentally punishing an innocent user, you must decide the applicable action yourself.\n"
            f"This message has been triggered by the following word in the member's username: '{trigger_word}'"
        )

class PhisingLog(BaseLog):

    def __init__(self, message: Message, url: str = None) -> None:
        super().__init__()
        self.set_type("Phising detected")
        self.put_author(message.author)
        self.set_footer(f"User ID: {message.author.id} | False positive? Create an issue in the Pidroid Github repository")
        if url is not None:
            self.set_description(f"```{escape_markdown(message.content)}```")
            self.add_field("Blacklisted URL:", url)
        else:
            self.set_description("Phising dynamically detected inside the embed of the message")

class BannedWordLog(BaseLog):

    def __init__(self, message: Message, trigger_word: str) -> None:
        super().__init__()
        self.set_type("Banned word")
        self.put_author(message.author)
        self.set_description(f"```{escape_markdown(message.content)}```")
        self.add_field("Blacklisted word:", trigger_word)
