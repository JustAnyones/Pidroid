import asyncio
import datetime

from discord import File
from discord.message import Message
from discord.ext import commands # type: ignore
from random import randint

from pidroid.client import Pidroid
from pidroid.constants import JUSTANYONE_ID
from pidroid.cogs.utils.checks import is_guild_theotown
from pidroid.cogs.utils.file import Resource
from pidroid.cogs.utils.time import utcnow

def find_whole_word(word: str, string: str) -> bool:
    """Returns true if specified word is in the string."""
    return word in string.split()


LINUX_COPYPASTA: str = (
    "I’d just like to interject for a moment. What you’re refering to as Linux, "
    "is in fact, GNU/Linux, or as I’ve recently taken to calling it, GNU plus Linux. "
    "Linux is not an operating system unto itself, but rather another free component "
    "of a fully functioning GNU system made useful by the GNU corelibs, shell utilities "
    "and vital system components comprising a full OS as defined by POSIX.\n\n"

    "Many computer users run a modified version of the GNU system every day, without realizing it. "
    "Through a peculiar turn of events, the version of GNU which is widely used today is often called “Linux”, "
    "and many of its users are not aware that it is basically the GNU system, developed by the GNU Project.\n\n"

    "There really is a Linux, and these people are using it, but it is just a part of the system they use. "
    "Linux is the kernel: the program in the system that allocates the machine’s resources to the other programs "
    "that you run. The kernel is an essential part of an operating system, but useless by itself; it can only "
    "function in the context of a complete operating system. Linux is normally used in combination with the GNU "
    "operating system: the whole system is basically GNU with Linux added, or GNU/Linux. All the so-called “Linux” "
    "distributions are really distributions of GNU/Linux."
)

AMONG_US_COPYPASTA: str = (
    "Dear %USERNAME% (which to whom concerned is not his real name), to whom it may concern, "
    "has ultimately been deemed suspicious:\n\n"

    "It is without doubt that you should be hereby informed about your recent activity, "
    "which has raised concern among the TheoTown community. Said behavior, which has hereby "
    "been deemed suspicious, needs to be formally addressed. As of typing, this is your third and the "
    "last violation [of the rule] of having behaviors which resemble such of a “suspicious imposter” "
    "from the popular video game, “Among Us”. This unfathomably suspicious behavior holds the ability to "
    "segfault into all kinds of other harmful, if not suspicious activity. I, and the entirety of the TheoTown "
    "community, inform you, %USERNAME% (to whom it may concern, has ultimately been deemed suspicious), have "
    "been granted one last chance in order to stop such suspicious and borderline “uncool” behavior, in which "
    "again, resembles such “suspicious imposters” from the popular video game, “Among Us”, and to stop "
    "impersonating others. It is without hesitation that this will be your lastmost and final warning before "
    "punishment of any kind is to be enforced.\n\n"

    "Thou art suspicious\n"
    "jie"
)

class CopypastaEventHandler(commands.Cog): # type: ignore
    """This class implements a cog for handling invocation of copypastas and other memes invoked by events like on_message."""

    def __init__(self, client: Pidroid):
        self.client = client
        empty_date = datetime.datetime.utcfromtimestamp(0)
        self.cooldowns = {
            "ping_ja": empty_date,
            "linux": empty_date,
            "among_us": empty_date
        }

    def check_probability(self, x: int) -> bool:
        """Returns true if random integer produced by 1 and x is 1.

        Probability can be calculated by 1/x * 100%"""
        if x <= 0:
            raise ValueError("X value cannot be lower than 1!")
        return randint(1, x) == 1 # nosec

    def check_cooldown(self, key: str, cooldown: int) -> bool:
        """Returns true if cooldown has ended.

        Note that this immediately starts the cooldown."""
        last_exec = self.cooldowns[key]
        if utcnow().timestamp() - last_exec.timestamp() > cooldown:
            self.cooldowns[key] = utcnow()
            return True
        return False

    def is_linux(self, content: str) -> bool:
        """Returns true if message is worthy of GNU/Linux copypasta."""
        return (
            find_whole_word('linux', content)
            and not find_whole_word('gnu', content)
            and not find_whole_word('kernel', content)
        )

    def is_among_us(self, content: str) -> bool:
        """Returns true if message is worthy of among us copypasta."""
        return (
            find_whole_word('sus', content)
            or (
                find_whole_word('among', content)
                and find_whole_word('us', content))
        )

    @commands.Cog.listener() # type: ignore
    async def on_message(self, message: Message): # noqa: C901
        if message.author.bot or not message.guild or not is_guild_theotown(message.guild):
            return

        content = message.clean_content.lower()

        # Reply as Pidroid to JA's pings
        if message.author.id != JUSTANYONE_ID:
            if len(message.mentions) > 0 and any(mention.id == JUSTANYONE_ID for mention in message.mentions):
                if self.check_cooldown("ping_ja", 60 * 60 * 24):
                    await message.reply(file=File(Resource('ja ping.png')), delete_after=0.9)

        # Linux copypasta
        if self.is_linux(content):
            if self.check_cooldown("linux", 60 * 60 * 7):
                if self.check_probability(5): # 20%
                    async with message.channel.typing():
                        await asyncio.sleep(67)
                        await message.reply(LINUX_COPYPASTA, delete_after=120)
                    return

        # Sus copypasta
        if self.is_among_us(content):
            if self.check_cooldown("among_us", 60 * 60 * 5):
                if self.check_probability(10): # 10%
                    await message.reply(
                        AMONG_US_COPYPASTA.replace("%USERNAME%", message.author.name),
                        delete_after=120
                    )


async def setup(client: Pidroid) -> None:
    await client.add_cog(CopypastaEventHandler(client))
