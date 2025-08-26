from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Coroutine
from dataclasses import dataclass
from discord import ChannelType, Interaction, ui
from discord.utils import MISSING
from typing import Any, Callable, Generic, TypeVar, override

V = TypeVar('V', bound='ui.view.BaseView', covariant=True)
RV = TypeVar('RV') # Return value

StringCallbackType = Callable[[Interaction, RV], Coroutine[Any, Any, None]]
FloatCallbackType = Callable[[Interaction, float], Coroutine[Any, Any, None]]
BooleanCallbackType = Callable[[Interaction, bool], Coroutine[Any, Any, None]]
RoleSelectCallbackType = Callable[[Interaction, list[int]], Coroutine[Any, Any, None]]
ChannelSelectCallbackType = Callable[[Interaction, list[int]], Coroutine[Any, Any, None]]


class UserInputModal:
    """
    This class is used to represent a modal that collects user input.
    It is designed to be subclassed for specific types of user input.
    """
    def __init__(
        self,
        *,
        title: str,
        timeout: int = 120
    ):
        self.modal: ui.Modal = ui.Modal(title=title, timeout=timeout)
        self.modal.on_submit = self.on_submit

    async def on_submit(self, interaction: Interaction) -> None:
        """This method gets called when the modal is submitted.
        It should be overridden by subclasses to handle the user input.
        """
        raise NotImplementedError

    async def send(self, interaction: Interaction):
        """
        This method is used to send the modal to the user.
        """
        await interaction.response.send_modal(self.modal)
        timed_out = await self.modal.wait()
        # TODO: handle modal timeout and parent view timeout
        # If it times out, notify the user, otherwise continue on to checking the user input
        #if timed_out:
        #    return
        #    return await interaction.response.send_message("Modal has timed out!", ephemeral=True)

        # Check if parent view is timed out or no longer responds
        #if self.view.is_finished():
        #    return
        #    return await interaction.response.send_message("Settings menu has timed out!", ephemeral=True)


class StringLikeInputModal(ABC, UserInputModal, Generic[RV]):

    def __init__(
        self,
        *,
        title: str,
        timeout: int = 120,

        input_label: str,
        placeholder: str | None = None,

        default_value: str | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        required: bool = False,
        
        callback: StringCallbackType[RV],
    ):
        super().__init__(title=title, timeout=timeout)
        self.modal.add_item(ui.TextInput(
            label=input_label,
            placeholder=placeholder,
            default=default_value,
            min_length=min_length,
            max_length=max_length,
            required=required,
        ))
        self.__min_length = min_length
        self.__max_length = max_length
        self.__callback = callback
    
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
    
    @abstractmethod
    async def handle_value(self, value: str) -> tuple[RV, str | None]:
        """
        This method must be overridden to handle the value before passing it to the callback.
        It should perform any necessary validation or processing on the input value.

        This method should return a tuple of the processed value and an error message if validation fails.
        If the value is valid, the error message will be None.
        """
        raise NotImplementedError

    @override
    async def on_submit(self, interaction: Interaction):
        assert len(self.modal.children) > 0, "Modal should have at least one TextInput"
        first_item = self.modal.children[0]
        assert isinstance(first_item, ui.TextInput), "Expected first item to be a TextInput"
        parsed, err = await self.handle_value(first_item.value)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        await self.__callback(interaction, parsed)

class StringInputModal(StringLikeInputModal[str]):

    def __init__(
        self,
        *,
        title: str,
        timeout: int = 120,

        input_label: str,
        placeholder: str | None = None,

        default_value: str | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        required: bool = False,
        
        callback: StringCallbackType[str],
    ):
        super().__init__(
            title=title, timeout=timeout, input_label=input_label,
            placeholder=placeholder, default_value=default_value,
            min_length=min_length, max_length=max_length, required=required,
            callback=callback
        )
    
    @override
    async def handle_value(self, value: str) -> tuple[str, str | None]:
        return self.parse_string_value(value)

class FloatInputModal(UserInputModal):

    def __init__(
        self,
        *,
        title: str,
        timeout: int = 120,

        input_label: str,
        placeholder: str | None = None,

        default_value: int | float | None = None,
        required: bool = False,

        min_value: float | None = None,
        max_value: float | None = None,
        round_to: int = 2,
        
        callback: FloatCallbackType
    ):
        super().__init__(title=title, timeout=timeout)
        value = str(default_value) if default_value is not None else None
        self.modal.add_item(ui.TextInput(
            label=input_label,
            placeholder=placeholder,
            default=value,
            min_length=None,
            max_length=64,
            required=required,
        ))
        self.__min_value = min_value
        self.__max_value = max_value
        self.__round_to = round_to
        assert self.__round_to >= 0, "round_to must be a non-negative integer"
        self.__callback = callback

    @override
    async def on_submit(self, interaction: Interaction):
        assert len(self.modal.children) > 0, "Modal should have at least one TextInput"
        first_item = self.modal.children[0]
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

@dataclass
class StringOptionImpl(Generic[V, RV]):
    """
    This dataclass provides the necessary information to create a StringButton.
    """
    modal: type[StringLikeInputModal[RV]] = StringLikeInputModal[RV]
    label: str = "Change"
    modal_title: str = "Change Value"
    input_label: str = "Enter a new value"
    placeholder: str | None = None
    min_length: int | None = None
    max_length: int | None = None
    required: bool = True

@dataclass
class FloatOptionImpl:
    """
    This dataclass provides the necessary information to create a FloatButton.
    """
    modal: type[FloatInputModal] = FloatInputModal
    label: str = "Change"
    modal_title: str = "Change Value"
    input_label: str = "Enter a new value"
    placeholder: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    round_to: int = 2
    required: bool = True

@dataclass
class BooleanOptionImpl:
    """
    This dataclass provides the necessary information to create a BooleanControl.
    """
    label_true: str = "True"
    label_false: str = "False"

@dataclass
class RoleOptionImpl:
    """
    This dataclass provides the necessary information to create a RoleControl.
    """
    placeholder: str | None = None

@dataclass
class ChannelOptionImpl:
    """
    This dataclass provides the necessary information to create a ChannelControl.
    """
    channel_types: list[ChannelType] = MISSING
    placeholder: str | None = None
