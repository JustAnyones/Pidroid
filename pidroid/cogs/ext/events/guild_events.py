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
        await self.client.wait_guild_config_cache_ready()

        if self.client.get_guild_configuration(guild.id):
            return

        config = await self.client.api.insert_guild_configuration(guild.id)
        self.client._update_guild_configuration(guild.id, config)

    @commands.Cog.listener() # type: ignore
    async def on_guild_remove(self, guild: Guild):
        await self.client.wait_guild_config_cache_ready()

        config = self.client.get_guild_configuration(guild.id)
        if config is None:
            return

        await self.client.api.delete_guild_configuration(config._id)
        self.client._remove_guild_configuration(guild.id)

    @commands.Cog.listener() # type: ignore
    async def on_guild_role_delete(self, role: Role) -> None:
        """Handles configuration updates based on role removals."""
        await self.client.wait_guild_config_cache_ready()

        guild_id = role.guild.id
        config = self.client.get_guild_configuration(guild_id)
        if config is None:
            return

        if config.jail_role == role.id:
            await config.update_jail_role(None)

    @commands.Cog.listener() # type: ignore
    async def on_guild_channel_delete(self, guild_channel: GuildChannel) -> None:
        """Handles configuration updates based on text channel removals."""
        # Only care about text channels, as Pidroid doesn't do anything moderative with
        # voice channels and etc
        if not isinstance(guild_channel, TextChannel):
            return

        await self.client.wait_guild_config_cache_ready()

        guild_id = guild_channel.guild.id
        if self.client.get_guild_configuration(guild_id):
            return

        config = self.client.get_guild_configuration(guild_id)
        if config is None:
            return
        if config.jail_channel == guild_channel.id:
            await config.update_jail_channel(None)


async def setup(client: Pidroid) -> None:
    await client.add_cog(GuildEventHandler(client))
