import logging

from discord import Game
from discord.ext import commands

from pidroid.client import Pidroid

logger = logging.getLogger("pidroid.services.presence")

class PresenceService(commands.Cog):
    def __init__(self, client: Pidroid):
        super().__init__()
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self.client.change_presence(activity=Game("TheoTown"))


async def setup(client: Pidroid) -> None:
    await client.add_cog(PresenceService(client))
