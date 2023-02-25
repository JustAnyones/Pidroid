from __future__ import annotations

import discord
import os
import typing
import sys

from discord.ext import commands # type: ignore
from discord.member import Member
from discord.message import Message
from discord.ext.commands import Greedy, Context # or a subclass of yours
from discord.ext.commands.context import Context # type: ignore
from discord.ext.commands.errors import BadArgument # type: ignore
from typing import TYPE_CHECKING, Optional
from typing_extensions import Annotated

from pidroid.client import Pidroid
from pidroid.constants import JUSTANYONE_ID
from pidroid.cogs.models.categories import OwnerCategory
from pidroid.cogs.utils.decorators import command_checks

class LevelCommands(commands.Cog): # type: ignore
    """This class implements a cog for special bot owner only commands."""
    def __init__(self, client: Pidroid) -> None:
        self.client = client
        
    async def try_earn_level(self, message: Message):
        # TODO: do some time checking, to avoid spam,
        # should return if it was under a minute
        
        assert message.guild is not None
        
        config = await self.client.fetch_guild_configuration(message.guild.id)
        
        
        await self.client.api.increase_member_level(message.guild.id, message.author.id, 0)
        
        
        
        pass

    #@commands.hybrid_command(name="level")
    #@commands.command( # type: ignore
    #    name="level",
    #    brief="Sends a message to a specified guild channel as the bot.",
    #    usage="<channel> <message>",
    #    aliases=["say"],
    #    permissions=["Bot owner"],
    #    category=OwnerCategory,
    #    hidden=True
    #)
    #@commands.is_owner() # type: ignore
    #@commands.bot_has_guild_permissions(send_messages=True) # type: ignore
    #async def level_command(self, ctx: Context, member: Annotated[Optional[Member], Member] = None):
    #    member = member or ctx.author
    #    await ctx.send(f"Querying level for {member}")
        
    #@commands.hybrid_command(name="leaderboard")
    #@commands.command( # type: ignore
    #    name="level",
    #    brief="Sends a message to a specified guild channel as the bot.",
    #    usage="<channel> <message>",
    #    aliases=["say"],
    #    permissions=["Bot owner"],
    #    category=OwnerCategory,
    #    hidden=True
    #)
    #@commands.is_owner() # type: ignore
    #@commands.bot_has_guild_permissions(send_messages=True) # type: ignore
    #async def leaderboard_command(self, ctx: Context):
    #    await ctx.send(f"Querying server leaderboard")

async def setup(client: Pidroid) -> None:
    await client.add_cog(LevelCommands(client))
