from discord import Guild, ui
from typing import Generic, TypeVar, override

from pidroid.modules.core.ui.opt.impl import (
    BooleanOptionImpl, BooleanCallbackType,
    ChannelSelectCallbackType, ChannelOptionImpl,
    FloatCallbackType, FloatOptionImpl,
    RoleOptionImpl, RoleSelectCallbackType,
    StringCallbackType, StringOptionImpl
)

V = TypeVar('V', bound='ui.view.BaseView', covariant=True)
RV = TypeVar('RV')

class Control(Generic[V]):
    """
    Base class for all options provided to Pidroid UI components.
    """

    def __init__(self, *, name: str, description: str | None = None) -> None:
        self.__name = name
        self.__description = description

    @property
    def name(self) -> str:
        """"Returns the name of the option."""
        return self.__name

    @property
    def description(self) -> str | None:
        """"Returns the option description."""
        return self.__description

    @property
    def value_as_str(self) -> str:
        """Returns the current option value as a string."""
        raise NotImplementedError
    
    def as_item(self) -> ui.Item[V]:
        """Returns the option as an item that can be interacted with."""
        raise NotImplementedError

class ReadonlyControl(Control[V]):
    """
    This class represents a readonly option.
    """

    def __init__(self, *, name: str, description: str | None = None, value: str | None) -> None:
        super().__init__(name=name, description=description)
        self.__value = value

    @property
    @override
    def value_as_str(self) -> str:
        if self.__value is None:
            return "Not set"
        return self.__value

class StringControl(Control[V], Generic[V, RV]):

    """
    This class represents a string option.
    """

    def __init__(
        self,
        *,
        name: str,
        description: str | None = None,
        value: str,
        impl: StringOptionImpl[V, RV] | None = None,
        callback: StringCallbackType[RV],
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, description=description)
        self.__value = value
        if impl is None:
            impl = StringOptionImpl[V, RV]()
        self.__impl = impl
        self.__callback = callback
        self.__disabled = disabled

    @property
    @override
    def value_as_str(self) -> str:
        return str(self.__value)
    
    @override
    def as_item(self) -> ui.Item[V]:
        return self.__impl.cls(
            label=self.__impl.label,
            modal_title=self.__impl.modal_title,
            input_label=self.__impl.input_label,
            placeholder=self.__impl.placeholder,
            min_length=self.__impl.min_length,
            max_length=self.__impl.max_length,
            required=self.__impl.required,
            disabled=self.__disabled,
            callback=self.__callback
        )

class FloatControl(Control[V]):

    """
    This class represents a float option.
    """

    def __init__(
        self,
        *,
        name: str,
        description: str | None = None,
        value: int | float,
        impl: FloatOptionImpl[V] | None = None,
        callback: FloatCallbackType,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, description=description)
        self.__value = value
        if impl is None:
            impl = FloatOptionImpl[V]()
        self.__impl = impl
        self.__callback = callback
        self.__disabled = disabled

    @property
    @override
    def value_as_str(self) -> str:
        return str(self.__value)
    
    @override
    def as_item(self) -> ui.Item[V]:
        return self.__impl.cls(
            label=self.__impl.label,
            modal_title=self.__impl.modal_title,
            input_label=self.__impl.input_label,
            placeholder=self.__impl.placeholder,
            min_value=self.__impl.min_value,
            max_value=self.__impl.max_value,
            required=self.__impl.required,
            disabled=self.__disabled,
            callback=self.__callback
        )

class BooleanControl(Control[V]):

    """
    This class represents a boolean option.
    """
    
    def __init__(
        self,
        *,
        name: str,
        description: str | None = None,
        value: bool,
        impl: BooleanOptionImpl[V] | None = None,
        callback: BooleanCallbackType,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, description=description)
        self.__value = value
        if impl is None:
            impl = BooleanOptionImpl[V]()
        self.__impl = impl
        self.__callback = callback
        self.__disabled = disabled

    @property
    @override
    def value_as_str(self) -> str:
        return "Yes" if self.__value else "No"
    
    @override
    def as_item(self) -> ui.Item[V]:
        # Inversed, because that's what the button will do
        label = self.__impl.label_false if self.__value else self.__impl.label_true
        return self.__impl.cls(
            label=label,
            disabled=self.__disabled,
            callback=self.__callback
        )

class RoleControl(Control[V]):
    """
    This class represents a role option.
    """

    def __init__(
        self,
        *,
        name: str,
        description: str | None = None,
        value: int | None,
        guild: Guild,
        impl: RoleOptionImpl[V] | None = None,
        callback: RoleSelectCallbackType,
        disabled: bool = False
    ) -> None:
        super().__init__(name=name, description=description)
        self.__value = value
        self.__guild = guild
        if impl is None:
            impl = RoleOptionImpl[V]()
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
        return self.__impl.cls(
            placeholder=self.__impl.placeholder,
            disabled=self.__disabled,
            callback=self.__callback
        )

class ChannelControl(Control[V]):
    """
    This class represents a channel option.
    """

    def __init__(
        self,
        *,
        name: str,
        description: str | None = None,
        value: int | None,
        guild: Guild,
        impl: ChannelOptionImpl[V] | None = None,
        callback: ChannelSelectCallbackType,
        disabled: bool = False
    ) -> None:
        super().__init__(name=name, description=description)
        self.__value = value
        self.__guild = guild
        if impl is None:
            impl = ChannelOptionImpl[V]()
        self.__impl = impl
        self.__callback = callback
        self.__disabled = disabled

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
        return self.__impl.cls(
            channel_types=self.__impl.channel_types,
            placeholder=self.__impl.placeholder,
            disabled=self.__disabled,
            callback=self.__callback
        )
