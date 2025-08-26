from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from discord import ButtonStyle, Guild, Interaction, ui
from typing import Any, Generic, TypeVar, override

from pidroid.modules.core.ui.opt.impl import (
    BooleanOptionImpl, BooleanCallbackType,
    ChannelSelectCallbackType, ChannelOptionImpl,
    FloatCallbackType, FloatOptionImpl,
    RoleOptionImpl, RoleSelectCallbackType,
    StringCallbackType, StringOptionImpl
)

V = TypeVar('V', ui.LayoutView, ui.view.BaseView, covariant=True)
RV = TypeVar('RV')

OnSendCustomButtonsType = Callable[[Interaction, list[ui.Item[V]]], Coroutine[Any, Any, None]]

class SupportsItems(ABC, Generic[V]):
    """
    This class is used to mark controls that support items.
    Controls that do not support items should not inherit from this class.
    """

    @abstractmethod
    def as_item(self) -> ui.Item[V]:
        """Returns the control as an item that can be interacted with."""
        raise NotImplementedError
    
    @abstractmethod
    def as_legacy_item(self) -> ui.Item[V]:
        """
        Returns the control as an interactive item that can be used in traditional
        Embed-based Views.

        May return None if the control does not support being edited.
        """
        raise NotImplementedError

class Control(ABC, Generic[V]):
    """
    Base class for all controls provided to Pidroid UI components.

    Passing None as callback will not provide any interaction with the option.
    """

    def __init__(
        self,
        *,
        # The name of the control
        name: str,
        # Emoji to display next to the control name
        emoji: str | None,
        # The description of the control
        description: str | None,

        # The method that will be called when the value is updated
        update_callback: Callable[[Interaction, RV], Coroutine[Any, Any, None]] | None = None,

        disabled: bool = False
    ) -> None:
        self.__name = name
        self.__emoji = emoji
        self.__description = description
        self.__update_callback = update_callback
        self.__disabled = disabled
        self.__options = []

    @property
    def name(self) -> str:
        """"Returns the name of the control."""
        return self.__name

    @property
    def display_name(self) -> str:
        """"Returns the display name of the control."""
        if self.__emoji:
            return f"{self.__emoji} {self.__name}"
        return self.__name

    @property
    def disabled(self) -> bool:
        """Returns whether the control is disabled."""
        return self.__disabled

    @property
    def description(self) -> str | None:
        """"Returns the control description."""
        return self.__description

    @property
    def value_as_str(self) -> str:
        """Returns the current control value as a string."""
        raise NotImplementedError
    
    @property
    def options(self) -> list:
        return self.__options

    def as_accessory(self) -> ui.Item[ui.LayoutView]:
        """Returns the control as an accessory item to be used in a container that belongs to a layout view."""
        return ui.Button(
            label="Edit",
            disabled=self.__disabled,
        )
    
    def as_layout_section(self) -> ui.Item[ui.LayoutView]:
        """Returns the control as a section that can be used in a container that belongs to a layout view."""
        current_value =f"### {self.display_name}\n{self.value_as_str}"
        if self.description:
            current_value += f"\n-# {self.description}"
        text_display = ui.TextDisplay[ui.LayoutView](current_value)
        if self.__update_callback is None:
            return text_display
        return ui.Section[ui.LayoutView](accessory=self.as_accessory()).add_item(text_display)

class ReadonlyControl(Control[V]):
    """
    This class represents a readonly control.
    """

    def __init__(self, *, name: str, emoji: str | None = None, description: str | None = None, value: str | None) -> None:
        super().__init__(name=name, emoji=emoji, description=description)
        self.__value = value

    @property
    @override
    def value_as_str(self) -> str:
        return self.__value if self.__value is not None else "Not set"

class SupportsOptions(Control[V], SupportsItems[V], ABC):
    send_custom_buttons: OnSendCustomButtonsType[V] | None

    @override
    def as_accessory(self) -> ui.Item[ui.LayoutView]:
        async def callback(interaction: Interaction) -> None:
            # If it supports options, return the options
            if self.options:
                await interaction.response.send_message(
                    "Control types with options are not supported yet.",
                    ephemeral=True
                )
                return
            
            # If it supports a modal, invoke it
            if isinstance(self, SupportsUserInput):
                await self.request_user_input(interaction)
                return
            
            # Otherwise, send item as a custom button back to view
            if self.send_custom_buttons is None:
                raise NotImplementedError(
                    f"Control {self.__class__.__name__} does not support modals or options."
                )
            await self.send_custom_buttons(interaction, [self.as_item()])

        button = ui.Button[ui.LayoutView](
            label="Edit",
            disabled=self.disabled,
        )
        button.callback = callback
        return button

