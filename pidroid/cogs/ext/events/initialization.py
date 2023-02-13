from __future__ import annotations

from discord import Game
from discord.ext import commands # type: ignore
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pidroid.client import Pidroid


class InvocationEventHandler(commands.Cog): # type: ignore
    """This class implements a cog for handling invocation of functions upon internal bot cache being prepared."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.log = self.client.logger

    @commands.Cog.listener() # type: ignore
    async def on_ready(self) -> None:
        """This notifies the host of the bot that the client is ready to use."""
        assert self.client.user is not None
        self.annoy_erk = self.client.loop.create_task(self.client.annoy_erksmit())
        await self._fill_guild_config_cache()
        self.log.info(f'{self.client.user.name} bot (build {self.client.full_version}) has started with the ID of {self.client.user.id}')
        await self.client.change_presence(activity=Game("TheoTown"))

    def cog_unload(self):
        """Ensure that tasks are cancelled on cog unload."""
        self.annoy_erk.cancel()

    async def _fill_guild_config_cache(self):
        self.log.debug("Filling guild configuration cache")
        raw_configs = await self.client.api.fetch_guild_configurations()
        for config in raw_configs:
            self.client._update_guild_configuration(config.guild_id, config)
        self.log.debug("Guild configuration cache filled")

        # Generate configurations for guilds that do not already have it
        for guild in self.client.guilds:
            config = self.client.get_guild_configuration(guild.id)
            if config is None:
                config = await self.client.api.insert_guild_configuration(guild.id)
                self.client._update_guild_configuration(guild.id, config)
                self.log.warn(f"Guild \"{guild.name}\" ({guild.id}) did not have a guild configuration. Generated one automatically")

        self.client._guild_config_ready.set()
        self.log.debug("Guild configuration cache ready")


async def setup(client: Pidroid) -> None:
    await client.add_cog(InvocationEventHandler(client))
