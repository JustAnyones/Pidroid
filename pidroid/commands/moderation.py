from __future__ import annotations

import asyncio
import datetime
import discord
import logging

from datetime import timedelta
from dateutil.relativedelta import relativedelta
from discord import Object, ui, ButtonStyle, Interaction, app_commands, Member, Message, RawMessageDeleteEvent
from discord.colour import Colour
from discord.embeds import Embed
from discord.emoji import Emoji
from discord.errors import NotFound
from discord.ext import commands, tasks
from discord.ext.commands import BadArgument, BadUnionArgument, Context, MissingPermissions, MissingRequiredArgument, UserNotFound
from discord.file import File
from discord.partial_emoji import PartialEmoji
from discord.role import Role
from discord.user import User
from discord.utils import escape_markdown, get
from typing import TYPE_CHECKING, Any, Callable, Self, TypedDict, override

from pidroid.client import Pidroid
from pidroid.models.categories import ModerationCategory
from pidroid.models.exceptions import InvalidDuration, MissingUserPermissions
from pidroid.models.punishments import Ban, BasePunishment, Kick, Timeout, Jail, Warning
from pidroid.services.error_handler import notify
from pidroid.models.view import BaseView, PidroidModal
from pidroid.utils import user_mention
from pidroid.utils.aliases import MessageableGuildChannel, MessageableGuildChannelTuple
from pidroid.utils.checks import (
    member_has_guild_permission,
    assert_junior_moderator_permissions, assert_normal_moderator_permissions, assert_senior_moderator_permissions,
    is_guild_moderator, is_guild_theotown
)
from pidroid.utils.decorators import command_checks
from pidroid.utils.file import Resource
from pidroid.utils.time import delta_to_datetime, try_convert_duration_to_relativedelta, utcnow

logger = logging.getLogger("Pidroid")

BUNNY_ID = 793465265237000212

class ReasonModal(PidroidModal, title='Custom reason modal'):
    reason_input: ui.TextInput[ModerationMenu] = ui.TextInput(label="Reason", placeholder="Please provide the reason")

class LengthModal(PidroidModal, title='Custom length modal'):
    length_input: ui.TextInput[ModerationMenu] = ui.TextInput(label="Length", placeholder="Please provide the length")

class BaseButton(ui.Button):
    if TYPE_CHECKING:
        view: ModerationMenu

    def __init__(self, style: ButtonStyle, label: str | None, disabled: bool = False, emoji: str | Emoji | PartialEmoji | None = None):
        super().__init__(style=style, label=label, disabled=disabled, emoji=emoji)

class ValueButton(BaseButton):
    def __init__(self, label: str | None, value: Any | None):
        super().__init__(ButtonStyle.gray, label)
        # If value doesn't exist, mark it as custom
        if value is None:
            self.label = label or "Custom..."
            self.style = ButtonStyle.blurple
        # If value is -1, consider it permanent and therefore colour the button red
        elif value == -1:
            self.style = ButtonStyle.red
        self.value = value

    def copy(self):
        return type(self)(self.label, self.value)

class LengthButton(ValueButton):
    def __init__(self, label: str | None, value: int | timedelta | None):
        super().__init__(label, value)

    @override
    async def callback(self, interaction: Interaction) -> None:
        value = self.value
        if value is None:
            value, interaction, timed_out = await self.view.custom_length_modal(interaction)

            if timed_out:
                return await interaction.response.send_message("Punishment reason modal has timed out!", ephemeral=True)

            if value is None:
                return await interaction.response.send_message("Punishment duration cannot be empty!", ephemeral=True)

            try:
                value = try_convert_duration_to_relativedelta(value)
            except InvalidDuration as e:
                return await interaction.response.send_message(str(e), ephemeral=True)

            now = utcnow()
            delta = now - (now - value)

            if delta.total_seconds() < 5 * 60:
                return await interaction.response.send_message("Punishment duration cannot be shorter than 5 minutes!", ephemeral=True)
            
            assert self.view._punishment is not None
            if isinstance(self.view._punishment, Timeout):
                if delta.total_seconds() > 2419200: # 4 * 7 * 24 * 60 * 60
                    return await interaction.response.send_message("Timeouts cannot be longer than 4 weeks!", ephemeral=True)

        if self.view.is_finished():
            return await interaction.response.send_message("Interaction has timed out!", ephemeral=True)

        self.view.select_length(value)
        await self.view.show_confirmation_menu(interaction)

