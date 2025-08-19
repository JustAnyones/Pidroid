import datetime

from dateutil.relativedelta import relativedelta
from datetime import timedelta
from discord import Guild, ui, ButtonStyle, Interaction, Role
from typing import TYPE_CHECKING, Any, Callable, Literal, NotRequired, TypeVar, TypedDict, override

from pidroid.models.exceptions import InvalidDuration
from pidroid.modules.moderation.models.dataclass import PunishmentInfo
from pidroid.modules.moderation.models.types import PunishmentMode, PunishmentType, ExpiringPunishment, Jail2, RevokeablePunishment
from pidroid.modules.moderation.ui.modmenu.modals import LengthModal, ReasonModal
from pidroid.modules.moderation.ui.modmenu.stage import MenuStage
from pidroid.utils.aliases import DiscordUser
from pidroid.utils.time import delta_to_datetime, try_convert_duration_to_relativedelta, utcnow

if TYPE_CHECKING:
    from pidroid.modules.moderation.ui.modmenu.view import ModmenuView

V = TypeVar('V', bound='ModmenuView', covariant=True)

class PunishmentSelectionButton(ui.Button[V]):
    """Button to select the punishment type."""
    def __init__(
        self,
        label: str,
        punishment_type: PunishmentType, mode: PunishmentMode = PunishmentMode.ISSUE,
        enabled: bool = False,
        callback: Callable[[PunishmentInfo], None] | None = None
    ):
        """
        Initializes a button to select a punishment type.

        Callback is a function that takes PunishmentInfo and returns None.
        Called just before the view is refreshed, useful to set additional
        information in PunishmentInfo, such as is_kidnapping.
        """

        super().__init__(label=label or punishment_type.name, style=ButtonStyle.secondary, disabled=not enabled)
        self.__punishment_type = punishment_type
        self.__mode = mode
        self.__callback = callback

    @override
    async def callback(self, interaction: Interaction):
        assert self.view
        self.view.set_punishment_type(self.__punishment_type, self.__mode)
        if self.__callback:
            self.__callback(self.view.get_info())
        await self.view.refresh_view(interaction)


class ValueButton(ui.Button[V]):
    """Base class for buttons that have a value associated with them."""
    def __init__(self, label: str | None, value: Any | None):
        super().__init__(label=label, style=ButtonStyle.gray)
        # If value doesn't exist, mark it as custom
        if value is None:
            self.label: str = label or "Custom..."
            self.style: ButtonStyle = ButtonStyle.blurple
        # If value is -1, consider it permanent and therefore colour the button red
        elif value == -1:
            self.style = ButtonStyle.red


class ReasonSelectionButton(ValueButton[V]):
    """Button to select a reason for the punishment."""
    def __init__(self, label: str | None, value: str | None):
        super().__init__(label=label, value=value)
        self.value: str | None = value

    async def custom_modal(self, interaction: Interaction) -> tuple[str | None, Interaction, bool]:
        """Opens a modal to input a custom reason for the punishment."""
        assert self.view
        modal = ReasonModal()
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()
        return modal.reason_input.value, modal.interaction, timed_out

    @override
    async def callback(self, interaction: Interaction) -> None:
        assert self.view
        value = self.value
        if value is None:
            value, interaction, timed_out = await self.custom_modal(interaction)

            if timed_out:
                await interaction.response.send_message("Punishment reason modal has timed out!", ephemeral=True)
                return

            if value is None:
                await interaction.response.send_message("Punishment reason cannot be empty!", ephemeral=True)
                return

            if len(value) > 480:
                await interaction.response.send_message("Punishment reason cannot be longer than 480 characters!", ephemeral=True)
                return

        if self.view.is_finished():
            await interaction.response.send_message("Modmenu has timed out!", ephemeral=True)
            return

        self.view.set_punishment_reason(value)
        await self.view.refresh_view(interaction)


