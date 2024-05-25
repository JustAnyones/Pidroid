import logging

from discord.abc import GuildChannel
from discord.channel import TextChannel
from discord.ext import commands
from discord.guild import Guild
from discord.role import Role

from pidroid.client import Pidroid

logger = logging.getLogger("Pidroid")

class GuildConfigurationService(commands.Cog):
    """This class implements a cog for handling of events related to the event channel."""
    def __init__(self, client: Pidroid):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """This notifies the host of the bot that the client is ready to use."""
        await self.__fill_guild_prefix_cache()
        #assert self.client.user is not None
        #logger.info(f'{self.client.user.name} bot (build {self.client.full_version}) has started with the ID of {self.client.user.id}')

    async def __fill_guild_prefix_cache(self):
        """Fills the internal cache with guild prefixes."""
        logger.debug("Filling guild prefix cache")
        raw_configs = await self.client.api.fetch_guild_configurations()
        for config in raw_configs:
            self.client.update_guild_prefixes_from_config(config.guild_id, config)
        logger.debug("Guild prefix cache filled")

        # Generate configurations for guilds that do not already have it
        logger.debug("Generating missing guild configurations")
        for guild in self.client.guilds:
            prefixes = self.client.get_guild_prefixes(guild.id)
            # If there's no prefix entry, there's no guild configuration either
            if prefixes is None:
                config = await self.client.api.insert_guild_configuration(guild.id)
                self.client.update_guild_prefixes_from_config(guild.id, config)
                logger.warn(f"Guild \"{guild.name}\" ({guild.id}) did not have a guild configuration. Generated one automatically")

        self.client._guild_prefix_cache_ready.set()
        logger.debug("Guild prefix cache ready")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: Guild):
        await self.client.wait_until_guild_configurations_loaded()

        # Fetching guild configuration will ensure that the
        # configuration is created, if it didn't exist
        # and get cached
        await self.client.fetch_guild_configuration(guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: Guild):
        await self.client.wait_until_guild_configurations_loaded()

        config = await self.client.api.fetch_guild_configuration(guild.id)
        if config:
            await config.delete()
            self.client.remove_guild_prefixes(guild.id)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: Role) -> None:
        """Handles configuration updates based on role removals."""
        await self.client.wait_until_guild_configurations_loaded()

        guild_id = role.guild.id
        config = await self.client.fetch_guild_configuration(guild_id)
        if config.jail_role_id == role.id:
            await config.edit(jail_role_id=None)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, guild_channel: GuildChannel) -> None:
        """Handles configuration updates based on text channel removals."""
        # Only care about text channels, as Pidroid doesn't do anything moderative with
        # voice channels and etc
        if not isinstance(guild_channel, TextChannel):
            return

        await self.client.wait_until_guild_configurations_loaded()

        guild_id = guild_channel.guild.id
        config = await self.client.fetch_guild_configuration(guild_id)
        if config.jail_channel_id == guild_channel.id:
            await config.edit(jail_channel_id=None)


async def setup(client: Pidroid) -> None:
    await client.add_cog(GuildConfigurationService(client))
