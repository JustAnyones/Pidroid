from __future__ import annotations

"""
Left to consider

Please do not forget to implement the following:
- Custom length and reason selection
- Actual checking of moderator permissions before executing and providing the buttons
- Actual issueing of punishments
- Ability to revoke punishments
- Passing or acquiring the roles for required operations

"""

import discord
import os
import typing
import sys

from datetime import timedelta
from discord import ui, ButtonStyle, Interaction
from discord.user import User
from discord.embeds import Embed
from discord.emoji import Emoji
from discord.ext import commands
from discord.ext.commands.context import Context
from discord.ext.commands.errors import BadArgument
from discord.member import Member
from discord.partial_emoji import PartialEmoji
from discord.utils import escape_markdown
from typing import TYPE_CHECKING, Any, List, Optional, Union

from client import Pidroid
from constants import JUSTANYONE_ID
from cogs.models.case import Ban, Case, Jail, Kick, Mute, Warning
from cogs.utils.checks import is_guild_moderator
from cogs.utils.time import humanize, timedelta_to_datetime, timestamp_to_datetime
from cogs.models.categories import OwnerCategory
from cogs.utils.decorators import command_checks
from cogs.utils.embeds import PidroidEmbed, ErrorEmbed

if TYPE_CHECKING:
    from cogs.ext.events.initialization import InvocationEventHandler
    from cogs.ext.tasks.automod import AutomodTask

class BaseButton(ui.Button):

    if TYPE_CHECKING:
        view: PunishmentInteraction

    def __init__(self, style: ButtonStyle, label: str, disabled: bool = False, emoji: Optional[Union[str, Emoji, PartialEmoji]] = None):
        super().__init__(style=style, label=label, disabled=disabled, emoji=emoji)

class ValueButton(BaseButton):

    def __init__(self, label: str, value: Optional[Any]):
        super().__init__(ButtonStyle.gray, label)

        # If value doesn't exist, allow user input
        if value is None:
            self.label = "..."

        # If value is -1, consider it permanent and therefore colour the button red
        elif value == -1:
            self.style = ButtonStyle.red

        self.value = value

class LengthButton(ValueButton):

    def __init__(self, label: str, value: Union[int, timedelta]):
        super().__init__(label, value)

    async def callback(self, interaction: Interaction):
        # TODO: implement custom values
        self.view._select_length(self.value)
        await self.view.create_reason_selector()
        await self.view._update_view(interaction)

class ReasonButton(ValueButton):

    def __init__(self, label: str, value: str):
        super().__init__(label, value)

    async def callback(self, interaction: Interaction):
        # TODO: implement custom values
        self.view._select_reason(self.value)
        await self.view.create_confirmation_selector()
        await self.view._update_view(interaction)

class ConfirmButton(BaseButton):

    def __init__(self):
        super().__init__(ButtonStyle.green, "Confirm")

    async def callback(self, interaction: Interaction):
        self.view.stop()
        await self.view._handle_confirmation(True)
        await self.view._update_view(interaction)

class CancelButton(BaseButton):

    def __init__(self):
        super().__init__(ButtonStyle.red, "Cancel")

    async def callback(self, interaction: Interaction):
        self.view.stop()
        await self.view._handle_confirmation(False)
        await self.view._update_view(interaction)

class BasePunishmentButton(ui.Button):

    if TYPE_CHECKING:
        view: PunishmentInteraction

    def __init__(self, style: ButtonStyle, label: str, disabled: bool = False, emoji: Optional[Union[str, Emoji, PartialEmoji]] = None):
        super().__init__(style=style, label=label, disabled=disabled, emoji=emoji)

class BanButton(BasePunishmentButton):

    def __init__(self):
        super().__init__(ButtonStyle.red, "Ban", emoji="🔨")

    async def callback(self, interaction: Interaction):
        self.view._select_type(Ban(self.view.ctx, self.view.user))
        await self.view.create_length_selector()
        await self.view._update_view(interaction)