class SupportsUserInput(SupportsOptions[V], ABC):
    """
    This class is used to mark controls that support modals.
    Controls that do not support modals should not inherit from this class.
    """

    @abstractmethod
    async def request_user_input(self, interaction: Interaction) -> None:
        """
        Requests user input for the control.
        This should open a modal or similar interface to collect input from the user.
        """
        raise NotImplementedError("Subclasses must implement request_user_input method.")

    @override
    def as_item(self) -> ui.Item[V]:
        button = ui.Button[V](
            label=f"Edit {self.name}...",
            style=ButtonStyle.primary,
            disabled=False
        )
        async def callback(interaction: Interaction) -> None:
            await self.request_user_input(interaction)
        button.callback = callback
        return button

class StringControl(SupportsUserInput[V], Generic[V, RV]):

    """
    This class represents a string option.
    """

    def __init__(
        self,
        *,
        name: str,
        emoji: str | None = None,
        description: str | None = None,
        value: str | None,
        impl: StringOptionImpl[V, RV] | None = None,
        callback: StringCallbackType[RV],
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, emoji=emoji, description=description, update_callback=callback, disabled=disabled)
        self.__value = value
        if impl is None:
            impl = StringOptionImpl[V, RV]()
        self.__impl = impl
        self.__callback = callback
        self.__disabled = disabled

    @property
    @override
    def value_as_str(self) -> str:
        return str(self.__value) if self.__value is not None else "Not set"
    
    @override
    async def request_user_input(self, interaction: Interaction) -> None:
        modal = self.__impl.modal(
            title=self.__impl.modal_title,
            input_label=self.__impl.input_label,
            placeholder=self.__impl.placeholder,
            min_length=self.__impl.min_length,
            max_length=self.__impl.max_length,
            required=self.__impl.required,
            default_value=self.__value,
            callback=self.__callback
        ) 
        await modal.send(interaction=interaction)

    @override
    def as_legacy_item(self) -> ui.Item[V]:
        button = ui.Button[V](
            label=self.__impl.label,
            disabled=self.__disabled
        )
        async def callback(interaction: Interaction) -> None:
            await self.request_user_input(interaction)
        button.callback = callback
        return button

class FloatControl(SupportsUserInput[V]):

    """
    This class represents a float option.
    """

    def __init__(
        self,
        *,
        name: str,
        emoji: str | None = None,
        description: str | None = None,
        value: int | float,
        impl: FloatOptionImpl | None = None,
        callback: FloatCallbackType,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, emoji=emoji, description=description, update_callback=callback, disabled=disabled)
        self.__value = value
        if impl is None:
            impl = FloatOptionImpl()
        self.__impl = impl
        self.__callback = callback
        self.__disabled = disabled

    @property
    @override
    def value_as_str(self) -> str:
        return str(self.__value)
    
    @override
    async def request_user_input(self, interaction: Interaction) -> None:
        modal = self.__impl.modal(
            title=self.__impl.modal_title,
            input_label=self.__impl.input_label,
            placeholder=self.__impl.placeholder,
            min_value=self.__impl.min_value,
            max_value=self.__impl.max_value,
            round_to=self.__impl.round_to,
            required=self.__impl.required,
            default_value=self.__value,
            callback=self.__callback
        ) 
        await modal.send(interaction=interaction)

    @override
    def as_legacy_item(self) -> ui.Item[V]:
        button = ui.Button[V](
            label=self.__impl.label,
            disabled=self.__disabled
        )
        async def callback(interaction: Interaction) -> None:
            await self.request_user_input(interaction)
        button.callback = callback
        return button

