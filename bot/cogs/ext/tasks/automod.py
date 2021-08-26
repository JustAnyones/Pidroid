import random
import re

from discord import Member
from discord.ext import commands
from discord.channel import TextChannel
from discord.message import Message
from typing import Union
from urllib.parse import urlparse

from client import Pidroid
from constants import AUTOMODERATOR_RESPONSES
from cogs.utils.checks import is_guild_moderator, is_client_pidroid, is_theotown_guild

BANNED_WORDS = [
    "sex", "hitler", "dick", "cock",
    "porn", "fuck", "fucker", "tits",
    "vagina", "orgasm", "squirt",
    "shit", "scheis", "clit", "cunt",
    "bitch", "anal", "nazi", "nsdap",
    "penis", "fucking"
]

SUSPICIOUS_USERS = [
    'hitler', 'porn', 'nazi',
    'sairam'
]


def find_swearing(string: str) -> Union[str, None]:
    """Returns a word which was found to be a swear in a string."""
    for word in string.split():
        if word in BANNED_WORDS:
            return word
    return None

def clean_markdown(message_content: str) -> str:
    """Returns a string stripped of any markdown."""
    return re.sub(r"[^a-zA-Z0-9\s]", "", message_content) # Did I ever tell you how much I hate regex?


class AutomodTask(commands.Cog):
    """This class implements a cog for handling automatic moderation of the TheoTown guild."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.mod_channel: TextChannel = None

    @commands.Cog.listener()
    async def on_member_join(self, member: Member) -> None:
        """Checks whether new member is in suspicious user list."""
        if not is_client_pidroid(self.client):
            return

        if not is_theotown_guild(member.guild):
            return

        # Get mod channel
        if self.mod_channel is None:
            self.mod_channel = self.client.get_channel(367318260724531200)

        if any(ext in member.name.lower() for ext in SUSPICIOUS_USERS):
            await self.mod_channel.send((
                '**Warning**\n'
                f'A potentially suspicious user by the name of {member.mention} (ID: {member.id}) has joined the server.\n'
                'Due to a possibility of accidentally punishing an innocent user, you must decide the applicable action yourself.'
            ))

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        """Checks every new message if it contains a swear word."""
        if not is_client_pidroid(self.client):
            return

        if message.author.bot:
            return

        if not message.guild or not is_theotown_guild(message.guild):
            return

        if len(message.embeds) > 0:
            link_type_embeds = [e for e in message.embeds if e.type == "link"]

            for link_embed in link_type_embeds:
                if "nitro" in link_embed.title.lower() and "a wild gift appears" in link_embed.provider.name.lower():
                    url = urlparse(link_embed.url.lower())
                    if url.netloc != "discord.gift":
                        await message.reply("That nitro URL seems sussy!")
                        break

        # Bad word detector
        content = clean_markdown(message.clean_content.lower())
        word = find_swearing(content)
        if word is not None and not is_guild_moderator(message.guild, message.channel, message.author):
            self.client.logger.debug(f'"{word}" has been detected as a bad word in "{content}"')
            await message.delete(delay=0)
            await message.channel.send(random.choice(AUTOMODERATOR_RESPONSES).replace('%user%', message.author.mention), delete_after=3.5) # nosec


def setup(client: Pidroid) -> None:
    client.add_cog(AutomodTask(client))