class ReasonButton(ValueButton):
    def __init__(self, label: str | None, value: str | None):
        super().__init__(label, value)

    @override
    async def callback(self, interaction: Interaction) -> None:
        value = self.value
        if value is None:
            value, interaction, timed_out = await self.view.custom_reason_modal(interaction)

            if timed_out:
                return await interaction.response.send_message("Punishment reason modal has timed out!", ephemeral=True)

            if value is None:
                return await interaction.response.send_message("Punishment reason cannot be empty!", ephemeral=True)

            if len(value) > 480:
                return await interaction.response.send_message("Punishment reason cannot be longer than 480 characters!", ephemeral=True)

        if self.view.is_finished():
            return await interaction.response.send_message("Interaction has timed out!", ephemeral=True)

        self.view.select_reason(value)
        await self.view.show_length_selection_menu(interaction)


LENGTH_MAPPING = {
    "timeout": [
        LengthButton("30 minutes", timedelta(minutes=30)),
        LengthButton("An hour", timedelta(hours=1)),
        LengthButton("2 hours", timedelta(hours=2)),
        LengthButton("12 hours", timedelta(hours=12)),
        LengthButton("A day", timedelta(hours=24)),
        LengthButton("A week", timedelta(weeks=1)),
        LengthButton("4 weeks (max)", timedelta(weeks=4)),
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

REASON_MAPPING = {
    "ban": [
        ReasonButton("Ignoring moderator's orders", "Ignoring moderator's orders."),
        ReasonButton("Hacked content", "Sharing, spreading or using hacked content."),
        ReasonButton("Offensive content or hate-speech", "Posting or spreading offensive content or hate-speech."),
        ReasonButton("Harassing other members", "Harassing other members."),
        ReasonButton("Scam or phishing", "Sharing or spreading scams or phishing content."),
        ReasonButton("Continued or repeat offences", "Continued or repeat offences."),
        ReasonButton("Spam", "Spam."),
        ReasonButton("Alternative account", "Alternative accounts are not allowed."),
        ReasonButton("Underage user", "You are under the allowed age as defined in Discord's Terms of Service."),
        ReasonButton(None, None)
    ],
    "kick": [
        ReasonButton("Spam", "Spam."),
        ReasonButton("Alternative account", "Alternative accounts are not allowed."),
        ReasonButton(
            "Underage",
            "You are under the allowed age as defined in Discord's Terms of Service. Please rejoin when you're older."
        ),
        ReasonButton(None, None)
    ],
    "jail": [
        #ReasonButton("Pending investigation", "Pending investigation."),
        #ReasonButton("Questioning", "Questioning."),
        ReasonButton(None, None)
    ],
    "timeout": [
        ReasonButton("Being emotional or upset", "Being emotional or upset."),
        ReasonButton("Spam", "Spam."),
        ReasonButton("Disrupting the chat", "Disrupting the chat."),
        ReasonButton(None, None)
    ],
    "warning": [
        ReasonButton("Spam", "Spam."),
        ReasonButton("Failure to follow orders", "Failure to follow orders."),
        ReasonButton("Failure to comply with verbal warning", "Failure to comply with a verbal warning."),
        ReasonButton("Hateful content", "Sharing or spreading hateful content."),
        ReasonButton("Repeat use of wrong channels", "Repeat use of wrong channels."),
        ReasonButton("NSFW content", "Sharing or spreading NSFW content."),
        ReasonButton("Politics", "Politics or political content."),
        ReasonButton(None, None)
    ]
}

class ModerationMenu(BaseView):

    if TYPE_CHECKING:
        _message: Message | None

    def __init__(
        self,
        ctx: Context[Pidroid],
        user: Member | User,
        punishing_moderator: bool
    ):
        super().__init__(ctx.bot, ctx, timeout=300)

        # Create embed object
        self._embed.title = f'Punish {escape_markdown(str(user))}'

        # Get the cog instance from context
        assert isinstance(ctx.cog, ModerationCommandCog)
        self._cog = ctx.cog

        # Acquire the client and API instance
        self._api = self._client.api

        # Aqcuire guild, channel and users from the context
        assert ctx.guild
        assert isinstance(ctx.channel, MessageableGuildChannelTuple)

        self.guild = ctx.guild
        self.channel: MessageableGuildChannel = ctx.channel
        self.moderator = ctx.author
        self.user = user

        # Initialize variables
        self._punishment: Ban | Kick | Jail | Timeout | Warning | None = None
        self._jail_role: Role | None = None
        self._punishing_moderator = punishing_moderator

    async def _init(self):
        """Acquires the guild configuration and related items."""
        config = await self._client.fetch_guild_configuration(self.guild.id)
        self._config = config

        if config.jail_role_id is not None:
            role = self.guild.get_role(config.jail_role_id)
            if role is not None:
                self._jail_role = role

        if self._cog.is_semaphore_locked(self.guild.id, self.user.id):
            raise BadArgument("Semaphore is already locked")

        # Lock the punishment menu with a semaphore
        await self._cog.lock_punishment_menu(
            self.guild.id, self.user.id,
            self._ctx.message.id,
            self._ctx.message.jump_url
        )

    @property
    def embed(self) -> Embed:
        """Returns the embed object associated with the current menu status."""
        return self._embed

    async def display(self):
        """Creates the response message and begins the menu."""
        await self._init()
        await self.show_type_selection_menu()
        self._message = await self._ctx.reply(embed=self.embed, view=self)

    """Private utility methods"""

    @property
    def punishment(self):
        """The punishment instance, if available."""
        return self._punishment

    @punishment.setter
    def punishment(self, instance: BasePunishment):
        """Sets the punishment instance."""
        self._embed.description = f"Type: {str(instance)}"
        self._punishment = instance

    def select_length(self, length: timedelta | relativedelta | None):
        # Special case
        if length == -1:
            length = None

        assert self.punishment
        self.punishment.set_length(length)
        assert isinstance(self._embed.description, str)
        self._embed.description += f"\nLength: {self.punishment.length_as_string}"

    def select_reason(self, reason: str):
        assert isinstance(self._embed.description, str)
        self._embed.description += f"\nReason: {reason}"
        assert self._punishment
        self._punishment.reason = reason

    """Checks"""

    async def is_user_banned(self) -> bool:
        """Returns true if user is currently banned."""
        try:
            _ = await self.guild.fetch_ban(self.user)
            return True
        except NotFound:
            return False

    async def is_user_jailed(self) -> bool:
        """Returns true if user is currently jailed."""
        if isinstance(self.user, User) or self._jail_role is None:
            return False
        client: Pidroid = self._ctx.bot
        return (
            get(self.guild.roles, id=self._jail_role.id) in self.user.roles
            and await client.api.is_currently_jailed(self.guild.id, self.user.id)
        )

    async def is_user_timed_out(self) -> bool:
        """Returns true if user is currently muted."""
        if isinstance(self.user, User):
            return False
        return self.user.is_timed_out()

    """
    Permission checks for moderators and Pidroid
    """

    def is_junior_moderator(self, **perms: bool) -> bool:
        try:
            assert_junior_moderator_permissions(self._ctx, **perms)
            return True
        except (MissingUserPermissions, MissingPermissions):
            return False

    def is_normal_moderator(self, **perms: bool) -> bool:
        try:
            assert_normal_moderator_permissions(self._ctx, **perms)
            return True
        except (MissingUserPermissions, MissingPermissions):
            return False

    def is_senior_moderator(self, **perms: bool) -> bool:
        try:
            assert_senior_moderator_permissions(self._ctx, **perms)
            return True
        except (MissingUserPermissions, MissingPermissions):
            return False

    """
    Methods for creating button interfaces for:
    - Selecting punishment type
    - Selecting punishment length
    - Selecting punishment reason
    - Confirming or cancelling the action
    """

    async def custom_reason_modal(self, interaction: Interaction) -> tuple[str | None, Interaction, bool]:
        modal = ReasonModal()
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            await self.timeout_view()
        return modal.reason_input.value, modal.interaction, timed_out

    async def custom_length_modal(self, interaction: Interaction) -> tuple[str | None, Interaction, bool]:
        modal = LengthModal()
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            await self.timeout_view()
        return modal.length_input.value, modal.interaction, timed_out

    @property
    def punishing_moderator(self) -> bool:
        """Returns true if a moderator is being punished."""
        return self._punishing_moderator

    @property
    def can_ban(self) -> bool:
        """Returns true if ban commands can be used."""
        assert isinstance(self._ctx.me, Member)
        return (
            self.is_normal_moderator(ban_members=True)
            and member_has_guild_permission(self._ctx.me, "ban_members")
            and not self.punishing_moderator
        )

    @property
    def can_unban(self) -> bool:
        """Returns true if unban commands can be used."""
        assert isinstance(self._ctx.me, Member)
        return (
            self.is_senior_moderator(ban_members=True)
            and member_has_guild_permission(self._ctx.me, "ban_members")
            and not self.punishing_moderator
        )

    @property
    def can_kick(self) -> bool:
        """Returns true if kick commands can be used."""
        assert isinstance(self._ctx.me, Member)
        return (
            self.is_junior_moderator(kick_members=True)
            and member_has_guild_permission(self._ctx.me, "kick_members")
            and not self.punishing_moderator
        )

    @property
    def can_jail(self)-> bool:
        """Returns true if jail commands can be used."""
        assert isinstance(self._ctx.me, Member)
        return (
            # TODO: implement role checks for TT guild
            member_has_guild_permission(self._ctx.me, "manage_roles")
        )

    @property
    def can_timeout(self)-> bool:
        """Returns true if timeout commands can be used.."""
        assert isinstance(self._ctx.me, Member)
        return (
            # TODO: implement role checks for TT guild
            member_has_guild_permission(self._ctx.me, "moderate_members")
        )

    def update_allowed_types(self):
        """Updates the allowed punishment type button status."""
        is_member = isinstance(self.user, Member)

        self.on_type_ban_button.disabled = not self.can_ban
        self.on_type_unban_button.disabled = not self.can_unban
        self.on_type_kick_button.disabled = not (is_member and self.can_kick)
        # Jail related
        self.on_type_jail_button.disabled = not (is_member and self._jail_role is not None and self.can_jail)
        self.on_type_kidnap_button.disabled = not (is_member and self._jail_role is not None and self.can_jail)
        self.on_type_unjail_button.disabled = not self.can_jail
        # Timeout related
        self.on_type_timeout_button.disabled = not (is_member and self.can_timeout)
        self.on_type_timeout_remove_button.disabled = not self.can_timeout
        # Warn
        self.on_type_warn_button.disabled = not is_member

    async def show_type_selection_menu(self) -> None:
        """Creates a punishment type selection menu."""
        _ = self._embed.set_footer(text="Select the punishment type")
        _ = self.clear_items()

        self.update_allowed_types()

        # Add ban/unban buttons
        # TODO: these buttons need to check for state whether user got unbanned while the menu was opening
        if not await self.is_user_banned():
            _ = self.add_item(self.on_type_ban_button)
        else:
            _ = self.add_item(self.on_type_unban_button)

        # Kick button
        _ = self.add_item(self.on_type_kick_button)

        # Add jail/unjail buttons
        # TODO: these buttons need to check for state whether user got jailed while the menu was opening
        if not await self.is_user_jailed():
            _ = self.add_item(self.on_type_jail_button)
            if is_guild_theotown(self._ctx.guild):
                _ = self.add_item(self.on_type_kidnap_button)
        else:
            _ = self.add_item(self.on_type_unjail_button)

        # Add timeout/un-timeout buttons
        # TODO: these buttons need to check for state whether user got jailed while the menu was opening
        if not await self.is_user_timed_out():
            _ = self.add_item(self.on_type_timeout_button)
        else:
            _ = self.add_item(self.on_type_timeout_remove_button)

        # Warn button
        _ = self.add_item(self.on_type_warn_button)
        # Cancel button
        _ = self.add_item(self.on_cancel_button)

    async def show_length_selection_menu(self, interaction: Interaction) -> None:
        """Shows the punishment length selection menu."""
        # Acquire mapping for lengths for punishment types
        mapping = LENGTH_MAPPING.get(str(self._punishment), None)
        if mapping is None or len(mapping) == 0:
            return await self.show_confirmation_menu(interaction)

        _ = self.clear_items()
        for button in mapping:
            _ = self.add_item(button.copy())
        _ = self.add_item(self.on_cancel_button)
        _ = self._embed.set_footer(text="Select the punishment length")
        await self._update_view(interaction)

    async def show_reason_selection_menu(self, interaction: Interaction):
        """Shows the punishment reason selection menu."""
        # Acquire mapping for reasons for punishment types
        mapping = REASON_MAPPING.get(str(self._punishment), None)
        if mapping is None or len(mapping) == 0:
            return await self.show_length_selection_menu(interaction)

        _ = self.clear_items()
        for button in mapping:
            _ = self.add_item(button.copy())
        _ = self.add_item(self.on_cancel_button)
        _ = self._embed.set_footer(text="Select reason for the punishment")
        await self._update_view(interaction)

    async def show_confirmation_menu(self, interaction: Interaction):
        """Shows the punishment confirmation menu."""
        _ = self.clear_items()
        _ = self.add_item(self.on_confirm_button)
        _ = self.add_item(self.on_cancel_button)
        _ = self._embed.set_footer(text="Confirm or cancel the punishment")
        await self._update_view(interaction)

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def on_confirm_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Reacts to the punishment confirmation button."""
        await interaction.response.defer()
        self.stop()

        assert self.punishment
        await self.punishment.issue()

        # Regardless, we clean up
        return await self.finalize_view(
            interaction,
            self.punishment.public_message_issue_embed,
            self.punishment.public_message_issue_file
        )

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red)
    async def on_cancel_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Reacts to the cancel button."""
        await self.close_view(interaction)

    """Punishment buttons"""

    @discord.ui.button(label='Ban', style=discord.ButtonStyle.red, emoji='🔨')
    async def on_type_ban_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Reacts to the ban type button."""
        self.punishment = Ban(
            self._api, self.guild,
            channel=self.channel, moderator=self.moderator, user=self.user,
            appeal_url=self._config.appeal_url
        )
        await self.show_reason_selection_menu(interaction)

    @discord.ui.button(label='Unban', style=discord.ButtonStyle.red, emoji='🔨')
    async def on_type_unban_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Reacts to the unban type button."""
        self.punishment = Ban(
            self._api, self.guild,
            channel=self.channel, moderator=self.moderator, user=self.user
        )
        await interaction.response.defer()
        self.stop()
        await self.punishment.revoke(reason=f"Unbanned by {str(self.moderator)}")
        await self.finalize_view(interaction, self.punishment.public_message_revoke_embed)

    @discord.ui.button(label='Kick', style=discord.ButtonStyle.gray)
    async def on_type_kick_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Reacts to the kick type button."""
        assert isinstance(self.user, Member)
        self.punishment = Kick(
            self._api, self.guild,
            channel=self.channel, moderator=self.moderator, user=self.user
        )
        await self.show_reason_selection_menu(interaction)

    @discord.ui.button(label='Jail', style=discord.ButtonStyle.gray)
    async def on_type_jail_button(self, interaction: discord.Interaction, _: discord.ui.Button[Self]):
        """Reacts to the jail type button."""
        assert isinstance(self.user, Member)
        assert self._jail_role
        self.punishment = Jail(
            self._api, self.guild,
            channel=self.channel, moderator=self.moderator, user=self.user,
            role=self._jail_role
        )
        await self.show_reason_selection_menu(interaction)

    @discord.ui.button(label='Kidnap', style=discord.ButtonStyle.gray)
    async def on_type_kidnap_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Reacts to the kidnap type button."""
        assert isinstance(self.user, Member)
        assert self._jail_role
        self.punishment = Jail(
            self._api, self.guild,
            channel=self.channel, moderator=self.moderator, user=self.user,
            role=self._jail_role, kidnapping=True
        )
        await self.show_reason_selection_menu(interaction)

    @discord.ui.button(label='Release from jail', style=discord.ButtonStyle.gray)
    async def on_type_unjail_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Reacts to the unjail type button."""
        assert isinstance(self.user, Member)
        assert self._jail_role
        self.punishment = Jail(
            self._api, self.guild,
            channel=self.channel, moderator=self.moderator, user=self.user,
            role=self._jail_role
        )
        await interaction.response.defer()
        self.stop()
        await self.punishment.revoke(reason=f"Released by {str(self.moderator)}")
        await self.finalize_view(interaction, self.punishment.public_message_revoke_embed)

    @discord.ui.button(label='Time-out', style=discord.ButtonStyle.gray)
    async def on_type_timeout_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Reacts to the timeout type button."""
        assert isinstance(self.user, Member)
        self.punishment = Timeout(
            self._api, self.guild,
            channel=self.channel, moderator=self.moderator, user=self.user
        )
        await self.show_reason_selection_menu(interaction)

    @discord.ui.button(label='Remove time-out', style=discord.ButtonStyle.gray)
    async def on_type_timeout_remove_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Reacts to the timeout removal type button."""
        assert isinstance(self.user, Member)
        self.punishment = Timeout(
            self._api, self.guild,
            channel=self.channel, moderator=self.moderator, user=self.user
        )
        await interaction.response.defer()
        self.stop()
        await self.punishment.revoke(reason=f"Time out removed by {str(self.moderator)}")
        await self.finalize_view(interaction, self.punishment.public_message_revoke_embed)

    @discord.ui.button(label='Warn', style=discord.ButtonStyle.gray, emoji='⚠️')
    async def on_type_warn_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Reacts to the warn type button."""
        assert isinstance(self.user, Member)
        self.punishment = Warning(
            self._api, self.guild,
            channel=self.channel, moderator=self.moderator, user=self.user
        )
        await self.show_reason_selection_menu(interaction)

    """Utility"""

    @override
    def stop(self) -> None:
        """Stops listening to all and any interactions for this view."""
        _ = self.clear_items()
        return super().stop()

    """???"""

    @override
    async def error_view(self, interaction: Interaction):
        _ = self._embed.set_footer(text="Moderation menu has encountered an error")
        self._embed.colour = Colour.red()
        await self.finalize_view(interaction)

    @override
    async def timeout_view(self):
        _ = self._embed.set_footer(text="Moderation menu has timed out")
        self._embed.colour = Colour.red()
        await self.finalize_view(None)

    @override
    async def close_view(self, interaction: Interaction) -> None:
        _ = self._embed.set_footer(text="Punishment creation has been cancelled")
        self._embed.colour = Colour.red()
        await self.finalize_view(interaction)

    @override
    async def finalize_view(
        self,
        interaction: Interaction | None,
        embed: Embed | None = None,
        file: File | None = None
    ) -> None:
        """Removes all buttons and updates the interface. No more calls can be done to the interface."""
        await super().finalize_view(interaction, embed, file)
        await self._cog.unlock_punishment_menu(self.guild.id, self.user.id) # Unlock semaphore


class UserSemaphoreDict(TypedDict):
    semaphore: asyncio.Semaphore
    message_id: int | None
    message_url: str | None
    created: datetime.datetime


def is_not_pinned(message: Message):
    return not message.pinned

async def purge_amount(ctx: Context[Pidroid], channel: MessageableGuildChannel, amount: int, check: Callable[[Message], bool]) -> list[Message]:
    """
    Purges a specified amount of messages from the specified channel.
    
    Performs input validation by throwing BadArgument exceptions.
    """
    if amount <= 0:
        raise BadArgument("That's not a valid amount!")

    # Evan proof
    if amount > 500:
        raise BadArgument("The maximum amount of messages I can purge at once is 500!")

    #await ctx.message.delete(delay=0)
    return await channel.purge(before=Object(id=ctx.message.id), limit=amount, check=check)

async def purge_after(ctx: Context[Pidroid], channel: MessageableGuildChannel, message_id: int, check: Callable[[Message], bool]) -> list[Message]:
    """
    Purges messages after a specified message ID from the specified channel.
    """
    return await channel.purge(before=Object(id=ctx.message.id), after=Object(id=message_id), check=check)

class ModerationCommandCog(commands.Cog):
    """This class implements cog which contains commands for moderation."""

    def __init__(self, client: Pidroid):
        super().__init__()
        self.client = client
        # {GUILD_ID: {USER_ID: UserSemaphoreDict}}
        self.user_semaphores: dict[int, dict[int, UserSemaphoreDict]] = {}
        _ = self.unlock_semaphores.start()

    @override
    async def cog_unload(self):
        self.unlock_semaphores.stop()

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: RawMessageDeleteEvent) -> None:
        """Handles removal of semaphore from users if their modmenu message was deleted."""
        if payload.guild_id is None:
            return

        guild_semaphores = self.user_semaphores.get(payload.guild_id)
        if guild_semaphores is None:
            return

        for user_id in guild_semaphores.copy().keys():
            if guild_semaphores[user_id]["message_id"] is not None and guild_semaphores[user_id]["message_id"] == payload.message_id:
                await self.unlock_punishment_menu(payload.guild_id, user_id)
                return

    @tasks.loop(minutes=10)
    async def unlock_semaphores(self) -> None:
        current_timestamp = utcnow().timestamp()
        for guild_id in self.user_semaphores.copy():
            for member_id in self.user_semaphores[guild_id].copy():
                item = self.user_semaphores[guild_id][member_id]
                if current_timestamp - item["created"].timestamp() > 10 * 60:
                    await self.unlock_punishment_menu(guild_id, member_id)

    @unlock_semaphores.before_loop
    async def before_unlock_semaphores(self) -> None:
        await self.client.wait_until_guild_configurations_loaded()

    def _create_semaphore_if_not_exist(
        self,
        guild_id: int, user_id: int,
        message_id: int | None = None,
        message_url: str | None = None
    ) -> asyncio.Semaphore:
        if self.user_semaphores.get(guild_id) is None:
            self.user_semaphores[guild_id] = {}
        user = self.user_semaphores[guild_id].get(user_id)
        if user is None:
            self.user_semaphores[guild_id][user_id] = {
                "semaphore": asyncio.Semaphore(1),
                "message_url": message_url,
                "message_id": message_id,
                "created": utcnow()
            }
        return self.user_semaphores[guild_id][user_id]["semaphore"]

    async def lock_punishment_menu(
        self,
        guild_id: int, user_id : int,
        message_id: int | None = None,
        message_url: str | None = None
    ) -> None:
        sem = self._create_semaphore_if_not_exist(guild_id, user_id, message_id, message_url)
        _ = await sem.acquire()

    async def unlock_punishment_menu(self, guild_id: int, user_id: int) -> None:
        sem = self._create_semaphore_if_not_exist(guild_id, user_id)
        sem.release()
        # Save memory with this simple trick
        _ = self.user_semaphores[guild_id].pop(user_id)

    def get_user_semaphore(self, guild_id: int, user_id: int) -> UserSemaphoreDict | None:
        guild = self.user_semaphores.get(guild_id)
        if guild is None:
            return None
        sem = guild.get(user_id)
        if sem is None:
            return None
        return sem

    def is_semaphore_locked(self, guild_id: int, user_id: int) -> bool:
        sem = self.get_user_semaphore(guild_id, user_id)
        if sem is not None and sem["semaphore"].locked():
            return True
        return False

    @commands.hybrid_group(
        name="purge",
        brief="Removes messages from the channel, that are not pinned.",
        info="""
        Removes messages from the channel, that are not pinned.
        The amount corresponds to the amount of messages to search.
        If a message is referenced, messages after it will be removed.
        """,
        usage='[amount]',
        category=ModerationCategory,
        invoke_without_command=True,
        fallback="any"
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True)
    @command_checks.can_purge()
    @commands.guild_only()
    async def purge_command(self, ctx: Context[Pidroid], amount: int | None = None):
        if ctx.invoked_subcommand is None:

            if amount and ctx.message.reference and ctx.message.reference.message_id:
                raise BadArgument("You cannot purge by message amount and message reference!")

            message_id = None
            if ctx.message.reference and ctx.message.reference.message_id:
                message_id = ctx.message.reference.message_id

            if amount is None and message_id is None:
                raise BadArgument("Please specify the amount of messages to purge!")

            assert isinstance(ctx.channel, MessageableGuildChannelTuple)
            if message_id:
                deleted = await purge_after(ctx, ctx.channel, message_id, is_not_pinned)
            else:
                assert amount
                deleted = await purge_amount(ctx, ctx.channel, amount, is_not_pinned)
            _ = await ctx.send(f'Purged {len(deleted)} message(s)!', delete_after=2.0)

    @purge_command.command(
        name="user",
        brief="Removes a specified amount of messages sent by specified user, that are not pinned.",
        info="""
        Removes a specified amount of messages sent by specified user, that are not pinned.
        The amount corresponds to the amount of messages to search, not purge.
        If a message is referenced, messages after it will be removed.
        """,
        usage="<user> [amount]",
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True)
    @command_checks.can_purge()
    @commands.guild_only()
    async def purge_user_command(self, ctx: Context[Pidroid], member: Member, amount: int | None = None):
        def is_member(message: Message):
            return message.author.id == member.id and not message.pinned
        
        if amount and ctx.message.reference and ctx.message.reference.message_id:
            raise BadArgument("You cannot purge by message amount and message reference!")

        message_id = None
        if ctx.message.reference and ctx.message.reference.message_id:
            message_id = ctx.message.reference.message_id

        if amount is None and message_id is None:
            raise BadArgument("Please specify the amount of messages to purge!")

        assert isinstance(ctx.channel, MessageableGuildChannelTuple)
        if message_id:
            deleted = await purge_after(ctx, ctx.channel, message_id, is_member)
        else:
            assert amount
            deleted = await purge_amount(ctx, ctx.channel, amount, is_member)
        _ = await ctx.send(f'Purged {len(deleted)} message(s)!', delete_after=2.0)

    @commands.command(hidden=True)
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, attach_files=True)
    @command_checks.is_junior_moderator(manage_messages=True)
    @commands.guild_only()
    async def deletethis(self, ctx: Context[Pidroid]):
        assert isinstance(ctx.channel, MessageableGuildChannelTuple)
        await ctx.message.delete(delay=0)
        _ = await ctx.channel.purge(limit=1)
        _ = await ctx.send(file=File(Resource('delete_this.png')))


    @commands.hybrid_command(
        name="modmenu",
        brief="Open user moderation and punishment menu.",
        usage="<user/member>",
        aliases=['punish'],
        category=ModerationCategory
    )
    @app_commands.describe(user="Member or user you are trying to punish.")
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def moderation_menu_command(
        self,
        ctx: Context[Pidroid],
        user: Member | User
    ):
        assert ctx.guild
        assert isinstance(ctx.message.author, Member)

        conf = await self.client.fetch_guild_configuration(ctx.guild.id)

        # Check initial permissions
        if not is_guild_moderator(ctx.message.author):
            raise BadArgument("You need to be a moderator to run this command!")

        if user.bot:
            raise BadArgument("You cannot punish bots, that would be pointless.")

        # Prevent moderator from punishing himself
        if user.id == ctx.message.author.id:
            raise BadArgument("You cannot punish yourself! That's what PHP is for.")

        # Generic check to only invoke the menu if author is a moderator
        is_moderator = isinstance(user, Member) and is_guild_moderator(user)
        if is_moderator and not conf.allow_to_punish_moderators:
            raise BadArgument("You are not allowed to punish a moderator!")

        if isinstance(user, Member) and user.top_role > ctx.guild.me.top_role:
            raise BadArgument("Specified member is above me!")

        if isinstance(user, Member) and user.top_role == ctx.guild.me.top_role:
            raise BadArgument("Specified member shares the same role as I do, I cannot punish them!")

        if isinstance(user, Member) and user.top_role >= ctx.message.author.top_role:
            raise BadArgument("Specified member is above or shares the same role with you!")
        
        sem = self.get_user_semaphore(ctx.guild.id, user.id)
        if sem is not None and sem["semaphore"].locked():
            raise BadArgument(f"The moderation menu is already open for the user at {sem['message_url']}")

        menu = ModerationMenu(ctx, user, is_moderator)
        await menu.display()

    @moderation_menu_command.error
    async def handle_moderation_menu_command_error(self, ctx: Context[Pidroid], error: Exception):
        if isinstance(error, MissingRequiredArgument):
            if error.param.name == "user":
                return await notify(ctx, "Please specify the member or the user you are trying to punish!")

        if isinstance(error, BadUnionArgument):
            if error.param.name == "user":
                for _err in error.errors:
                    if isinstance(_err, UserNotFound):
                        return await notify(ctx, str(_err))
        setattr(error, 'unhandled', True)

    @commands.hybrid_command(
        name="suspend",
        brief='Immediately suspends member\'s ability to send messages for a week.',
        usage='<member>',
        category=ModerationCategory
    )
    @app_commands.describe(member="Member you are trying to suspend.")
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, moderate_members=True)
    @command_checks.is_junior_moderator(moderate_members=True)
    @commands.guild_only()
    async def suspend_command(
        self,
        ctx: Context[Pidroid],
        member: Member
    ):
        assert ctx.guild
        assert isinstance(ctx.message.author, Member)
        assert isinstance(ctx.channel, MessageableGuildChannelTuple)
        
        conf = await self.client.fetch_guild_configuration(ctx.guild.id)
        
        if member.bot:
            raise BadArgument("You cannot suspend bots, that would be pointless.")

        if member.id == ctx.message.author.id:
            raise BadArgument("You cannot suspend yourself!")

        if member.top_role >= ctx.message.author.top_role:
            raise BadArgument("Specified member is above or shares the same role with you, you cannot suspend them!")

        if member.top_role > ctx.guild.me.top_role:
            raise BadArgument("Specified member is above me, I cannot suspend them!")

        sem = self.get_user_semaphore(ctx.guild.id, member.id)
        if sem is not None and sem["semaphore"].locked():
            raise BadArgument(f"There's a moderation menu open for the member at {sem['message_url']}, I cannot manage them.")

        if is_guild_moderator(member) and not conf.allow_to_punish_moderators:
            raise BadArgument("You cannot suspend a moderator!")

        t = Timeout(self.client.api, ctx.guild, channel=ctx.channel, moderator=ctx.author, user=member)
        t.reason = "Suspended communications"
        t.set_length(timedelta(days=7))
        await t.issue()
        await ctx.reply(embed=t.public_message_issue_embed)

    @commands.command(
        name="punish-bunny",
        brief='Bans (times out) bunny for 4 weeks.',
        hidden=True,
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, moderate_members=True)
    @command_checks.is_junior_moderator(moderate_members=True)
    @commands.guild_only()
    async def punish_bunny_command(
        self,
        ctx: Context[Pidroid]
    ):
        assert ctx.guild
        assert isinstance(ctx.message.author, Member)
        assert isinstance(ctx.channel, MessageableGuildChannelTuple)

        member = await self.client.get_or_fetch_member(ctx.guild, BUNNY_ID)

        if member is None:
            raise BadArgument("I could not find Bunny in this server.")

        if member.top_role >= ctx.message.author.top_role:
            raise BadArgument("Bunny is above or shares the same role with you, you cannot punish her!")

        if member.top_role > ctx.guild.me.top_role:
            raise BadArgument("Bunny is above me, I cannot punish her!")
        
        timed_out_until = delta_to_datetime(timedelta(weeks=4))

        _ = await member.edit(reason=":)", timed_out_until=timed_out_until)
        _ = await ctx.reply(f"{user_mention(BUNNY_ID)}, can you hear me now?")

async def setup(client: Pidroid):
    await client.add_cog(ModerationCommandCog(client))
