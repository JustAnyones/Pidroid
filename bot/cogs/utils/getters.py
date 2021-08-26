import discord

from typing import Optional

def get_role(guild: discord.Guild, role_id: int) -> Optional[discord.Role]:
    return guild.get_role(role_id)

def get_channel(guild: discord.Guild, channel_id: int) -> Optional[discord.abc.GuildChannel]:
    return guild.get_channel(channel_id)


def setup(client):
    pass

def teardown(client):
    pass
