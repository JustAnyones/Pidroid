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
import typing

from discord.errors import HTTPException
from discord.ext import commands
from discord.ext.commands.context import Context # type: ignore
from typing import TYPE_CHECKING, Any, List, Optional, Tuple, Union

from client import Pidroid
from cogs.models.case import Ban2, Kick, Timeout, Jail, Warning, remove_timeout
from cogs.models.categories import ModerationCategory
from cogs.models.exceptions import InvalidDuration
from cogs.utils.decorators import command_checks
from cogs.utils.embeds import PidroidEmbed, ErrorEmbed
from cogs.utils.getters import get_role, get_channel

from datetime import timedelta
from dateutil.relativedelta import relativedelta
from discord import ui, ButtonStyle, Interaction
from discord.colour import Colour
from discord.ui import Modal, TextInput
from discord.user import User
from discord.embeds import Embed
from discord.emoji import Emoji
from discord.ext.commands.errors import BadArgument
from discord.member import Member
from discord.partial_emoji import PartialEmoji
from discord.utils import escape_markdown

from cogs.utils.checks import is_guild_moderator
from cogs.utils.time import duration_string_to_relativedelta, humanize, timedelta_to_datetime, timestamp_to_datetime

class ReasonModal(Modal, title='Custom reason modal'):
    reason_input = TextInput(label="Reason", placeholder="Please provide the reason")
    interaction = None

    async def on_submit(self, interaction: discord.Interaction):
        self.interaction = interaction
        self.stop()

class LengthModal(Modal, title='Custom length modal'):
    length_input = TextInput(label="Length", placeholder="Please provide the length")
    interaction = None

    async def on_submit(self, interaction: discord.Interaction):
        self.interaction = interaction
        self.stop()

class BaseButton(ui.Button):
    if TYPE_CHECKING:
        view: PunishmentInteraction

    def __init__(self, style: ButtonStyle, label: str, disabled: bool = False, emoji: Optional[Union[str, Emoji, PartialEmoji]] = None):
        super().__init__(style=style, label=label, disabled=disabled, emoji=emoji)

class ValueButton(BaseButton):
    def __init__(self, label: Optional[str], value: Optional[Any]):
        super().__init__(ButtonStyle.gray, label)
        # If value doesn't exist, mark it as custom
        if value is None:
            self.label = label or "Custom..."
            self.style = ButtonStyle.blurple
        # If value is -1, consider it permanent and therefore colour the button red
        elif value == -1:
            self.style = ButtonStyle.red
        self.value = value

class LengthButton(ValueButton):
    def __init__(self, label: Optional[str], value: Optional[Union[int, timedelta]]):
        super().__init__(label, value)

    async def callback(self, interaction: Interaction) -> None:
        value = self.value
        if value is None:
            value, interaction = await self.view.custom_length_modal(interaction)
            try:
                value = duration_string_to_relativedelta(value)
            except InvalidDuration as e:
                return await interaction.response.send_message(str(e), ephemeral=True)

        self.view._select_length(value)
        await self.view.create_reason_selector()
        await self.view._update_view(interaction)

class ReasonButton(ValueButton):
    def __init__(self, label: Optional[str], value: Optional[str]):
        super().__init__(label, value)

    async def callback(self, interaction: Interaction) -> None:
        value = self.value
        if value is None:
            value, interaction = await self.view.custom_reason_modal(interaction)

        self.view._select_reason(value)
        await self.view.create_confirmation_selector()
        await self.view._update_view(interaction)

class ConfirmButton(BaseButton):
    def __init__(self):
        super().__init__(ButtonStyle.green, "Confirm")

    async def callback(self, interaction: Interaction) -> None:
        await self.view._handle_confirmation(interaction, True)

class CancelButton(BaseButton):
    def __init__(self):
        super().__init__(ButtonStyle.red, "Cancel")

    async def callback(self, interaction: Interaction) -> None:
        await self.view._handle_confirmation(interaction, False)

class BasePunishmentButton(ui.Button):
    if TYPE_CHECKING:
        view: PunishmentInteraction

    def __init__(self, style: ButtonStyle, label: str, disabled: bool = False, emoji: Optional[Union[str, Emoji, PartialEmoji]] = None):
        super().__init__(style=style, label=label, disabled=disabled, emoji=emoji)

class BanButton(BasePunishmentButton):
    def __init__(self):
        super().__init__(ButtonStyle.red, "Ban", emoji="🔨")

    async def callback(self, interaction: Interaction) -> None:
        self.view._select_type(Ban2(self.view.ctx, self.view.user))
        await self.view.create_length_selector()
        await self.view._update_view(interaction)

