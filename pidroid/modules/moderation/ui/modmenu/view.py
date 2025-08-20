from __future__ import annotations

import datetime
import logging

from collections.abc import Awaitable, Sequence
from discord import (
    Color,
    File,
    Interaction,
    Member,
    Message,
)
from discord.ext.commands import BadArgument, Context
from discord.ui import (
    ActionRow, Button, Container,
    Section, TextDisplay, Separator,
    MediaGallery,
    LayoutView,
)
from discord.utils import format_dt, get
from typing import Callable, Self, override

from pidroid.client import Pidroid
from pidroid.constants import EMBED_COLOUR
from pidroid.models.guild_configuration import GuildConfiguration
from pidroid.modules.moderation.models.dataclass import PunishmentInfo
from pidroid.modules.moderation.models.types import PunishmentMode, PunishmentType
from pidroid.modules.moderation.ui.modmenu.buttons import CancelPunishmentButton, ConfirmPunishmentButton, DeleteMessageDaysSelectionButton, EditButton, ExpirationSelectionButton, PunishmentSelectionButton, ReasonSelectionButton
from pidroid.modules.moderation.ui.modmenu.stage import MenuStage
from pidroid.utils.aliases import DiscordUser
from pidroid.utils.api import API
from pidroid.utils.checks import is_guild_theotown, is_user_banned

logger = logging.getLogger("pidroid.moderation.modmenu")

def create_section(title: str, value: str, button: Button[ModmenuView]) -> Section[ModmenuView]:
    """Creates a section with a title, value, and a button."""
    return Section(
        accessory=button
    ).add_item(TextDisplay(f"### {title}\n{value}"))


class MenuContainer(Container["ModmenuView"]):

    def add_punishment_type_part(self, punishment_type: PunishmentType | None, is_revocation: bool = False) -> None:
        """Adds a punishment type section to the container."""
        if punishment_type is None:
            self.add_item(TextDisplay("### Type\nSelect a punishment type"))
        else:
            if is_revocation:
                self.add_item(TextDisplay(f"### Type\nRevoking {punishment_type.name}"))
            else:
                self.add_item(TextDisplay(f"### Type\n{punishment_type}"))
        self.add_item(Separator())

    def add_reason_part(self, view: "ModmenuView", reason: str | None) -> None:
        """Adds a reason section to the container."""
        reason_value = "No reason specified"
        if reason is not None:
            reason_value = reason
        self.add_item(create_section(
            title="Reason",
            value=reason_value,
            button=EditButton(
                stage=MenuStage.EDIT_REASON,
                disabled=view.in_wizard or view.is_finished() or view.get_stage() == MenuStage.EDIT_REASON
            )
        ))
        self.add_item(Separator())

    def add_expires_part(self, view: "ModmenuView", expires_at: datetime.datetime | None) -> None:
        """Adds an expires section to the container."""
        expires_value = "Never"
        if expires_at is not None:
            expires_value = f"{format_dt(expires_at, 'F')} ({format_dt(expires_at, 'R')})"
        self.add_item(create_section(
            title="Expires at",
            value=expires_value,
            button=EditButton(
                stage=MenuStage.EDIT_DATE_EXPIRE,
                disabled=view.in_wizard or view.is_finished() or view.get_stage() == MenuStage.EDIT_DATE_EXPIRE
            )
        ))
        self.add_item(Separator())

    def add_delete_message_days_part(self, view: "ModmenuView", days: int) -> None:
        value_as_str = f"Messages that were made {days} "
        if days == 0:
            value_as_str = "No messages will be deleted"
        elif days == 1:
            value_as_str += "day ago"
        else:
            value_as_str += "days ago"

        self.add_item(create_section(
            title="Delete messages after ban",
            value=value_as_str,
            button=EditButton(
                stage=MenuStage.EDIT_DELETE_MESSAGE_DAYS,
                disabled=view.in_wizard or view.is_finished() or view.get_stage() == MenuStage.EDIT_DELETE_MESSAGE_DAYS
            )
        ))
        self.add_item(Separator())

    def add_footer_part(self, text: str) -> None:
        """Adds a footer to the container."""
        self.add_item(TextDisplay(f"-# {text}"))

    @classmethod
    def from_info(cls, view: "ModmenuView", info: PunishmentInfo) -> Self:
        """Creates a new instance of MenuContainer from PunishmentInfo."""
        container = cls()

        is_revocation = info.punishment_mode == PunishmentMode.REVOKE

        container.add_item(TextDisplay(f"# Punish {info.target}"))
        container.add_item(Separator())

        # Punishment type section
        container.add_punishment_type_part(info.punishment_type, is_revocation)
        
        # If we have punishment type, we can add the reason and expires sections
        if info.punishment_type:
            container.add_reason_part(view, info.reason)

            # If punishment type supports expiration, we can add the expires section
            if info.punishment_type.options.supports_expiration and not is_revocation:
                container.add_expires_part(view, info.expires_at)

            # If punishment is ban, we can add an option to select how many days of messages to delete
            if info.punishment_type == PunishmentType.BAN and not is_revocation:
                container.add_delete_message_days_part(view, info.delete_message_days)

        # Informative footer section
        if view.get_stage() == MenuStage.TIMED_OUT:
            container.add_footer_part("Moderation menu timed out.")
        elif view.get_stage() == MenuStage.CANCELLED:
            container.add_footer_part("Moderation menu cancelled by the user.")
        else:
            container.add_footer_part("Select an action below to continue | Times out in 3 minutes.")

        return container

