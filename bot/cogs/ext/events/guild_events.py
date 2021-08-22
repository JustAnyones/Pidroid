from discord.abc import GuildChannel
from discord.channel import TextChannel
from discord.ext import commands
from discord.guild import Guild
from discord.role import Role

from client import Pidroid
from cogs.utils.checks import is_client_development

class GuildEventHandler(commands.Cog):
    """This class implements a cog for handling of events related to the event channel."""
    def __init__(self, client: Pidroid):
        self.client = client
        self.api = self.client.api

    @commands.Cog.listener()
    async def on_guild_join(self, guild: Guild):
        if is_client_development(self.client):
            return

        await self.client.wait_guild_config_cache_ready()

        if guild.id in self.client.guild_configuration_guilds:
            return

        config = await self.api.create_new_guild_configuration(guild.id)
        self.client._update_guild_configuration(guild.id, config)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: Guild):
        if is_client_development(self.client):
            return

        await self.client.wait_guild_config_cache_ready()

        if guild.id not in self.client.guild_configuration_guilds:
            return

        config = self.client.get_guild_configuration(guild.id)
        await self.api.delete_guild_configuration(config._id)
        self.client._remove_guild_configuration(guild.id)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: Role) -> None:
        """Handles configuration updates based on role removals."""
        if is_client_development(self.client):
            return

        await self.client.wait_guild_config_cache_ready()

        guild_id = role.guild.id
        if guild_id not in self.client.guild_configuration_guilds:
            return

        config = self.client.get_guild_configuration(guild_id)
        if config.jail_role == role.id:
            await config.update_jail_role(None)
        elif config.mute_role == role.id:
            await config.update_mute_role(None)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, guild_channel: GuildChannel) -> None:
        """Handles configuration updates based on text channel removals."""
        # Only care about text channels, as Pidroid doesn't do anything moderative with
        # voice channels and etc
        if not isinstance(guild_channel, TextChannel):
            return

        if is_client_development(self.client):
            return

        await self.client.wait_guild_config_cache_ready()

        guild_id = guild_channel.guild.id
        if guild_id not in self.client.guild_configuration_guilds:
            return

        config = self.client.get_guild_configuration(guild_id)
        if config.jail_channel == guild_channel.id:
            await config.update_jail_channel(None)


def setup(client: Pidroid) -> None:
    client.add_cog(GuildEventHandler(client))
