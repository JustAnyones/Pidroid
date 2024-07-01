import logging

from discord.ext import tasks, commands
from typing import override

from pidroid.client import Pidroid
from pidroid.constants import THEOTOWN_GUILD
from pidroid.utils.http import Route

logger = logging.getLogger("Pidroid")

class GuildStatisticsService(commands.Cog):
    """This class implements a cog for synchronizing TheoTown's guild member count with the TheoTown API."""

    def __init__(self, client: Pidroid) -> None:
        super().__init__()
        self.client = client
        _ = self.update_statistics.start()

    @override
    async def cog_unload(self):
        """Ensure that tasks are cancelled on cog unload."""
        self.update_statistics.cancel()

    @tasks.loop(seconds=300)
    async def update_statistics(self) -> None:
        """Updates TheoTown API with guild member count."""
        try:
            guild = self.client.get_guild(THEOTOWN_GUILD)
            if guild is None:
                return logger.warn("Unable to update discord server member count, TheoTown guild was not found")
            _ = await self.client.api.post(
                Route("/discord/statistics"),
                {"count": guild.member_count}
            )
        except Exception:
            logger.exception("An exception was encountered while trying to update guild statistics")

    @update_statistics.before_loop
    async def before_update_statistics(self) -> None:
        """Runs before update_statistics task to ensure that the task is ready to run."""
        await self.client.wait_until_ready()


async def setup(client: Pidroid) -> None:
    await client.add_cog(GuildStatisticsService(client))
