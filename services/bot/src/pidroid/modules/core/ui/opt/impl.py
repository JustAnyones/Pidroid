from __future__ import annotations

from collections.abc import Coroutine
from dataclasses import dataclass
from discord import ChannelType, Interaction, ui
from discord.utils import MISSING
from typing import Any, Callable, Generic, TypeVar, override

V = TypeVar('V', bound='ui.view.BaseView', covariant=True)
RV = TypeVar('RV') # Return value

StringCallbackType = Callable[[Interaction, RV], Coroutine[Any, Any, None]]
FloatCallbackType = Callable[[Interaction, float], Coroutine[Any, Any, None]]
BooleanCallbackType = Callable[[Interaction], Coroutine[Any, Any, None]]
RoleSelectCallbackType = Callable[[Interaction, list[int]], Coroutine[Any, Any, None]]
ChannelSelectCallbackType = Callable[[Interaction, list[int]], Coroutine[Any, Any, None]]

class BaseTextInputButton(ui.Button[V]):
    """
    Base class for buttons that open a modal with text input.
    
    This class is designed to be subclassed for specific text input buttons.
    It provides a structure for creating a modal and handling the input from it.
    """

    def __init__(
        self,
        *,
        label: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(label=label, disabled=disabled)

    def create_modal(self) -> ui.Modal:
        """Creates a custom modal for current TextButton."""
        raise NotImplementedError

    async def on_submit(self, interaction: Interaction, modal: ui.Modal) -> None:
        raise NotImplementedError

    @override
    async def callback(self, interaction: Interaction):
        assert self.view is not None

        # This is the callback that will be called when the modal is submitted
        async def on_submit(interaction: Interaction):
            await self.on_submit(interaction, modal)

        # Construct a custom TextModal for our current button
        modal = self.create_modal()
        modal.on_submit = on_submit

        # Respond with a modal and wait for it to be sent back
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()
        # If it times out, notify the user, otherwise continue on to checking the user input
        if timed_out:
            return
            return await interaction.response.send_message("Modal has timed out!", ephemeral=True)

        # Check if parent view is timed out or no longer responds
        if self.view.is_finished():
            return
            return await interaction.response.send_message("Settings menu has timed out!", ephemeral=True)

class StringButton(BaseTextInputButton[V], Generic[V, RV]):
    def __init__(
        self,
        *,
        label: str,
        disabled: bool = False,

        modal_title: str,
        input_label: str,
        placeholder: str | None = None,

        default_value: str | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        required: bool = False,
        
        callback: StringCallbackType[RV],
    ):
        super().__init__(label=label, disabled=disabled)
        self.__modal_title = modal_title
        self.__input_label = input_label
        self.__placeholder = placeholder

        self.__default_value = default_value
        self.__min_length = min_length
        self.__max_length = max_length
        self.__required = required
        self.__callback = callback

    @override
    def create_modal(self) -> ui.Modal:
        modal = ui.Modal(title=self.__modal_title, timeout=120)
        _ = modal.add_item(ui.TextInput(
            label=self.__input_label,
            placeholder=self.__placeholder,
            default=self.__default_value,
            min_length=self.__min_length,
            max_length=self.__max_length,
            required=self.__required,
        ))
        return modal
    
    def parse_string_value(self, value: str) -> tuple[str, str | None]:
        """
        This method does the basic string validation and processing.
        It strips whitespace and checks the length of the input.
        Returns a tuple of the processed value and an error message if validation fails.
        If the value is valid, the error message will be None.
        """
        stripped_value = value.strip()

        if self.__min_length is not None and len(stripped_value) < self.__min_length:
            return "", f"Input must be at least {self.__min_length} characters long."
        
        if self.__max_length is not None and len(stripped_value) > self.__max_length:
            return "", f"Input must be at most {self.__max_length} characters long.",
    
        return stripped_value, None
    
    
    async def handle_value(self, value: str) -> tuple[RV, str | None]:
        """
        This method must be overridden to handle the value before passing it to the callback.
        It should perform any necessary validation or processing on the input value.

        This method should return a tuple of the processed value and an error message if validation fails.
        If the value is valid, the error message will be None.
        """
        raise NotImplementedError

    @override
    async def on_submit(self, interaction: Interaction, modal: ui.Modal):
        assert len(modal.children) > 0, "Modal should have at least one TextInput"
        first_item = modal.children[0]
        assert isinstance(first_item, ui.TextInput), "Expected first item to be a TextInput"
        parsed, err = await self.handle_value(first_item.value)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        await self.__callback(interaction, parsed)


class FloatButton(BaseTextInputButton[V]):
    def __init__(
        self,
        *,
        label: str,
        disabled: bool = False,

        modal_title: str,
        input_label: str,
        placeholder: str | None = None,

        default_value: str | None = None,
        required: bool = False,

        max_value: float | None = None,
        min_value: float | None = None,
        round_to: int = 2,
        
        callback: FloatCallbackType
    ):
        super().__init__(label=label, disabled=disabled)
        self.__modal_title = modal_title
        self.__input_label = input_label
        self.__placeholder = placeholder

        self.__default_value = default_value
        self.__required = required

        self.__max_value = max_value
        self.__min_value = min_value
        self.__round_to = round_to
        assert self.__round_to >= 0, "round_to must be a non-negative integer"

        self.__callback = callback

    @override
    def create_modal(self) -> ui.Modal:
        modal = ui.Modal(title=self.__modal_title, timeout=120)
        _ = modal.add_item(ui.TextInput(
            label=self.__input_label,
            placeholder=self.__placeholder,
            default=self.__default_value,
            min_length=None,
            max_length=64,
            required=self.__required,
        ))
        return modal

    @override
    async def on_submit(self, interaction: Interaction, modal: ui.Modal):
        assert len(modal.children) > 0, "Modal should have at least one TextInput"
        first_item = modal.children[0]
        assert isinstance(first_item, ui.TextInput), "Expected first item to be a TextInput"
        stripped_value = first_item.value.strip().replace(",", ".")
        
        try:
            value = float(stripped_value)
        except ValueError:
            await interaction.response.send_message(
                f"'{stripped_value}' is not a valid floating point number.",
                ephemeral=True
            )
            return
        
        # If both min and max values are set, check if the value is within the range
        if (
            self.__min_value is not None
            and self.__max_value is not None
            and not (self.__min_value <= value <= self.__max_value)
        ):
            await interaction.response.send_message(
                f"{value} is outside the required range of {self.__min_value} ≤ x ≤ {self.__max_value}.",
                ephemeral=True
            )
            return

        # If only one of min or max is set, check if the value is within that limit    
        if self.__min_value is not None and value < self.__min_value:
            await interaction.response.send_message(
                f"{value} is below the minimum value of {self.__min_value}.",
                ephemeral=True
            )
            return
    
        if self.__max_value is not None and value > self.__max_value:
            await interaction.response.send_message(
                f"{value} is above the maximum value of {self.__max_value}.",
                ephemeral=True
            )
            return

        # Round the value to the specified number of decimal places
        rounded = round(value, self.__round_to)

        await self.__callback(interaction, rounded)


class BooleanButton(ui.Button[V]):
    def __init__(
        self,
        *,
        label: str | None = None,
        disabled: bool = False,
        callback: BooleanCallbackType
    ):
        super().__init__(label=label, disabled=disabled)
        self.__callback = callback

    @override
    async def callback(self, interaction: Interaction):
        await self.__callback(interaction)

class RoleSelect(ui.RoleSelect[V]):
    def __init__(
        self,
        *,
        placeholder: str | None = None,
        min_values: int = 1,
        max_values: int = 1,
        disabled: bool = False,
        callback: RoleSelectCallbackType
    ) -> None:
        super().__init__(placeholder=placeholder, min_values=min_values, max_values=max_values, disabled=disabled)
        self.__callback = callback

    @override
    async def callback(self, interaction: Interaction):
        await self.__callback(interaction, [item.id for item in self.values])

class ChannelSelect(ui.ChannelSelect[V]):

    def __init__(
        self,
        *,
        channel_types: list[ChannelType] = MISSING,
        placeholder: str | None = None,
        min_values: int = 1,
        max_values: int = 1,
        disabled: bool = False,
        callback: ChannelSelectCallbackType
    ) -> None:
        super().__init__(channel_types=channel_types, placeholder=placeholder, min_values=min_values, max_values=max_values, disabled=disabled)
        self.__callback = callback

    @override
    async def callback(self, interaction: Interaction):
        await self.__callback(interaction, [item.id for item in self.values])

@dataclass
class StringOptionImpl(Generic[V, RV]):
    """
    This dataclass provides the necessary information to create a StringButton.
    """
    cls: type[StringButton[V, RV]] = StringButton
    label: str = "Change"
    modal_title: str = "Change Value"
    input_label: str = "Enter a new value"
    placeholder: str | None = None
    min_length: int | None = None
    max_length: int | None = None
    required: bool = True

@dataclass
class FloatOptionImpl(Generic[V]):
    """
    This dataclass provides the necessary information to create a FloatButton.
    """
    cls: type[FloatButton[V]] = FloatButton
    label: str = "Change"
    modal_title: str = "Change Value"
    input_label: str = "Enter a new value"
    placeholder: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    round_to: int = 2
    required: bool = True

@dataclass
class BooleanOptionImpl(Generic[V]):
    """
    This dataclass provides the necessary information to create a BooleanButton.
    """
    cls: type[BooleanButton[V]] = BooleanButton
    label_true: str = "True"
    label_false: str = "False"

@dataclass
class RoleOptionImpl(Generic[V]):
    """
    This dataclass provides the necessary information to create a RoleSelect.
    """
    cls: type[RoleSelect[V]] = RoleSelect
    placeholder: str | None = None

@dataclass
class ChannelOptionImpl(Generic[V]):
    """
    This dataclass provides the necessary information to create a ChannelSelect.
    """
    cls: type[ChannelSelect[V]] = ChannelSelect
    channel_types: list[ChannelType] = MISSING
    placeholder: str | None = None
