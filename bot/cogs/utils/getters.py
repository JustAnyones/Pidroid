import discord

from discord.ext.commands.context import Context
from discord.ext.commands.errors import BadArgument
from typing import List, Union

from client import Pidroid
from cogs.models.case import Case


async def get_user(client: Pidroid, user_id: int) -> Union[discord.User, discord.Member, int, None]:
    user = client.get_user(user_id)
    if user is None:
        try:
            user = await client.fetch_user(user_id)
        except discord.errors.NotFound:
            return user_id
    return user

async def _resolve_case(client: Pidroid, d: dict) -> Case:
    d["user"] = await client.resolve_user(d["user_id"])
    d["moderator"] = await client.resolve_user(d["moderator_id"])
    return Case(client.api, d)

async def get_case(ctx: Context, case_id: str) -> Union[Case, None]:
    client: Pidroid = ctx.bot
    c = await client.api.get_guild_case(ctx.guild.id, case_id)
    if c is None:
        raise BadArgument("Specified case could not be found!")
    return await _resolve_case(client, c)

async def get_modlogs(ctx: Context, user: Union[discord.Member, discord.User]) -> List[Case]:
    client: Pidroid = ctx.bot
    warnings = await client.api.get_moderation_logs(ctx.guild.id, user.id)
    return [await _resolve_case(client, w) for w in warnings]

async def get_warnings(ctx: Context, user: Union[discord.Member, discord.User]) -> List[Case]:
    client: Pidroid = ctx.bot
    warnings = await client.api.get_active_warnings(ctx.guild.id, user.id)
    return [await _resolve_case(client, w) for w in warnings]

async def get_all_warnings(ctx: Context, user: Union[discord.Member, discord.User]) -> List[Case]:
    client: Pidroid = ctx.bot
    warnings = await client.api.get_all_warnings(ctx.guild.id, user.id)
    return [await _resolve_case(client, w) for w in warnings]


def get_role(guild: discord.Guild, role_id: int) -> Union[discord.Role, None]:
    return guild.get_role(role_id)

def get_channel(guild: discord.Guild, channel_id: int) -> Union[discord.abc.GuildChannel, None]:
    return guild.get_channel(channel_id)


def setup(client):
    pass

def teardown(client):
    pass
