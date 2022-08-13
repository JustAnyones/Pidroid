from discord.ext import tasks, commands # type: ignore

from pidroid.client import Pidroid
from pidroid.constants import THEOTOWN_GUILD
from pidroid.cogs.utils.checks import is_client_pidroid
from pidroid.cogs.utils.http import Route

class GuildStatisticsTask(commands.Cog): # type: ignore
    """This class implements a cog for synchronizing TheoTown's guild member count with the TheoTown API."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.update_statistics.start()

    def cog_unload(self) -> None:
        """Ensure that tasks are cancelled on cog unload."""
        self.update_statistics.cancel()

    @tasks.loop(seconds=120)
    async def update_statistics(self) -> None:
        """Updates TheoTown API with guild member count."""
        try:
            guild = self.client.get_guild(THEOTOWN_GUILD)
            await self.client.api.get(Route(
                "/private/discord/update",
                {"type": "write", "member_count": guild.member_count}
            ))
        except Exception:
            self.client.logger.exception("An exception was encountered while trying to update guild statistics")

    @update_statistics.before_loop
    async def before_update_statistics(self) -> None:
        """Runs before update_statistics task to ensure that the task is allowed to run."""
        await self.client.wait_until_ready()
        if not is_client_pidroid(self.client):
            self.update_statistics.cancel()


async def setup(client: Pidroid) -> None:
    await client.add_cog(GuildStatisticsTask(client))
