import asyncio

from discord import File
from discord.message import Message
from discord.ext import commands
from random import randint
from time import time

from client import Pidroid
from constants import JUSTANYONE_ID
from cogs.utils.checks import is_client_pidroid, is_theotown_guild

def find_whole_word(word: str, string: str) -> bool:
    """Returns true if specified word is in the string."""
    return word in string.split()

class CopypastaEventHandler(commands.Cog):
    """This class implements a cog for handling invocation of copypastas and other memes invoked by events like on_message."""

    def __init__(self, client: Pidroid):
        self.client = client
        self.ja_ping_cooldown = int(time())
        self.linux_copypasta_cooldown = int(time())

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if not is_client_pidroid(self.client):
            return

        if message.author.bot:
            return

        if not message.guild or not is_theotown_guild(message.guild):
            return

        current_time = int(time())
        content = message.clean_content.lower()

        # Reply as Pidroid to JA's pings
        if message.author.id != JUSTANYONE_ID:
            if len(message.mentions) > 0 and any(mention.id == JUSTANYONE_ID for mention in message.mentions):
                if (current_time - self.ja_ping_cooldown) > 60 * 60 * 24:
                    self.ja_ping_cooldown = current_time
                    await message.reply(file=File('./resources/ja ping.png'), delete_after=0.8)

        # Linux copypasta
        if find_whole_word('linux', content) and not find_whole_word('gnu', content) and not find_whole_word('kernel', content):
            if (current_time - self.linux_copypasta_cooldown) > 60 * 60 * 5:
                self.linux_copypasta_cooldown = current_time
                if randint(1, 4) != 5:
                    return
                async with message.channel.typing():
                    await asyncio.sleep(67)
                    await message.reply("""I’d just like to interject for a moment. What you’re refering to as Linux, is in fact, GNU/Linux, or as I’ve recently taken to calling it, GNU plus Linux. Linux is not an operating system unto itself, but rather another free component of a fully functioning GNU system made useful by the GNU corelibs, shell utilities and vital system components comprising a full OS as defined by POSIX.\n\nMany computer users run a modified version of the GNU system every day, without realizing it. Through a peculiar turn of events, the version of GNU which is widely used today is often called “Linux”, and many of its users are not aware that it is basically the GNU system, developed by the GNU Project.\n\nThere really is a Linux, and these people are using it, but it is just a part of the system they use. Linux is the kernel: the program in the system that allocates the machine’s resources to the other programs that you run. The kernel is an essential part of an operating system, but useless by itself; it can only function in the context of a complete operating system. Linux is normally used in combination with the GNU operating system: the whole system is basically GNU with Linux added, or GNU/Linux. All the so-called “Linux” distributions are really distributions of GNU/Linux.""", delete_after=120)


def setup(client: Pidroid) -> None:
    client.add_cog(CopypastaEventHandler(client))
