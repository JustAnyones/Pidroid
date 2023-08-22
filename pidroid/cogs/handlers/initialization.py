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
        await self.__fill_guild_prefix_cache()
        self.log.info(f'{self.client.user.name} bot (build {self.client.full_version}) has started with the ID of {self.client.user.id}')
        await self.client.change_presence(activity=Game("TheoTown"))

    def cog_unload(self):
        """Ensure that tasks are cancelled on cog unload."""
        self.annoy_erk.cancel()

    async def __fill_guild_prefix_cache(self):
        """Fills the internal cache with guild prefixes."""
        self.log.debug("Filling guild prefix cache")
        raw_configs = await self.client.api.fetch_guild_configurations()
        for config in raw_configs:
            self.client.update_guild_prefixes_from_config(config.guild_id, config)
        self.log.debug("Guild prefix cache filled")

        # Generate configurations for guilds that do not already have it
        self.log.debug("Generating missing guild configurations")
        for guild in self.client.guilds:
            prefixes = self.client.get_guild_prefixes(guild.id)
            # If there's no prefix entry, there's no guild configuration either
            if prefixes is None:
                config = await self.client.api.insert_guild_configuration(guild.id)
                self.client.update_guild_prefixes_from_config(guild.id, config)
                self.log.warn(f"Guild \"{guild.name}\" ({guild.id}) did not have a guild configuration. Generated one automatically")

        self.client._guild_prefix_cache_ready.set()
        self.log.debug("Guild prefix cache ready")


async def setup(client: Pidroid) -> None:
    await client.add_cog(InvocationEventHandler(client))
