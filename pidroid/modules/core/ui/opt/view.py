import enum

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from discord import ButtonStyle, ChannelType, Guild, Interaction, ui
from typing import Generic, Self, TypeVar, override

from pidroid.modules.core.ui.opt.control import BooleanControl, ChannelControl, Control, FloatControl, ReadonlyControl, StringControl, SupportsItems
from pidroid.modules.core.ui.opt.impl import ChannelOptionImpl, FloatOptionImpl, StringInputModal, StringOptionImpl


@dataclass
class BaseViewState:
    """
    A base class for the state of a view.
    This class is used to store the state of the view and is passed to the view when it is created.
    """
    current_control_id: enum.Enum | None = None


StateT = TypeVar('StateT', bound=BaseViewState)


class StageBasedContainerView(ABC, ui.LayoutView, Generic[StateT]):
    def __init__(
        self,
        *,
        initial_state: StateT,
        timeout: int = 180,
    ):
        super().__init__(timeout=timeout)
        self.state: StateT = initial_state

    @abstractmethod
    def get_action_row_items(self) -> Sequence[ui.Item[Self]]:
        """
        This method should be implemented by subclasses to return a list of items for action rows.
        """
        raise NotImplementedError("Subclasses must implement get_action_row_items method.")

    def get_action_rows(self) -> Sequence[ui.ActionRow[Self]]:
        items = self.get_action_row_items()
        if not items:
            return []

        rows: list[ui.ActionRow[Self]] = []
        current_row = ui.ActionRow[Self]()
        for item in items:
            # If the item is a select, we need to handle it specially
            # as it can only be the only item in the row
            if isinstance(item, ui.ChannelSelect) or isinstance(item, ui.RoleSelect):
                # If current row has items, we need to create a new row for the select
                if current_row.children:
                    # If the current row has items, add it to the list of rows
                    rows.append(current_row)
                    # Create a new row for the select and add it to the list
                    rows.append(ui.ActionRow[Self](item))
                # If there's no children
                else:
                    # If the current row is empty, we can simply create a new row with the select
                    # and add it to the list
                    rows.append(ui.ActionRow[Self](item))
                continue

            # If the current row has 5 items, we need to create a new row
            if len(current_row.children) >= 5:
                rows.append(current_row)
                current_row = ui.ActionRow[Self]()
    
            current_row.add_item(item)
        
        # If there's any items left in the current row, we need to add it to the list of rows
        if current_row.children:
            rows.append(current_row)
        return rows

    def build_container(self) -> ui.Container[Self]:
        return ui.Container[Self]()

    def build(self):
        """
        Builds the view by clearing existing items and adding the container and action rows.
        """
        self.clear_items()
        self.add_item(self.build_container())
        for row in self.get_action_rows():
            self.add_item(row)

    async def update(self, interaction: Interaction | None) -> None:
        print("Updating view with state:", self.state)
        self.build()
        if interaction is not None:
            await interaction.response.edit_message(view=self)

@dataclass
class MyStageDict(BaseViewState):
    name: str | None = None
    channel_id: int | None = None
    ends_at: float | None = None
    winner_count: int = 1
    prize: str | None = None

    # This is used to determine if the view is in a wizard mode.
    # If True, the view will be used in a wizard-like flow.
    in_wizard: bool = True