class ExpirationSelectionButton(ValueButton[V]):
    """Button to select the expiration time for the punishment."""
    def __init__(self, label: str | None, value: timedelta | Literal[-1] | None):
        super().__init__(label, value)
        self.value: timedelta | Literal[-1] | None = value

    async def custom_modal(self, interaction: Interaction) -> tuple[str | None, Interaction, bool]:
        """Opens a modal to input a custom length for the punishment."""
        modal = LengthModal()
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()
        return modal.length_input.value, modal.interaction, timed_out

    @override
    async def callback(self, interaction: Interaction) -> None:
        assert self.view
        value = self.value
        if value is None:
            value, interaction, timed_out = await self.custom_modal(interaction)

            if timed_out:
                await interaction.response.send_message("Punishment reason modal has timed out!", ephemeral=True)
                return

            if value is None:
                await interaction.response.send_message("Punishment duration cannot be empty!", ephemeral=True)
                return

            try:
                value = try_convert_duration_to_relativedelta(value)
            except InvalidDuration as e:
                await interaction.response.send_message(str(e), ephemeral=True)
                return

            now = utcnow()
            delta = now - (now - value)

            if delta.total_seconds() < 5 * 60:
                await interaction.response.send_message("Punishment duration cannot be shorter than 5 minutes!", ephemeral=True)
                return
            
            # If the punishment is a timeout, we check if the duration is longer than 4 weeks
            # Discord does not allow timeouts longer than 4 weeks
            if self.view.get_info().punishment_type == PunishmentType.TIMEOUT:
                if delta.total_seconds() > 2419200: # 4 * 7 * 24 * 60 * 60
                    await interaction.response.send_message("Timeouts cannot be longer than 4 weeks!", ephemeral=True)
                    return

        if self.view.is_finished():
            await interaction.response.send_message("Interaction has timed out!", ephemeral=True)
            return
        
        # If the value is -1, we set the expiration to None (permanent)
        if value == -1:
            value = None

        if isinstance(value, (timedelta, relativedelta)):
            value = delta_to_datetime(value)
        
        self.view.set_punishment_expires_at(value)
        await self.view.refresh_view(interaction)


class CancelPunishmentButton(ui.Button[V]):
    """Button to cancel the punishment."""

    def __init__(self):
        super().__init__(label="Cancel", style=ButtonStyle.red)

    @override
    async def callback(self, interaction: Interaction) -> None:
        assert self.view
        self.view.set_stage(MenuStage.CANCELLED)
        await self.view.refresh_view(interaction)


class ConfirmPunishmentButton(ui.Button[V]):
    """Button to confirm the punishment."""

    def __init__(self):
        super().__init__(label="Confirm", style=ButtonStyle.success)

    @override
    async def callback(self, interaction: Interaction) -> None:
        assert self.view

        info = self.view.get_info()
        assert info.punishment_type is not None, "Punishment type is None, this should not happen."
        punishment_constructor = info.punishment_type.object_constructor

        class TypedKwargs(TypedDict):
            guild: Guild
            moderator: DiscordUser
            target: DiscordUser
            reason: str | None
            date_expire: NotRequired[datetime.datetime | None]
            jail_role:  NotRequired[Role]
            is_kidnapping: NotRequired[bool]

        kwargs: TypedKwargs = {
            "guild": info.guild,
            "moderator": info.moderator,
            "target": info.target,
            "reason": info.reason,
        }

        # If the punishment type supports expiration, we set the date_expire
        if issubclass(punishment_constructor, ExpiringPunishment):
            kwargs["date_expire"] = info.expires_at


        # Jail requires jail_role and is_kidnapping parameters
        if punishment_constructor is Jail2:
            assert info.jail_role is not None, "Jail role is None, this should not happen."
            kwargs["jail_role"] = info.jail_role
            kwargs["is_kidnapping"] = info.is_kidnapping


        # Construct the punishment object
        punishment = info.punishment_type.object_constructor(
            self.view.get_api(), **kwargs # pyright: ignore[reportCallIssue]
        )

        # Either issue or revoke the punishment based on the mode
        if info.punishment_mode == PunishmentMode.ISSUE:
            case = await punishment.issue()
            self.view.set_final_view(
                title=f"Punishment Issued (Case #{case.case_id})",
                text=punishment.public_issue_message,
                file=punishment.public_issue_file
            )
        else:
            assert isinstance(punishment, RevokeablePunishment), "Revoke mode can only be used with revokeable punishments."
            await punishment.revoke()
            self.view.set_final_view(
                title="Punishment Revoked",
                text=punishment.public_revoke_message
            )

        self.view.set_stage(MenuStage.FINISHED)
        await self.view.refresh_view(interaction)

class EditButton(ui.Button[V]):
    """
    Button to edit a concrete punishment value.
    
    This returns user to a state where they can edit the value as they could
    during the initial selection.
    For example, if the user wants to edit the reason, this button will return
    them to the state where they can select a reason or provide a custom one.

    The actual behavior of this button depends on the `stage` parameter,
    which determines what value is being edited.
    """

    def __init__(self, *, disabled: bool = False, stage: MenuStage):
        super().__init__(label="Edit", style=ButtonStyle.secondary, disabled=disabled)
        self.__stage = stage

    @override
    async def callback(self, interaction: Interaction) -> None:
        assert self.view
        self.view.set_stage(self.__stage)
        await self.view.refresh_view(interaction)
