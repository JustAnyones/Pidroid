from __future__ import annotations

import aiofiles
import discord
import logging
import os
import sys

from discord.ext import commands
from discord.ext.commands.context import Context 
from discord.ext.commands.errors import BadArgument

from pidroid.client import Pidroid
from pidroid.constants import JUSTANYONE_ID, TEMPORARY_FILE_PATH
from pidroid.models.categories import OwnerCategory
from pidroid.modules.core.ui.opt.view import ImplView
from pidroid.utils.aliases import DiscordUser
from pidroid.utils.checks import member_has_guild_permission
from pidroid.utils.data import PersistentDataStore
from pidroid.utils.decorators import command_checks
from pidroid.utils.embeds import ErrorEmbed

logger = logging.getLogger('Pidroid')

class OwnerCommandCog(commands.Cog):
    """This class implements a cog for special bot owner only commands."""
    
    def __init__(self, client: Pidroid) -> None:
        super().__init__()
        self.client = client

    @commands.command(
        brief="Sends a message to a specified guild channel as the bot.",
        usage="<channel> <message>",
        aliases=["say"],
        category=OwnerCategory,
        hidden=True
    )
    @commands.is_owner()
    @commands.bot_has_guild_permissions(send_messages=True, manage_messages=True)
    async def speak(self, ctx: Context[Pidroid], channel: discord.TextChannel, *, message: str):
        try:
            await ctx.message.delete(delay=0)
            return await channel.send(message)
        except Exception as e:
            return await ctx.reply(embed=ErrorEmbed(str(e)))

    @commands.command(
        brief="Set the bot's playing game status to the specified game.",
        usage="<game>",
        aliases=["setgame", "play"],
        category=OwnerCategory
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def playgame(self, ctx: Context[Pidroid], *, game: str):
        await self.client.change_presence(activity=discord.Game(game))
        return await ctx.reply(f"Now playing {game}!")

    @commands.command(
        brief="Stops the bot by killing the process with a SIGKILL signal.",
        aliases=["pulltheplug", "shutdown"],
        category=OwnerCategory
    )
    @command_checks.can_shutdown_bot()
    @commands.bot_has_permissions(send_messages=True)
    async def stop(self, ctx: Context[Pidroid]):
        user = await self.client.get_or_fetch_user(JUSTANYONE_ID)
        logger.critical(f'Kill request received by {ctx.message.author}')
        if user:
            _ = await user.send(f'The bot was manually shut down by {ctx.message.author}')
        _ = await ctx.reply('Shutting down!')
        # Thank you, windows, very kool
        if sys.platform == 'win32':
            from signal import SIGTERM
            os.kill(os.getpid(), SIGTERM)
        else:
            from signal import SIGKILL
            os.kill(os.getpid(), SIGKILL)

    @commands.command(
        brief="Sends a message to the specified user as the bot.",
        usage="<user> <message>",
        category=OwnerCategory,
        hidden=True
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def dm(self, ctx: Context[Pidroid], user: DiscordUser, *, message: str):
        _ = await user.send(message)
        _ = await ctx.reply(f"Message to {str(user)} was sent successfully")

    @commands.command(
        name="show-data-store",
        category=OwnerCategory,
        hidden=True
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def show_data_store_command(self, ctx: Context[Pidroid]):
        string = ""
        async with PersistentDataStore() as store:
            for key in await store.keys():
                val = await store.get(key)
                string += f"{key}: {val}\n"
        return await ctx.reply(
            f"Displaying values stored in persistent data store:\n\n{string.strip()}"
        )

    @commands.command(
        name="set-data-store",
        category=OwnerCategory,
        hidden=True
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def set_data_store_command(self, ctx: Context[Pidroid], key: str, value: str):
        async with PersistentDataStore() as store:
            await store.set(key, value)
        return await ctx.reply(
            f"Set the data store value with key '{key}' to '{value}'"
        )

    @commands.command(
        name="get-data-store",
        category=OwnerCategory,
        hidden=True
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def get_data_store_command(self, ctx: Context[Pidroid], key: str):
        async with PersistentDataStore() as store:
            value = await store.get(key)
        if value is None:
            raise BadArgument(f"Data store does not have a value for key '{key}'")
        return await ctx.reply(
            f"The data store value for key '{key}' is {value}"
        )

    @commands.command(
        name="load-temp-extension",
        brief="Loads a temporary extension that will not survive a restart.",
        category=OwnerCategory,
        hidden=True,
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def load_temp_extension_command(self, ctx: Context[Pidroid]):
        if not ctx.message.attachments:
            raise BadArgument("Please provide a single python extension file")
        
        extension_file = ctx.message.attachments[0]
        if not extension_file.filename.endswith(".py"):
            raise BadArgument("Please provide a single python extension file")
        
        logger.critical("Attempting to load a temp extension")
        data = await extension_file.read()

        file_name = os.path.join(TEMPORARY_FILE_PATH, "temp_extension.py")
        if os.path.exists(file_name):
            os.remove(file_name)

        async with aiofiles.open(file_name, "wb") as f:
            _ = await f.write(data)

        logger.critical("Modifying system path to load a temp extension")
        if file_name not in sys.path:
            sys.path.append(file_name)
        await self.client.load_extension("data.temporary.temp_extension")
        logger.critical("Temp extension has been loaded")
        return await ctx.reply("Extension loaded successfully")

    @commands.command(
        name="unload-temp-extension",
        brief="Unloads a temporary extension that is currently loaded.",
        category=OwnerCategory,
        hidden=True,
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def unload_temp_extension_command(self, ctx: Context[Pidroid]):
        logger.critical("Attempting to unload a temp extension")
        await self.client.unload_extension("data.temporary.temp_extension")
        file_name = os.path.join(TEMPORARY_FILE_PATH, "temp_extension.py")
        logger.critical("Removing temp extension file and updating path")
        if os.path.exists(file_name):
            os.remove(file_name)
            sys.path.remove(file_name)
        logger.critical("Temp extension has been unloaded")
        return await ctx.reply("Extension unloaded successfully")

    @commands.command(
        name="test-view",
        brief="Unloads a temporary extension that is currently loaded.",
        category=OwnerCategory,
        hidden=True,
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def test_view_command(self, ctx: Context[Pidroid]):
        assert ctx.guild is not None, "This command can only be used in a guild context."
        view = ImplView(
            guild=ctx.guild
        )
        await view.update(None)  # Initialize the view
        await ctx.reply(
            view=view
        )

    # Work in progress
    @commands.command(
        name="sync-bans",
        brief="Syncs the ban list from the specified server with this one.",
        category=OwnerCategory
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def sync_bans_command(self, ctx: Context[Pidroid], guild_id: int):
        source_guild = self.client.get_guild(guild_id)
        if source_guild is None:
            raise BadArgument("Pidroid cannot find the specified server.")

        assert ctx.guild

        if source_guild.id == ctx.guild.id:
            raise BadArgument("Source server cannot be the same as the destination.")

        if not member_has_guild_permission(source_guild.me, discord.Permissions.ban_members):
            raise BadArgument("I do not have the permission to read bans in the specified server.")


        await ctx.reply("Resolving the ban list, this can take a while for huge servers")

        intermediate_list: list[discord.User] = []
        async for entry in source_guild.bans():
            intermediate_list.append(entry.user)

        return await ctx.reply(f"Resolved {len(intermediate_list)} bans")

async def setup(client: Pidroid) -> None:
    await client.add_cog(OwnerCommandCog(client))
