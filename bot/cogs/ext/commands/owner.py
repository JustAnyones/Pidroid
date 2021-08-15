import discord
import os
import typing
import sys

from discord import ui, ButtonStyle, Interaction
from discord.ext import commands
from discord.ext.commands.context import Context

from client import Pidroid
from constants import JUSTANYONE_ID
from cogs.models.categories import OwnerCategory
from cogs.utils.decorators import command_checks
from cogs.utils.embeds import error


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
        brief="Experiment with new discord interactions interface.",
    )
    #@commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def interface(self, ctx: Context):
        await ctx.send(content="Hello, my friend. Would you like to answer a survey?", view=QuestionInteraction())

def setup(client: Pidroid) -> None:
    client.add_cog(OwnerCommands(client))