class BooleanControl(Control[V], SupportsItems[V]):

    """
    This class represents a boolean option.
    """
    
    def __init__(
        self,
        *,
        name: str,
        emoji: str | None = None,
        description: str | None = None,
        value: bool,
        impl: BooleanOptionImpl | None = None,
        callback: BooleanCallbackType,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, emoji=emoji, description=description, update_callback=callback, disabled=disabled)
        self.__value = value
        if impl is None:
            impl = BooleanOptionImpl()
        self.__impl = impl
        self.__callback = callback
        self.__disabled = disabled

    @property
    @override
    def value_as_str(self) -> str:
        return "Yes" if self.__value else "No"
    
    @override
    def as_accessory(self) -> ui.Item[ui.LayoutView]:
        async def callback(interaction: Interaction) -> None:
            await self.__callback(interaction, not self.__value)
        button = ui.Button[ui.LayoutView](
            label="Toggle",
            disabled=self.__disabled
        )
        button.callback = callback
        return button

    @override
    def as_item(self) -> ui.Item[V]:
        button = ui.Button[V](
            label=self.__impl.label_true if self.__value else self.__impl.label_false,
            disabled=self.__disabled
        )
        async def callback(interaction: Interaction) -> None:
            await self.__callback(interaction, not self.__value)
        button.callback = callback
        return button

    @override
    def as_legacy_item(self) -> ui.Item[V]:
        # The new Button is compatible with legacy views
        return self.as_item()

class RoleControl(SupportsOptions[V]):
    """
    This class represents a role option.
    """

    def __init__(
        self,
        *,
        name: str,
        emoji: str | None = None,
        description: str | None = None,
        value: int | None,
        guild: Guild,
        impl: RoleOptionImpl | None = None,
        callback: RoleSelectCallbackType,
        disabled: bool = False
    ) -> None:
        super().__init__(name=name, emoji=emoji, description=description, update_callback=callback, disabled=disabled)
        self.__value = value
        self.__guild = guild
        if impl is None:
            impl = RoleOptionImpl()
        self.__impl = impl
        self.__callback = callback
        self.__disabled = disabled

    @property
    @override
    def value_as_str(self) -> str:
        if self.__value is None:
            return "Not set"
        role = self.__guild.get_role(self.__value)
        if role:
            return role.mention
        return f"{self.__value} (deleted?)"

    @override
    def as_item(self) -> ui.Item[V]:
        select = ui.RoleSelect[V](
            placeholder=self.__impl.placeholder,
            min_values=1,
            max_values=1,
            #disabled=self.__disabled,
        )
        async def callback(interaction: Interaction) -> None:
            await self.__callback(interaction, [item.id for item in select.values])
        select.callback = callback
        return select

    @override
    def as_legacy_item(self) -> ui.Item[V]:
        # The new RoleSelect is compatible with legacy views
        return self.as_item()

class ChannelControl(SupportsOptions[V]):
    """
    This class represents a channel option.
    """

    def __init__(
        self,
        *,
        name: str,
        emoji: str | None = None,
        description: str | None = None,
        value: int | None,
        guild: Guild,
        impl: ChannelOptionImpl | None = None,
        callback: ChannelSelectCallbackType,
        disabled: bool = False,

        on_send_custom_buttons: OnSendCustomButtonsType[V] | None = None
    ) -> None:
        super().__init__(name=name, emoji=emoji, description=description, update_callback=callback, disabled=disabled)
        self.__value = value
        self.__guild = guild
        if impl is None:
            impl = ChannelOptionImpl()
        self.__impl = impl
        self.__callback = callback
        self.__disabled = disabled

        self.send_custom_buttons: OnSendCustomButtonsType[V] | None = on_send_custom_buttons

    @property
    @override
    def value_as_str(self) -> str:
        if self.__value is None:
            return "Not set"
        chan = self.__guild.get_channel(self.__value)
        if chan:
            return chan.mention
        return f"{self.__value} (deleted?)"

    @override
    def as_item(self) -> ui.Item[V]:
        select = ui.ChannelSelect[V](
            channel_types=self.__impl.channel_types,
            placeholder=self.__impl.placeholder,
            min_values=1,
            max_values=1,
            #disabled=self.__disabled,
        )
        async def callback(interaction: Interaction) -> None:
            await self.__callback(interaction, [item.id for item in select.values])
        select.callback = callback
        return select

    @override
    def as_legacy_item(self) -> ui.Item[V]:
        # The new ChannelSelect is compatible with legacy views
        return self.as_item()