class UnbanButton(BasePunishmentButton):
    def __init__(self):
        super().__init__(ButtonStyle.red, "Unban", emoji="🔨")

    async def callback(self, interaction: Interaction) -> None:
        print("NO IDEA HOW TO IMPLEMENT")

class KickButton(BasePunishmentButton):
    def __init__(self, disabled: bool = False):
        super().__init__(ButtonStyle.gray, "Kick", disabled=disabled)

    async def callback(self, interaction: Interaction) -> None:
        self.view._select_type(Kick(self.view.ctx, self.view.user))
        await self.view.create_reason_selector()
        await self.view._update_view(interaction)

class JailButton(BasePunishmentButton):
    def __init__(self, disabled: bool = False):
        super().__init__(ButtonStyle.gray, "Jail", disabled=disabled)

    async def callback(self, interaction: Interaction) -> None:
        self.view._select_type(Jail(self.view.ctx, self.view.user))
        await self.view.create_reason_selector()
        await self.view._update_view(interaction)

class RemoveJailButton(BasePunishmentButton):
    def __init__(self):
        super().__init__(ButtonStyle.gray, "Release from jail")

    async def callback(self, interaction: Interaction) -> None:
        print("NO IDEA HOW TO IMPLEMENT")

class TimeoutButton(BasePunishmentButton):
    def __init__(self, disabled: bool = False):
        super().__init__(ButtonStyle.gray, "Time-out", disabled=disabled)

    async def callback(self, interaction: Interaction) -> None:
        self.view._select_type(Timeout(self.view.ctx, self.view.user))
        await self.view.create_length_selector()
        await self.view._update_view(interaction)

class RemoveTimeoutButton(BasePunishmentButton):
    def __init__(self):
        super().__init__(ButtonStyle.gray, "Remove time-out")

    async def callback(self, interaction: Interaction) -> None:
        await remove_timeout(
            self.view.ctx.bot.api, self.view.ctx.guild, self.view.ctx.channel,
            self.view.ctx.author, self.view.user,
            f"Removed by {str(self.view.ctx.author)}"
        )
        await self.view.finish(interaction)

class WarnButton(BasePunishmentButton):
    def __init__(self, disabled: bool = False):
        super().__init__(ButtonStyle.gray, "Warn", disabled, "⚠️")

    async def callback(self, interaction: Interaction) -> None:
        self.view._select_type(Warning(self.view.ctx, self.view.user))
        await self.view.create_reason_selector()
        await self.view._update_view(interaction)


LENGTH_MAPPING = {
    "timeout": [
        LengthButton("30 minutes", timedelta(minutes=30)),
        LengthButton("An hour", timedelta(hours=1)),
        LengthButton("2 hours", timedelta(hours=2)),
        LengthButton("12 hours", timedelta(hours=12)),
        LengthButton("A day", timedelta(hours=24)),
        LengthButton("A week", timedelta(weeks=1)),
        LengthButton(None, None)
    ],
    "ban": [
        LengthButton("24 hours", timedelta(hours=24)),
        LengthButton("A week", timedelta(weeks=1)),
        LengthButton("2 weeks", timedelta(weeks=2)),
        LengthButton("A month", timedelta(days=30)),
        LengthButton("Permanent", -1),
        LengthButton(None, None)
    ]
}

# TODO: add
REASON_MAPPING = {
    "ban": [
        ReasonButton("Spam", "Spam"),
        ReasonButton(None, None)
    ],
    "kick": [
        ReasonButton(None, None)
    ],
    "jail": [
        ReasonButton("Investigation", "Investigation"),
        ReasonButton(None, None)
    ],
    "timeout": [
        ReasonButton(None, None)
    ],
    "warning": [
        ReasonButton(None, None)
    ]
}

