from __future__ import annotations

import discord
import os
import typing
import sys

from discord.ext import commands # type: ignore
from discord.ext.commands.context import Context  # type: ignore
from discord.ext.commands.errors import BadArgument

from pidroid.client import Pidroid
from pidroid.constants import JUSTANYONE_ID
from pidroid.models.categories import OwnerCategory
from pidroid.utils.data import PersistentDataStore
from pidroid.utils.decorators import command_checks
from pidroid.utils.embeds import ErrorEmbed

class OwnerCommands(commands.Cog): # type: ignore
    """This class implements a cog for special bot owner only commands."""
    def __init__(self, client: Pidroid) -> None:
        self.client = client

    @commands.command( # type: ignore
        brief="Sends a message to a specified guild channel as the bot.",
        usage="<channel> <message>",
        aliases=["say"],
        category=OwnerCategory,
        hidden=True
    )
    @commands.is_owner() # type: ignore
    @commands.bot_has_guild_permissions(send_messages=True, manage_messages=True) # type: ignore
    async def speak(self, ctx: Context, channel: discord.TextChannel, *, message: str):
        try:
            await ctx.message.delete(delay=0)
            await channel.send(message)
        except Exception as e:
            await ctx.reply(embed=ErrorEmbed(str(e)))

    @commands.command( # type: ignore
        brief="Set the bot's playing game status to the specified game.",
        usage="<game>",
        aliases=["setgame", "play"],
        category=OwnerCategory
    )
    @commands.is_owner() # type: ignore
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def playgame(self, ctx: Context, *, game: str):
        await self.client.change_presence(activity=discord.Game(game))
        await ctx.reply(f"Now playing {game}!")

    @commands.command( # type: ignore
        brief="Stops the bot by killing the process with a SIGKILL signal.",
        aliases=["pulltheplug", "shutdown"],
        category=OwnerCategory
    )
    @command_checks.can_shutdown_bot()
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def stop(self, ctx: Context):
        user = await self.client.get_or_fetch_user(JUSTANYONE_ID)
        self.client.logger.critical(f'Kill request received by {ctx.message.author}')
        if user:
            await user.send(f'The bot was manually shut down by {ctx.message.author}')
        await ctx.reply('Shutting down!')
        # Thank you, windows, very kool
        if sys.platform == 'win32':
            from signal import SIGTERM
            os.kill(os.getpid(), SIGTERM)
        else:
            from signal import SIGKILL
            os.kill(os.getpid(), SIGKILL)

    @commands.command( # type: ignore
        brief="Sends a message to the specified user as the bot.",
        usage="<user> <message>",
        category=OwnerCategory,
        hidden=True
    )
    @commands.is_owner() # type: ignore
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def dm(self, ctx: Context, user: typing.Union[discord.Member, discord.User], *, message: str):
        await user.send(message)
        await ctx.reply(f"Message to {str(user)} was sent succesfully")

    @commands.command(
        name="show-data-store",
        category=OwnerCategory,
        hidden=True
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def show_data_store_command(self, ctx: Context):
        string = ""
        async with PersistentDataStore() as store:
            for key in await store.keys():
                val = await store.get(key)
                string += f"{key}: {val}\n"
        await ctx.reply(
            f"Displaying values stored in persistent data store:\n\n{string.strip()}"
        )

    @commands.command(
        name="set-data-store",
        category=OwnerCategory,
        hidden=True
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def set_data_store_command(self, ctx: Context, key: str, value: str):
        async with PersistentDataStore() as store:
            await store.set(key, value)
        await ctx.reply(
            f"Set the data store value with key '{key}' to '{value}'"
        )

    @commands.command(
        name="get-data-store",
        category=OwnerCategory,
        hidden=True
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def get_data_store_command(self, ctx: Context, key: str):
        async with PersistentDataStore() as store:
            value = await store.get(key)
        if value is None:
            raise BadArgument(f"Data store does not have a value for key '{key}'")
        await ctx.reply(
            f"The data store value for key '{key}' is {value}"
        )

async def setup(client: Pidroid) -> None:
    await client.add_cog(OwnerCommands(client))
