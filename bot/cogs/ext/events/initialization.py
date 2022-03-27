from discord import Game
from discord.ext import commands
from typing import TYPE_CHECKING

from client import Pidroid

if TYPE_CHECKING:
    from cogs.ext.tasks.automod import AutomodTask


class InvocationEventHandler(commands.Cog):
    """This class implements a cog for handling invocation of functions upon internal bot cache being prepared."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.log = self.client.logger

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """This notifies the host of the bot that the client is ready to use."""
        self.annoy_erk = self.client.loop.create_task(self.client.annoy_erksmit())
        await self._fill_guild_config_cache()
        print(f'{self.client.user.name} bot (build {self.client.full_version}) has started with the ID of {self.client.user.id}')
        await self.client.change_presence(activity=Game("TheoTown"))

    def cog_unload(self) -> None:
        """Ensure that tasks are cancelled on cog unload."""
        self.annoy_erk.cancel()

    async def _fill_guild_config_cache(self):
        self.log.debug("Filling guild configuration cache")
        raw_configs = await self.client.api.get_all_guild_configurations()
        for config in raw_configs:
            self.client._update_guild_configuration(config.guild_id, config)

        # Also update phising URLS
        cog: AutomodTask = self.client.get_cog("AutomodTask")
        await cog._update_phising_urls()

        self.client._guild_config_ready.set()
        self.log.debug("Guild configuration cache filled")


async def setup(client: Pidroid) -> None:
    await client.add_cog(InvocationEventHandler(client))