class KickButton(BasePunishmentButton):

    def __init__(self, disabled: bool = False):
        super().__init__(ButtonStyle.gray, "Kick", disabled=disabled)

    async def callback(self, interaction: Interaction):
        self.view._select_type(Kick(self.view.ctx, self.view.user))
        await self.view.create_reason_selector()
        await self.view._update_view(interaction)

class JailButton(BasePunishmentButton):

    def __init__(self, disabled: bool = False):
        super().__init__(ButtonStyle.gray, "Jail", disabled=disabled)

    async def callback(self, interaction: Interaction):
        self.view._select_type(Jail(self.view.ctx, self.view.user))
        await self.view.create_reason_selector()
        await self.view._update_view(interaction)

class MuteButton(BasePunishmentButton):

    def __init__(self, disabled: bool = False):
        super().__init__(ButtonStyle.gray, "Mute", disabled=disabled)

    async def callback(self, interaction: Interaction):
        self.view._select_type(Mute(self.view.ctx, self.view.user))
        await self.view.create_length_selector()
        await self.view._update_view(interaction)

class WarnButton(BasePunishmentButton):

    def __init__(self, disabled: bool = False):
        super().__init__(ButtonStyle.gray, "Warn", disabled, "⚠️")

    async def callback(self, interaction: Interaction):
        self.view._select_type(Warning(self.view.ctx, self.view.user))
        await self.view.create_reason_selector()
        await self.view._update_view(interaction)


LENGTH_MAPPING = {
    "mute": [
        LengthButton("30 minutes", timedelta(minutes=30)),
        LengthButton("An hour", timedelta(hours=1)),
        LengthButton("2 hours", timedelta(hours=2)),
        LengthButton("12 hours", timedelta(hours=12)),
        LengthButton("A day", timedelta(hours=24)),
        LengthButton("Permanent", -1)
    ],
    "ban": [
        LengthButton("24 hours", timedelta(hours=24)),
        LengthButton("A week", timedelta(weeks=1)),
        LengthButton("2 weeks", timedelta(weeks=2)),
        LengthButton("A month", timedelta(days=30)),
        LengthButton("Permanent", -1)
    ]
}

# TODO: add
REASON_MAPPING = {}

