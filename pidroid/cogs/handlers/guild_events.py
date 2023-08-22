from discord.abc import GuildChannel
from discord.channel import TextChannel
from discord.ext import commands # type: ignore
from discord.guild import Guild
from discord.role import Role

from pidroid.client import Pidroid

class GuildEventHandler(commands.Cog): # type: ignore
    """This class implements a cog for handling of events related to the event channel."""
    def __init__(self, client: Pidroid):
        self.client = client

    @commands.Cog.listener() # type: ignore
    async def on_guild_join(self, guild: Guild):
        await self.client.wait_until_guild_configurations_loaded()

        # Fetching guild configuration will ensure that the
        # configuration is created, if it didn't exist
        # and get cached
        await self.client.fetch_guild_configuration(guild.id)

    @commands.Cog.listener() # type: ignore
    async def on_guild_remove(self, guild: Guild):
        await self.client.wait_until_guild_configurations_loaded()

        config = await self.client.api.fetch_guild_configuration(guild.id)
        if config:
            await config.delete()
            self.client.remove_guild_prefixes(guild.id)

    @commands.Cog.listener() # type: ignore
    async def on_guild_role_delete(self, role: Role) -> None:
        """Handles configuration updates based on role removals."""
        await self.client.wait_until_guild_configurations_loaded()

        guild_id = role.guild.id
        config = await self.client.fetch_guild_configuration(guild_id)
        if config.jail_role_id == role.id:
            await config.edit(jail_role_id=None)

    @commands.Cog.listener() # type: ignore
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
    await client.add_cog(GuildEventHandler(client))
