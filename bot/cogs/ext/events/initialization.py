from discord import Game
from discord.ext import commands

from client import Pidroid
from cogs.utils.checks import is_client_pidroid
from cogs.utils.http import Route


class InvocationEventHandler(commands.Cog):
    """This class implements a cog for handling invocation of functions upon internal bot cache being prepared."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.log = self.client.logger

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """This notifies the host of the bot that the client is ready to use."""
        if is_client_pidroid(self.client):
            await self._fill_scavenger_hunt_data()
        await self._fill_guild_config_cache()
        print(f'{self.client.user.name} bot (build {self.client.full_version}) has started with the ID of {self.client.user.id}')
        await self.client.change_presence(activity=Game("TheoTown"))

    async def _fill_scavenger_hunt_data(self):
        """Get data for the scavenger hunt."""
        if self.client.scavenger_hunt["_loaded"]:
            return

        self.log.debug("Filling scavenger hunt data")
        data = await self.client.api.get(Route(
            "/private/20k/get_secrets"
        ))

        self.client.scavenger_hunt["full_message"] = data["message"]
        self.client.scavenger_hunt["secret_code"] = data["code"]

        self.client.scavenger_hunt["active"] = False # should be enabled manually
        self.client.scavenger_hunt["_loaded"] = True
        self.log.debug("Scavenger hunt data filled")

    async def _fill_guild_config_cache(self):
        self.log.debug("Filling guild configuration cache")
        raw_configs = await self.client.api.get_all_guild_configurations()
        for config in raw_configs:
            self.client._update_guild_configuration(config.guild_id, config)
        self.client._guild_config_ready.set()
        self.log.debug("Guild configuration cache filled")


def setup(client: Pidroid) -> None:
    client.add_cog(InvocationEventHandler(client))
