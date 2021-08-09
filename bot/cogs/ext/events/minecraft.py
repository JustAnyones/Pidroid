import re
import pytz

from discord import Member
from datetime import datetime
from discord.ext import commands
from discord.message import Message

from client import Pidroid
from constants import MINECRAFT_LISTENER_CHANNEL, MINECRAFT_LISTENER_GUILD, MINECRAFT_LISTENER_USER


REMOVE_IP_PATTERN = re.compile(r'\b(?!(10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|192\.168))(?:(?:2(?:[0-4][0-9]|5[0-5])|[0-1]?[0-9]?[0-9])\.){3}(?:(?:2([0-4][0-9]|5[0-5])|[0-1]?[0-9]?[0-9]))\b')  # noqa: E501


def is_command(text: str) -> bool:
    """Returns true if specified message is a command."""
    return text.startswith("pp")

def is_chatbot(member: Member) -> bool:
    """Returns true if specified member is minecraft bot."""
    return member.id == MINECRAFT_LISTENER_USER

async def handle_command(message: str, command: str, **args) -> str:
    """Handles passed command and returns the result as string."""
    if command == "time":
        # Lithuanian time which also supports DST, god I hate timezones and such sh*t
        utc = pytz.timezone('UTC')
        now = utc.localize(datetime.utcnow())
        today = now.astimezone(pytz.timezone('EET'))
        return f'Current time in Lithuania: {today.strftime("%Y-%m-%d %H:%M:%S")}'
    if command == "username":
        return f'Your Minecraft username is {message.content.split()[0]}'
    if command == "help":
        return 'PPtime - displays time in Lithuania\nPPusername - displays your Minecraft username as is known to the bot'
    return f'Minecraft command executor couldn\'t find the executor for "{command}" command!'


class MinecraftEventHandler(commands.Cog):
    """This class implements a cog for event handling related to Minecraft."""

    def __init__(self, client: Pidroid):
        self.client = client

    @commands.Cog.listener()
    async def on_message(self, message: Message): # noqa C901
        if not message.guild:
            return

        # Handles Lobster's Kitchen in-game command responder
        if message.guild.id != MINECRAFT_LISTENER_GUILD:
            return

        channel = message.channel
        if channel.id != MINECRAFT_LISTENER_CHANNEL:
            return

        if not is_chatbot(message.author):
            return

        if not message.embeds:
            username = message.content.split()[0]
            content = message.content
            authorised = "JustAnyone"
            text = content.split()[2].lower()

            if not is_command(text):
                return

            if content.startswith(f'{authorised} »'):
                await channel.send(await handle_command(message, text[2:]))
                return

            if content.startswith(f'{username} »'):
                await channel.send("PP not worthy enough")


def setup(client: Pidroid) -> None:
    client.add_cog(MinecraftEventHandler(client))
