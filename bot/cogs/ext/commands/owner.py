import discord
import os
import typing
import sys

from discord import ui, ButtonStyle, Interaction
from discord.ext import commands
from discord.ext.commands.context import Context
from discord.ext.commands.errors import BadArgument
from typing import TYPE_CHECKING

from client import Pidroid
from constants import JUSTANYONE_ID
from cogs.models.categories import OwnerCategory
from cogs.utils.decorators import command_checks
from cogs.utils.embeds import error

if TYPE_CHECKING:
    from cogs.ext.events.initialization import InvocationEventHandler
    from cogs.ext.tasks.automod import AutomodTask


class QuestionInteraction(ui.View):
    @ui.button(label='Yes', style=ButtonStyle.green)
    async def yes_button(self, button: ui.Button, interaction: Interaction):
        for child in self.children:
            child.disabled = True

        await interaction.message.edit(content="Alright, give me some time to implement the rest", view=self)
        self.stop()

    @ui.button(label='No', style=ButtonStyle.red)
    async def counter(self, button: ui.Button, interaction: Interaction):
        for child in self.children:
            child.disabled = True

        await interaction.message.edit(content="Fair enough", view=self)
        self.stop()


class OwnerCommands(commands.Cog):
    """This class implements a cog for special bot owner only commands."""
    def __init__(self, client: Pidroid) -> None:
        self.client = client

    @commands.command(
        brief="Sends a message to a specified guild channel as the bot.",
        usage="<channel> <message>",
        aliases=["say"],
        permissions=["Bot owner"],
        category=OwnerCategory,
        hidden=True
    )
    @commands.is_owner()
    @commands.bot_has_guild_permissions(send_messages=True, manage_messages=True)
    async def speak(self, ctx: Context, channel: discord.TextChannel, *, message: str):
        try:
            await ctx.message.delete(delay=0)
            await channel.send(message)
        except Exception as e:
            await ctx.reply(embed=error(e))

    @commands.command(
        brief="Set the bot's playing game status to the specified game.",
        usage="<game>",
        aliases=["setgame", "play"],
        permissions=["Bot owner"],
        category=OwnerCategory
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def playgame(self, ctx: Context, *, game: str):
        await self.client.change_presence(activity=discord.Game(game))
        await ctx.reply(f"Now playing {game}!")

    @commands.command(
        brief="Stops the bot by killing the process with a SIGKILL signal.",
        aliases=["pulltheplug", "shutdown"],
        permissions=["Bot owner"],
        category=OwnerCategory
    )
    @command_checks.can_shutdown_bot()
    @commands.bot_has_permissions(send_messages=True)
    async def stop(self, ctx: Context):
        user = self.client.get_user(JUSTANYONE_ID)
        print(f'Kill request received by {ctx.message.author}')
        await user.send(f'The bot was manually shut down by {ctx.message.author}')
        await ctx.reply('Shutting down!')
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
    async def dm(self, ctx: Context, user: typing.Union[discord.Member, discord.User], *, message: str):
        try:
            await user.send(message)
            await ctx.reply(f"Message to {user.name}#{user.discriminator} was sent succesfully")
        except Exception as e:
            await ctx.reply(embed=error(f"Message was not sent\n```{e}```"))

    @commands.command(
        name="update-guild-cache",
        brief="Forcefully updates the internal guild configuration cache.\nShould only be called when desynced on development versions.",
        category=OwnerCategory
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def updateguildcache(self, ctx: Context):
        cog: InvocationEventHandler = self.client.get_cog("InvocationEventHandler")
        await cog._fill_guild_config_cache()
        await ctx.reply("Internal guild cache updated!")

    @commands.group(
        brief="Command group used to interact with phising protection related system.",
        permissions=["Bot owner"],
        category=OwnerCategory,
        invoke_without_command=True
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.is_owner()
    async def phising(self, ctx: Context):
        return

    @phising.command(
        name="update-urls",
        brief="Updates internal phising URL list by calling the database.",
        permissions=["Bot owner"],
        category=OwnerCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.is_owner()
    async def updateurls(self, ctx: Context):
        cog: AutomodTask = self.client.get_cog("AutomodTask")
        await cog._update_phising_urls()
        await ctx.reply("Phising URL list has been updated!")

    @phising.command(
        name="insert-url",
        brief="Updates internal and database phising URL list by adding a new URL.",
        permissions=["Bot owner"],
        aliases=["add-url"],
        category=OwnerCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.is_owner()
    async def inserturl(self, ctx: Context, url: str):
        url = url.lower()
        cog: AutomodTask = self.client.get_cog("AutomodTask")
        if url in cog.phising_urls:
            raise BadArgument("Phising URL is already in the list!")
        await self.client.api.insert_new_phising_url(url)
        cog.phising_urls.append(url)
        await ctx.reply("New phising URL has been added!")

    @commands.command(
        brief="Experiment with new discord interactions interface.",
    )
    @commands.bot_has_permissions(send_messages=True)
    async def interface(self, ctx: Context):
        await ctx.reply(content="Hello, my friend. Would you like to answer a survey?", view=QuestionInteraction())

def setup(client: Pidroid) -> None:
    client.add_cog(OwnerCommands(client))