class PunishmentInteraction(ui.View):

    def __init__(self, ctx: Context, user: Union[Member, User], embed: Embed):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.user = user
        self.embed = embed

        self._punishment: Union[Ban2, Kick, Jail, Timeout, Warning] = None

    """Private utility methods"""

    def _select_type(self, instance):
        self.embed.description = f"Type: {str(instance)}"
        self._punishment = instance

    def _select_length(self, length: Union[int, timedelta, relativedelta]):
        # Get correct representation of provided length value
        if isinstance(length, int):
            if length == -1:
                len_str = "permanent"
            else:
                len_str = humanize(timestamp_to_datetime(length), max_units=3)
        elif isinstance(length, relativedelta):
            len_str = humanize(length, max_units=3)
        else:
            len_str = humanize(timedelta_to_datetime(length), max_units=3)

        self.embed.description += f"\nLength: {len_str}"
        self._punishment.length = length

    def _select_reason(self, reason: str):
        self.embed.description += f"\nReason: {reason}"
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

    async def is_user_timed_out(self) -> bool:
        """Returns true if user is currently muted."""
        if isinstance(self.user, User):
            return False
        return self.user.is_timed_out()

    """
    Methods for creating button interfaces for:
    - Selecting punishment type
    - Selecting punishment length
    - Selecting punishment reason
    - Confirming or cancelling the action
    """

    async def custom_reason_modal(self, interaction: Interaction) -> Tuple[Optional[str], Interaction]:
        modal = ReasonModal()
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()
        return modal.reason_input.value, modal.interaction

    async def custom_length_modal(self, interaction: Interaction) -> Tuple[Optional[str], Interaction]:
        modal = LengthModal()
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()
        return modal.length_input.value, modal.interaction

    async def create_type_selector(self):
        self.embed.set_footer(text="Select punishment type")
        self.clear_items()
        is_member = isinstance(self.user, Member)

        # Add ban/unban buttons
        if not await self.is_user_banned():
            self.add_item(BanButton())
        else:
            self.add_item(UnbanButton())

        # Kick button
        self.add_item(KickButton(not is_member))

        # Add jail/unjail buttons
        if not await self.is_user_jailed():
            self.add_item(JailButton(not is_member))
        else:
            self.add_item(RemoveJailButton())

        # Add timeout/un-timeout buttons
        if not await self.is_user_timed_out():
            self.add_item(TimeoutButton(not is_member))
        else:
            self.add_item(RemoveTimeoutButton())

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

    async def _handle_confirmation(self, interaction: Interaction, confirmed: bool):
        self.embed.remove_footer()

        # If moderator confirmed the action
        if confirmed:

            if (self._punishment.type and (
                self._punishment.type == "timeout"
                or self._punishment.type == "ban"
            )):
                await self._punishment.issue()

            return await self.finish()

        # Otherwise, clear items
        self.embed.set_footer(text="CANCELLED")
        self.embed.colour = Colour.red()
        self.remove_items()
        await self._update_view(interaction)
        self.stop()

    """Clean up related methods"""

    def disable_items(self) -> None:
        """Disables all view items."""
        for child in self.children:
            child.disabled = True

    def remove_items(self) -> None:
        """Removes all items from the view."""
        for child in self.children.copy():
            self.remove_item(child)

    async def finish(self, interaction: Interaction) -> None:
        """Causes the view to remove itself and stop listening to interactions."""
        await interaction.response.defer()
        await interaction.delete_original_message()
        return self.stop()

    def stop(self) -> None:
        """Stops listening to all interactions for this view."""
        self.remove_items()
        return super().stop()

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Ensure that the interaction is called by the message author.

        Moderator, in this case."""
        if interaction.user and interaction.user.id == self.ctx.author.id:
            return True
        await interaction.response.send_message('This menu cannot be controlled by you, sorry!', ephemeral=True)
        return False


class ModeratorCommands(commands.Cog):
    """This class implements cog which contains commands for moderation."""

    def __init__(self, client: Pidroid):
        self.client = client
        self.api = self.client.api

    @commands.command(
        brief='Removes a specified amount of messages from the channel.',
        usage='<amount>',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True)
    @command_checks.can_purge()
    @commands.guild_only()
    async def purge(self, ctx: Context, amount: int = 0):
        if amount <= 0:
            return await ctx.reply(embed=ErrorEmbed(
                "Please specify an amount of messages to delete!"
            ))

        # Evan proof
        if amount > 1000:
            amount = 1000

        await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f'{amount} messages have been purged!', delete_after=1.5)

    @commands.command(hidden=True)
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, attach_files=True)
    @command_checks.is_junior_moderator(manage_messages=True)
    @commands.guild_only()
    async def deletethis(self, ctx: Context):
        await ctx.message.delete(delay=0)
        await ctx.channel.purge(limit=1)
        await ctx.send(file=discord.File('./resources/delete_this.png'))

    @commands.command(
        brief="Open user moderation and punishment menu.",
        usage="<user/member>",
        category=ModerationCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @commands.is_owner()
    async def punish(self, ctx: Context, user: Union[Member, User] = None):
        # Check initial permissions
        if not is_guild_moderator(ctx.guild, ctx.channel, ctx.message.author):
            raise BadArgument("You need to be a moderator to run this command!")

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

        view = PunishmentInteraction(ctx, user, embed)
        await view.create_type_selector()

        await ctx.reply(embed=embed, view=view)

async def setup(client: Pidroid):
    await client.add_cog(ModeratorCommands(client))
