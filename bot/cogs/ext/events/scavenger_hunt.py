import re

from discord.ext import commands
from discord.message import Message

from client import Pidroid
from cogs.utils.checks import is_client_pidroid

class ScavengerEventHandler(commands.Cog):
    """This class implements a cog for handling of events related to reactions."""
    def __init__(self, client: Pidroid):
        self.client = client
        self._pattern = None

    @property
    def pattern(self) -> re.Pattern:
        if self._pattern:
            return self._pattern
        self._pattern = re.compile(self.client.scavenger_hunt["pattern"], re.I)
        return self._pattern

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        """Listens to a message which contains the secret code."""
        if not is_client_pidroid(self.client):
            return

        if not self.client.scavenger_hunt["active"]:
            return

        # Disallow guilds
        if message.guild:
            return

        if message.author.bot:
            return

        if re.match(self.pattern, message.clean_content):
            code = self.client.scavenger_hunt["next_code"]
            return await message.reply(code)


def setup(client: Pidroid) -> None:
    client.add_cog(ScavengerEventHandler(client))
