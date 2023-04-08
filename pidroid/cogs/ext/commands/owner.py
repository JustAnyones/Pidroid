from __future__ import annotations

import discord
import os
import typing
import sys

from discord.ext import commands # type: ignore
from discord.ext.commands.context import Context  # type: ignore

from pidroid.client import Pidroid
from pidroid.constants import JUSTANYONE_ID
from pidroid.cogs.models.categories import OwnerCategory
from pidroid.cogs.utils.decorators import command_checks
from pidroid.cogs.utils.embeds import ErrorEmbed

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
        user = self.client.get_user(JUSTANYONE_ID)
        print(f'Kill request received by {ctx.message.author}')
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
        await ctx.reply(f"Message to {user.name}#{user.discriminator} was sent succesfully")

async def setup(client: Pidroid) -> None:
    await client.add_cog(OwnerCommands(client))