class PunishmentInteraction(ui.View):

    def __init__(self, ctx: Context, user: Union[Member, User], cases: List[Case], embed: Embed):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.user = user
        self.embed = embed

        self._punishment: Union[Kick, Ban, Warning, Jail, Mute] = None

    """Private utility methods"""

    def _select_type(self, instance):
        self.embed.description = f"Type: **{str(instance)}**"
        self._punishment = instance

    def _select_length(self, length: Union[int, timedelta]):
        # Get correct representation of provided length value
        if isinstance(length, int):
            if length == -1:
                len_str = "permanent"
            else:
                len_str = humanize(timestamp_to_datetime(length), max_units=3)
        else:
            len_str = humanize(timedelta_to_datetime(length), max_units=3)

        self.embed.description += f"\nLength: *{len_str}*"
        self._punishment.length = length

    def _select_reason(self, reason: str):
        self.embed.description += f"\nReason: *{reason}*"
        self._punishment.reason = reason

    async def _update_view(self, interaction: Interaction):
        await interaction.response.edit_message(embed=self.embed, view=self)

    """Checks"""

    async def is_user_banned(self) -> bool:
        """Returns true if user is currently banned."""
        for entry in await self.ctx.guild.bans():
            if entry.user.id == self.user.id:
                return True
        return False

    async def is_user_jailed(self) -> bool:
        """Returns true if user is currently jailed."""
        # TODO: implement
        return False

    async def is_user_muted(self) -> bool:
        """Returns true if user is currently muted."""
        # TODO: implement
        return False

    """
    Methods for creating button interfaces for:
    - Selecting punishment type
    - Selecting punishment length
    - Selecting punishment reason
    - Confirming or cancelling the action
    """

    async def create_type_selector(self):
        self.embed.set_footer(text="Select punishment type")
        self.clear_items()
        is_member = isinstance(self.user, Member)

        # Add ban/unban buttons
        if not await self.is_user_banned():
            self.add_item(BanButton())
        else:
            # TODO: Add unban button
            pass

        # Kick button
        self.add_item(KickButton(not is_member))

        # Add jail/unjail buttons
        if not await self.is_user_jailed():
            self.add_item(JailButton(not is_member))
        else:
            # TODO: add unjail button
            pass

        # Add mute/unmute buttons
        if not await self.is_user_muted():
            self.add_item(MuteButton(not is_member))
        else:
            # TODO: add unmute button
            pass

        # Warn button
        self.add_item(WarnButton(not is_member))

    async def create_length_selector(self):
        # Acquire mapping for lengths for punishment types
        mapping: List[ValueButton] = LENGTH_MAPPING.get(str(self._punishment), None)
        if mapping is None or len(mapping) == 0:
            return await self.create_reason_selector()

        self.clear_items()
        for button in mapping:
            self.add_item(button)
        self.embed.set_footer(text="Select punishment length")

    async def create_reason_selector(self):
        # Acquire mapping for lengths for punishment types
        mapping: List[ValueButton] = REASON_MAPPING.get(str(self._punishment), None)
        if mapping is None or len(mapping) == 0:
            return await self.create_confirmation_selector()

        self.clear_items()
        for button in mapping:
            self.add_item(button)
        self.embed.set_footer(text="Select punishment reason")

    async def create_confirmation_selector(self):
        self.clear_items()
        self.add_item(ConfirmButton())
        self.add_item(CancelButton())
        self.embed.set_footer(text="Confirm or cancel the punishment")

    """Handle selections"""

    async def _handle_confirmation(self, confirmed: bool):
        self.embed.remove_footer()

        # If moderator confirmed the action
        if confirmed:
            # TODO: call method's issue command
            # TODO: delete the punishment dialogue after done
            self.embed.description = "Punishment confirmed"
            #await self._punishment.issue()
            return

        # Otherwise, clear items
        self.embed.description += "\n\nCANCELLED"

    def disable_buttons(self) -> None:
        for child in self.children:
            child.disabled = True

    def stop(self) -> None:
        self.disable_buttons()
        return super().stop()

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Ensure that the interaction is called by the message author.

        Moderator, in this case."""
        if interaction.user and interaction.user.id == self.ctx.author.id:
            return True
        await interaction.response.send_message('This menu cannot be controlled by you, sorry!', ephemeral=True)
        return False

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
            await ctx.reply(embed=ErrorEmbed(e))

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
            await ctx.reply(embed=ErrorEmbed(f"Message was not sent\n```{e}```"))

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
        brief="Experiment with new discord interactions interface in regards of the punishment system.",
        enabled=False
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @commands.is_owner()
    async def punish(self, ctx: Context, user: Union[Member, User] = None):
        if user is None:
            raise BadArgument("Please specify the member or the user you are trying to punish!")

        # Prevent moderator from punishing himself
        if user.id == ctx.message.author.id:
            raise BadArgument("You cannot punish yourself! That's what PHP is for.")

        # Generic check to only invoke the menu if author is a moderator
        if is_guild_moderator(ctx.guild, ctx.channel, user):
            raise BadArgument("You cannot punish a moderator!")

        # Create an embed overview
        embed = PidroidEmbed()
        embed.title = f"Punish {escape_markdown(str(user))}"

        # Use these to assign correct punishments
        cases = [case for case in await self.client.api.fetch_active_cases(ctx.guild.id, user.id) if case.type != "warning"]

        view = PunishmentInteraction(ctx, user, cases, embed)
        await view.create_type_selector()

        await ctx.reply(embed=embed, view=view)

async def setup(client: Pidroid) -> None:
    await client.add_cog(OwnerCommands(client))