class ModmenuView(LayoutView):
    
    def __init__(
        self,
        *,
        api: API,
        ctx: Context[Pidroid],
        configuration: GuildConfiguration,
        target: DiscordUser,

        lock_fn: Callable[[int, int, int, str], Awaitable[None]],
        unlock_fn: Callable[[int, int], Awaitable[None]],
        is_locked_fn: Callable[[int, int], bool]
    ):
        super().__init__(timeout=180)
        assert ctx.guild is not None
        self.__api = api
        self.__ctx = ctx
        self.__configuration: GuildConfiguration = configuration
        self.__menu_stage = MenuStage.TYPE_SELECTION
        self.__message: Message | None = None
        # Whether the actions should be displayed in a wizard-like manner
        self.__wizard = True
        # Custom container for the final view state
        self.__custom_container: Container[Self] | None = None
        # Custom file to be sent with the final view state
        self.__custom_attachments: list[File] = []
        # Stores information about the punishment being issued
        # Information stored here will be used to issue/revoke the punishment
        self.__info = PunishmentInfo(
            guild=ctx.guild,
            channel_id=ctx.channel.id,
            moderator=ctx.author,
            target=target
        )
        # Stores the functions for locking and unlocking the punishment menu
        self.__lock_fn = lock_fn
        self.__unlock_fn = unlock_fn
        self.__is_locked_fn = is_locked_fn
        # Information about the target to determine what kind of actions can be performed
        self.__is_target_banned: bool = False
        self.__is_target_timed_out: bool = False
        self.__is_target_jailed: bool = False

    async def initialize(self) -> None:
        """Fully initializes the view, fetching any necessary data and reaffirming
        that target user is not locked from punishment."""
        if self.__is_locked_fn(self.__info.guild.id, self.__info.target.id):
            raise BadArgument("Semaphore is already locked")

        # Lock the punishment menu with a semaphore
        await self.__lock_fn(
            self.__info.guild.id, self.__info.target.id,
            self.__ctx.message.id,
            self.__ctx.message.jump_url
        )

        # Get the jail role if it exists
        if self.__configuration.jail_role_id is not None:
            role = self.__info.guild.get_role(self.__configuration.jail_role_id)
            if role is not None:
                self.__info.jail_role = role

        # Check if the target is banned
        self.__is_target_banned = await is_user_banned(self.__info.guild, self.__info.target)
        # Check if the target is a member and if so, check if they are timed out or jailed
        if isinstance(self.__info.target, Member):
            self.__is_target_timed_out = self.__info.target.is_timed_out()
            self.__is_target_jailed = (
                self.__info.jail_role is not None
                and get(self.__info.guild.roles, id=self.__info.jail_role.id) in self.__info.target.roles
                and await self.__api.is_currently_jailed(self.__info.guild.id, self.__info.target.id)
            )

        self._build_view()

    def set_message(self, message: Message) -> None:
        """Sets the message for the view, used to update the view later if interaction is not available."""
        self.__message = message

    async def _cleanup(self):
        """Cleans up the view, releasing the associated lock on the user."""
        if self.__is_locked_fn(self.__info.guild.id, self.__info.target.id):
            await self.__unlock_fn(self.__info.guild.id, self.__info.target.id)

    def _build_view(self) -> None:
        """Builds the view with the current information."""
        # If we have a custom container, we clear the items and add it
        if self.__custom_container is not None:
            self.clear_items()
            self.add_item(self.__custom_container)
            return

        container = MenuContainer.from_info(self, self.__info)
        self.clear_items()
        self.add_item(container)

        items = self.__get_action_row_items()
        if not items:
            return

        # only 5 items can be added to an action row, if there's more, add them to a new row
        if len(items) > 5:
            action_rows = [ActionRow(*items[i:i + 5]) for i in range(0, len(items), 5)]
        else:
            action_rows = [ActionRow(*items)]

        for row in action_rows:
            self.add_item(row)

    def get_punishment_buttons(self) -> list[PunishmentSelectionButton[Self]]:
        """Returns a list of punishment selection buttons based on the target's and moderator's status."""
        buttons: list[PunishmentSelectionButton[Self]] = []
        is_member = isinstance(self.__info.target, Member)

        # Ban button
        if self.__is_target_banned:
            buttons.append(
                PunishmentSelectionButton[Self](
                    "Unban", PunishmentType.BAN, PunishmentMode.REVOKE,
                    PunishmentType.BAN.can_be_revoked(self.__ctx)
                )
            )
        else:
            buttons.append(
                PunishmentSelectionButton[Self](
                    "Ban", PunishmentType.BAN, PunishmentMode.ISSUE,
                    PunishmentType.BAN.can_be_issued(self.__ctx)
                )
            )

        # Kick button
        buttons.append(
            PunishmentSelectionButton[Self](
                "Kick", PunishmentType.KICK, PunishmentMode.ISSUE,
                PunishmentType.KICK.can_be_issued(self.__ctx) and is_member
            )
        )

        # Jail button
        if self.__is_target_jailed:
            buttons.append(PunishmentSelectionButton[Self](
                "Release from Jail", PunishmentType.JAIL, PunishmentMode.REVOKE,
                PunishmentType.JAIL.can_be_revoked(self.__ctx) and is_member and self.__info.jail_role is not None
            ))
        else:
            buttons.append(PunishmentSelectionButton[Self](
                "Jail", PunishmentType.JAIL, PunishmentMode.ISSUE,
                PunishmentType.JAIL.can_be_issued(self.__ctx) and is_member and self.__info.jail_role is not None
            ))
            if is_guild_theotown(self.__ctx.guild):
                def mark_as_kidnapping(info: PunishmentInfo) -> None:
                    """Callback to mark the punishment as kidnapping."""
                    info.is_kidnapping = True
                buttons.append(PunishmentSelectionButton[Self](
                    "Kidnap", PunishmentType.JAIL, PunishmentMode.ISSUE,
                    PunishmentType.JAIL.can_be_issued(self.__ctx) and is_member and self.__info.jail_role is not None,
                    callback=mark_as_kidnapping
                ))

        # Timeout button
        if self.__is_target_timed_out:
            buttons.append(
                PunishmentSelectionButton[Self](
                    "Remove Timeout", PunishmentType.TIMEOUT, PunishmentMode.REVOKE,
                    PunishmentType.TIMEOUT.can_be_revoked(self.__ctx) and is_member
                )
            )
        else:
            buttons.append(
                PunishmentSelectionButton[Self](
                    "Timeout", PunishmentType.TIMEOUT, PunishmentMode.ISSUE,
                    PunishmentType.TIMEOUT.can_be_issued(self.__ctx) and is_member
                )
            )

        # Warn button
        buttons.append(
            PunishmentSelectionButton[Self](
                "Warn", PunishmentType.WARNING, PunishmentMode.ISSUE,
                PunishmentType.WARNING.can_be_issued(self.__ctx) and is_member
            )
        )

        return buttons

    @property
    def in_wizard(self) -> bool:
        """Returns whether the view is in wizard mode."""
        return self.__wizard

    def __get_action_row_items(self) -> Sequence[Button[Self]]:
        """Returns a list of buttons for the action row."""
        # If we are in the type selection stage, we return the punishment type buttons
        if self.__menu_stage == MenuStage.TYPE_SELECTION:
            return self.get_punishment_buttons() + [CancelPunishmentButton[Self]()]
        
        # If we are in the reason edit stage, we return the reason selection buttons
        if self.__menu_stage == MenuStage.EDIT_REASON:
            assert self.__info.punishment_type
            return [ReasonSelectionButton[Self](label, value) for label, value in self.__info.punishment_type.reasons] + [
                ReasonSelectionButton[Self](None, None),  # Custom reason button
                CancelPunishmentButton[Self]()
            ]
        
        # If we are in the expires edit stage, we return the expiration selection buttons
        if self.__menu_stage == MenuStage.EDIT_DATE_EXPIRE:
            assert self.__info.punishment_type
            return [ExpirationSelectionButton[Self](label, value) for label, value in self.__info.punishment_type.lengths] + [
                ExpirationSelectionButton[Self](None, None),  # Custom length button
                CancelPunishmentButton[Self]()
            ]

        if self.__menu_stage == MenuStage.EDIT_DELETE_MESSAGE_DAYS:
            return [
                DeleteMessageDaysSelectionButton[Self]("Don't delete messages", 0),
                DeleteMessageDaysSelectionButton[Self]("Last day", 1),
                DeleteMessageDaysSelectionButton[Self]("Last week", 7),
                DeleteMessageDaysSelectionButton[Self](None, None),
                CancelPunishmentButton[Self]()
            ]
        
        # If we are in the confirmation stage, we return the confirm and cancel buttons
        if self.__menu_stage == MenuStage.CONFIRMATION:
            return [ConfirmPunishmentButton[Self](), CancelPunishmentButton[Self]()]

        # By this point, we are either in the cancelled stage or an unknown stage,
        # in which case we return an empty list.
        return []

    def get_api(self) -> API:
        """Returns the API instance."""
        return self.__api

    def get_stage(self) -> MenuStage:
        """Returns the current stage of the menu."""
        return self.__menu_stage

    def get_info(self) -> PunishmentInfo:
        """Returns the current punishment information."""
        return self.__info

    def set_stage(self, stage: MenuStage) -> None:
        """Sets the current stage of the menu."""
        self.__menu_stage = stage
        if self.__menu_stage == MenuStage.CONFIRMATION:
            self.__wizard = False

    def set_final_view(
        self,
        title: str,
        text: str,
        accent_color: Color | None = None,
        file: File | None = None,
    ) -> None:
        """Sets the final view contents."""
        if accent_color is None:
            accent_color = Color(EMBED_COLOUR)
        self.__custom_container = Container(accent_color=accent_color)
        self.__custom_container.add_item(TextDisplay(f"### {title}\n{text}"))
        if file is not None:
            self.__custom_container.add_item(
                MediaGallery[Self]().add_item(
                    media=file
                )
            )
            self.__custom_attachments = [file]

    def set_punishment_type(self, punishment_type: PunishmentType, mode: PunishmentMode) -> None:
        """Sets the punishment type."""
        self.__info.punishment_type = punishment_type
        self.__info.punishment_mode = mode
        if not self.__wizard or mode == PunishmentMode.REVOKE:
            self.set_stage(MenuStage.CONFIRMATION)
            return
        self.set_stage(MenuStage.EDIT_REASON)

    def set_punishment_reason(self, reason: str) -> None:
        """Sets the punishment reason."""
        assert self.__info.punishment_type is not None
        self.__info.reason = reason
        if not self.__wizard:
            self.set_stage(MenuStage.CONFIRMATION)
            return
        
        if self.__info.punishment_type.options.supports_expiration:
            self.set_stage(MenuStage.EDIT_DATE_EXPIRE)
        else:
            self.set_stage(MenuStage.CONFIRMATION)

    def set_punishment_expires_at(self, expires_at: datetime.datetime | None) -> None:
        """Sets the punishment expiration time."""
        self.__info.expires_at = expires_at
        self.set_stage(MenuStage.CONFIRMATION)

    def set_punishment_delete_message_days(self, days: int) -> None:
        """Sets the days to delete messages from for the punishment."""
        self.__info.delete_message_days = days
        self.set_stage(MenuStage.CONFIRMATION)

    @override
    async def on_error(self, interaction: Interaction, error: Exception, _) -> None:
        logger.error(f"An error occurred in ModmenuView: {error}", exc_info=error)
        await interaction.response.send_message(
            "An error occurred while processing your request. Please try again later.",
            ephemeral=True
        )

    @override
    async def on_timeout(self) -> None:
        self.set_stage(MenuStage.TIMED_OUT)
        await self.refresh_view(None)
        logger.debug(f"ModmenuView for {self.__info.target} timed out after {self.timeout} seconds.")

    @override
    async def interaction_check(self, interaction: Interaction) -> bool:
        """Ensure that the interaction is called by the moderator."""
        if interaction.user and interaction.user.id == self.__info.moderator.id:
            return True
        await interaction.response.send_message('This menu cannot be controlled by you!', ephemeral=True)
        return False
    
    async def refresh_view(self, interaction: Interaction | None) -> None:
        """Refreshes the view by updating the items and action rows."""
        # If the menu is cancelled or timed out,
        # we need to stop the view and perform cleanup.
        if self.__menu_stage in [MenuStage.CANCELLED, MenuStage.TIMED_OUT, MenuStage.FINISHED]:
            self.stop()  # Stop listening for interactions
            await self._cleanup() # Unlock the semaphore if it was locked

        self._build_view()

        if interaction:
            await interaction.response.edit_message(view=self, attachments=self.__custom_attachments)
            return

        if self.__message:
            await self.__message.edit(view=self, attachments=self.__custom_attachments)
            return
        
        logger.error("refresh_view method requires an interaction to be passed, or a message to be set.")