class ImplView(StageBasedContainerView[MyStageDict]):

    class ControlId(enum.Enum):
        NAME = "name"
        CHANNEL = "channel"
        DURATION = "duration"
        WINNER_COUNT = "winner_count"
        PRIZE = "prize"

    def __init__(
        self,
        *,
        timeout: int = 180,
        guild: Guild
    ):
        super().__init__(
            timeout=timeout,
            initial_state=MyStageDict()
        )
        self.__guild = guild
        self.__custom_action_items: list[ui.Item[Self]] = []

    @override
    def build_container(self):
        container = super().build_container()

        container.add_item(ui.TextDisplay("# Creating a New Giveaway"))
        container.add_item(ui.Separator())

        controls = self.build_controls()
        if self.state.in_wizard and self.state.current_control_id is None:
            self.state.current_control_id = ImplView.ControlId.NAME
        for control in controls:
            container.add_item(control.as_layout_section())
            container.add_item(ui.Separator())
        
        if self.state.current_control_id:
            container.add_item(
                ui.TextDisplay(
                    f"-# Currently editing: {self.state.current_control_id.value}"
                )
            )
        else:
            container.add_item(
                ui.TextDisplay(
                    "-# If the information looks correct, please click the submit button."
                )
            )

        return container

    async def on_name_update(self, interaction: Interaction, value: str) -> None:
        """
        Callback for when the name control is updated.
        This method is called when the user updates the name of the giveaway.
        """
        self.state.name = value
        if self.state.in_wizard:
            self.state.current_control_id = ImplView.ControlId.CHANNEL
        else:
            self.state.current_control_id = None
        await self.update(interaction)

    async def on_channel_update(self, interaction: Interaction, channel_ids: list[int]) -> None:
        """
        Callback for when the channel control is updated.
        This method is called when the user selects a channel for the giveaway.
        """
        channel_id = channel_ids[0] if channel_ids else None
        self.state.channel_id = channel_id
        if self.state.in_wizard:
            self.state.current_control_id = ImplView.ControlId.DURATION
        else:
            self.state.current_control_id = None
        await self.update(interaction)

    async def on_duration_update(self, interaction: Interaction, value: float) -> None:
        """
        Callback for when the duration control is updated.
        This method is called when the user updates the duration of the giveaway.
        """
        self.state.ends_at = value

        if self.state.in_wizard:
            self.state.current_control_id = ImplView.ControlId.WINNER_COUNT
        else:
            self.state.current_control_id = None

        await self.update(interaction)

    async def on_winner_count_update(self, interaction: Interaction, value: float) -> None:
        """
        Callback for when the winner count control is updated.
        This method is called when the user updates the number of winners for the giveaway.
        """
        self.state.winner_count = int(value)

        if self.state.in_wizard:
            self.state.current_control_id = ImplView.ControlId.PRIZE
        else:
            self.state.current_control_id = None

        await self.update(interaction)

    async def on_prize_update(self, interaction: Interaction, value: str) -> None:
        """
        Callback for when the prize control is updated.
        This method is called when the user updates the prize for the giveaway.
        """
        self.state.prize = value
        self.state.in_wizard = False # End the wizard mode after prize is set
        self.state.current_control_id = None # Reset current control
        await self.update(interaction)

    async def on_channel_reselect(self, interaction: Interaction, items: list[ui.Item[Self]]) -> None:
        #self.__custom_action_items = items
        self.state.current_control_id = ImplView.ControlId.CHANNEL
        await self.update(interaction)

    def build_controls(self) -> Sequence[Control[Self]]:

        self.__controls: dict[enum.Enum, Control[Self]] = {
            ImplView.ControlId.NAME: StringControl[Self, str](
                emoji=":label:",
                name="Name",
                description="The name of the giveaway.",
                value=self.state.name,
                impl=StringOptionImpl[Self, str](
                    modal=StringInputModal
                ),
                callback=self.on_name_update,
                disabled=self.state.in_wizard or self.state.current_control_id == ImplView.ControlId.NAME
            ),
            ImplView.ControlId.CHANNEL: ChannelControl[Self](
                emoji=":loudspeaker:",
                name="Channel",
                description="The channel where the giveaway will be held.",
                value=self.state.channel_id,
                guild=self.__guild,
                impl=ChannelOptionImpl(
                    channel_types=[ChannelType.text]
                ),
                callback=self.on_channel_update,
                on_send_custom_buttons=self.on_channel_reselect,
                disabled=self.state.in_wizard or self.state.current_control_id == ImplView.ControlId.CHANNEL
            ),
            ImplView.ControlId.DURATION: FloatControl[Self](
                emoji=":hourglass_flowing_sand:",
                name="Duration",
                description="The duration of the giveaway in seconds.",
                value=self.state.ends_at or 3600.0,
                #impl=FloatControl.FloatOptionImpl[Self, float](),
                callback=self.on_duration_update,
                disabled=self.state.in_wizard or self.state.current_control_id == ImplView.ControlId.DURATION
            ),
            ImplView.ControlId.WINNER_COUNT: FloatControl[Self](
                emoji=":trophy:",
                name="Winner Count",
                description="The number of winners for the giveaway.",
                value=self.state.winner_count,
                impl=FloatOptionImpl(
                    min_value=1.0,
                    max_value=100.0,
                    round_to=1,
                    placeholder="Enter the number of winners (1-100)",
                ),
                callback=self.on_winner_count_update,
                disabled=self.state.in_wizard or self.state.current_control_id == ImplView.ControlId.WINNER_COUNT
            ),
            ImplView.ControlId.PRIZE: StringControl[Self, str](
                emoji=":gift:",
                name="Prize",
                description="The prize for the giveaway.",
                value=self.state.prize,
                impl=StringOptionImpl[Self, str](
                    modal=StringInputModal
                ),
                callback=self.on_prize_update,
                disabled=self.state.in_wizard or self.state.current_control_id == ImplView.ControlId.PRIZE
            ),
        }

        return [
            self.__controls[ImplView.ControlId.NAME],
            self.__controls[ImplView.ControlId.CHANNEL],
            self.__controls[ImplView.ControlId.DURATION],
            self.__controls[ImplView.ControlId.WINNER_COUNT],
            self.__controls[ImplView.ControlId.PRIZE],
        ]

    @override
    def get_action_row_items(self) -> Sequence[ui.Item[Self]]:

        items: list[ui.Item[Self]] = []

        # If there are custom action items, add them first
        if self.__custom_action_items:
            items.extend(self.__custom_action_items)
            self.__custom_action_items.clear()


        if self.state.current_control_id is not None:
            control = self.__controls[self.state.current_control_id]
            assert isinstance(control, SupportsItems), "Control must implement SupportsItems to be used in action rows"
            items.append(control.as_item())
        else:
            items.append(
                ui.Button(
                    label="Submit",
                    style=ButtonStyle.success,
                    disabled=True
                )
            )
        
        # Add a button to close the view
        items.append(
            ui.Button(
                label="Close",
                style=ButtonStyle.danger,
                disabled=True
            )
        )
        return items
    
    @override
    async def on_error(self, interaction: Interaction, error: Exception, item: ui.Item[Self]) -> None:
        print(f"Error in ImplView: {error}")
        return await super().on_error(interaction, error, item)

