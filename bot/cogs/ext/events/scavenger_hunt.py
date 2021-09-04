import re

from discord.ext import commands
from discord.message import Message

from client import Pidroid
from cogs.utils.http import Route
from cogs.utils.checks import is_client_pidroid

class ScavengerEventHandler(commands.Cog):
    """This class implements a cog for handling of events related to reactions."""
    def __init__(self, client: Pidroid):
        self.client = client
        self._pattern = None

    async def obtain_next_code(self) -> dict:
        """Sends a request to the API to resolve next URL clue."""
        code = self.client.scavenger_hunt["secret_code"]
        response = await self.client.api.get(
            Route("/public/20k/resolve_code", {"code": code})
        )
        return response

    @property
    def pattern(self) -> re.Pattern:
        if self._pattern:
            return self._pattern
        self._pattern = re.compile(self.client.scavenger_hunt["secret_code"])
        return self._pattern

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        """Listens to a message which contains the secret code."""
        if not is_client_pidroid(self.client):
            return

        if not self.client.scavenger_hunt["active"]:
            return

        if message.author.bot:
            return

        if re.match(self.pattern, message.clean_content):
            res = await self.obtain_next_code()
            if res["success"]:
                next_url = res["url"]

                if not message.guild:
                    return await message.reply(next_url)

                if message.guild:
                    try:
                        await message.author.send(f"Hmm, what's this...\n{next_url}")
                    except: # noqa
                        await message.reply(next_url)


def setup(client: Pidroid) -> None:
    client.add_cog(ScavengerEventHandler(client))
