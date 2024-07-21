from __future__ import annotations

import discord

from collections.abc import Coroutine, Sequence
from discord import  ButtonStyle, ChannelType, Emoji, Interaction, PartialEmoji
from discord.utils import MISSING
from typing import TYPE_CHECKING, Any, Callable, Self, override

from pidroid.models.guild_configuration import GuildConfiguration
from pidroid.utils.embeds import PidroidEmbed

if TYPE_CHECKING:
    from pidroid.commands.setting import GuildConfigurationView

class Setting:

    def __init__(self, *, name: str, description: str | None = None, value: Any) -> None:
        self.__name = name
        self.__description = description
        self._value = value

    @property
    def name(self) -> str:
        """"Returns the name of the setting."""
        return self.__name

    @property
    def description(self) -> str | None:
        """"Returns the setting description."""
        return self.__description

    @property
    def value_as_str(self) -> str:
        """Returns the setting value as a string."""
        raise NotImplementedError
    
    def as_item(self) -> discord.ui.Item:
        """Returns the setting as item that can be interacted with."""
        raise NotImplementedError

class ReadonlySetting(Setting):

    if TYPE_CHECKING:
        _value: str | None

    def __init__(
        self,
        *,
        name: str,
        description: str | None = None,
        value: str | None
    ) -> None:
        super().__init__(name=name, description=description, value=value)

    @property
    @override
    def value_as_str(self) -> str:
        if self._value is None:
            return "Not set"
        return self._value

    @override
    def as_item(self):
        return None

class TextSetting(Setting):

    if TYPE_CHECKING:
        _value: str | None

    def __init__(
        self,
        *,
        cls: type[TextButton],
        name: str,
        description: str | None = None,
        value: str | None,
        label: str,
        callback: Callable[[Any], Coroutine[Any, Any, None]],
        disabled: bool = False
    ) -> None:
        super().__init__(name=name, description=description, value=value)
        self.__cls = cls
        self.__label = label
        self.__callback = callback
        self.__disabled = disabled

    @property
    @override
    def value_as_str(self) -> str:
        if self._value is None:
            return "Not set"
        return self._value

    @override
    def as_item(self):
        return self.__cls(label=self.__label, disabled=self.__disabled, callback=self.__callback)

class NumberSetting(Setting):

    if TYPE_CHECKING:
        _value: float | int | str

    def __init__(
        self,
        *,
        cls: type[TextButton],
        name: str,
        description: str | None = None,
        value: float | int | str,
        label: str,
        callback: Callable[[Any], Coroutine[Any, Any, None]],
        disabled: bool = False
    ) -> None:
        super().__init__(name=name, description=description, value=value)
        self.__cls = cls
        self.__label = label
        self.__callback = callback
        self.__disabled = disabled

    @property
    @override
    def value_as_str(self) -> str:
        if isinstance(self._value, str):
            return self._value
        return str(self._value)
    
    @override
    def as_item(self):
        return self.__cls(label=self.__label, disabled=self.__disabled, callback=self.__callback)

class BooleanSetting(Setting):

    if TYPE_CHECKING:
        _value: bool
    
    def __init__(
        self,
        *,
        name: str,
        description: str | None = None,
        value: bool,
        label_true: str,
        label_false: str,
        callback: Callable[[], Coroutine[Any, Any, None]],
        disabled: bool = False
    ) -> None:
        super().__init__(name=name, description=description, value=value)
        self.__label_true = label_true
        self.__label_false = label_false
        self.__callback = callback
        self.__disabled = disabled

    @property
    @override
    def value_as_str(self) -> str:
        return "Yes" if self._value else "No"
    
    @override
    def as_item(self):
        label = self.__label_false if self._value else self.__label_true # Inversed, because that's what the button will do
        return BooleanButton(label=label, disabled=self.__disabled, callback=self.__callback)

class RoleSetting(Setting):
    
    if TYPE_CHECKING:
        _value: int | None

    def __init__(
        self,
        *,
        name: str,
        description: str | None = None,
        value: int | None,
        configuration: GuildConfiguration,
        placeholder: str,
        callback: Callable[[int | None], Coroutine[Any, Any, None]],
        disabled: bool = False
    ) -> None:
        super().__init__(name=name, description=description, value=value)
        self.__configuration = configuration
        self.__placeholder = placeholder
        self.__callback = callback
        self.__disabled = disabled

    @property
    @override
    def value_as_str(self) -> str:
        assert self.__configuration.guild
        if self._value is None:
            return "Not set"
        
        role = self.__configuration.guild.get_role(self._value)
        if role:
            return role.mention
        return f"{self._value} (deleted?)"
    
    @override
    def as_item(self):
        return RoleSelect(
            placeholder=self.__placeholder,
            disabled=self.__disabled,
            callback=self.__callback
        )

class ChannelSetting(Setting):
    
    if TYPE_CHECKING:
        _value: int | None

    def __init__(
        self,
        *,
        name: str,
        description: str | None = None,
        value: int | None,
        configuration: GuildConfiguration,
        channel_types: list[discord.ChannelType],
        placeholder: str,
        callback: Callable[[int | None], Coroutine[Any, Any, None]],
        disabled: bool = False
    ) -> None:
        super().__init__(name=name, description=description, value=value)
        self.__configuration = configuration
        self.__channel_types = channel_types
        self.__placeholder = placeholder
        self.__callback = callback
        self.__disabled = disabled

    @property
    @override
    def value_as_str(self) -> str:
        assert self.__configuration.guild
        if self._value is None:
            return "Not set"

        chan = self.__configuration.guild.get_channel(self._value)
        if chan:
            return chan.mention
        return f"{self._value} (deleted?)"

    @override
    def as_item(self):
        return ChannelSelect(
            channel_types=self.__channel_types,
            placeholder=self.__placeholder,
            disabled=self.__disabled,
            callback=self.__callback
        )

class Submenu:

    def __init__(self, *, name: str, description: str, settings: Sequence[Setting]) -> None:
        self.__name = name
        self.__description = description
        self.__settings = settings

    @property
    def embed(self) -> PidroidEmbed:
        embed = PidroidEmbed(title=self.__name, description=self.__description)
        assert embed.description
        for setting in self.__settings:
            if setting.description:
                embed.description += f"\n- {setting.name}: {setting.description}"
            embed.add_field(name=setting.name, value=setting.value_as_str)
        embed.set_footer(text="Any change that you make here will be applied instantly.")
        return embed
    
    @property
    def items(self) -> list[discord.ui.Item]:
        items = []
        for setting in self.__settings:
            item = setting.as_item()
            if item:
                items.append(item)
        return items



class TextModal(discord.ui.Modal):

    if TYPE_CHECKING:
        # Since this is strictly a TextInput modal, we
        # add some glue to add type hinting when handling
        # chilren values
        children: list[discord.ui.TextInput[Self]]

    async def on_submit(self, interaction: Interaction):
        self.interaction = interaction
        self.stop()

class TextButton(discord.ui.Button):
    
    if TYPE_CHECKING:
        label: str
        view: GuildConfigurationView

    def __init__(
        self,
        *,
        style: ButtonStyle = ButtonStyle.secondary,
        label: str | None = None,
        disabled: bool = False,
        emoji: str | Emoji | PartialEmoji | None = None,
        callback
    ):
        super().__init__(style=style, label=label, disabled=disabled, emoji=emoji)
        self._callback = callback

    def create_modal(self) -> TextModal:
        """Creates a custom modal for current TextButton."""
        raise NotImplementedError

    async def handle_input(self, modal: TextModal):
        raise NotImplementedError

    @override
    async def callback(self, interaction: Interaction):
        # Construct a custom TextModal for our current button
        modal = self.create_modal()

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
        
        # Deal with user input as appropriate
        await self.handle_input(modal)

class BooleanButton(discord.ui.Button):
    
    if TYPE_CHECKING:
        view: GuildConfigurationView

    def __init__(
        self,
        *,
        style: ButtonStyle = ButtonStyle.secondary,
        label: str | None = None,
        disabled: bool = False,
        emoji: str | Emoji | PartialEmoji | None = None,
        callback: Callable[[], Coroutine[Any, Any, None]]
    ):
        super().__init__(style=style, label=label, disabled=disabled, emoji=emoji)
        self.__callback = callback

    @override
    async def callback(self, interaction: Interaction):
        await self.__callback()
        _ = await self.view.refresh_menu(interaction)

class RoleSelect(discord.ui.RoleSelect):

    if TYPE_CHECKING:
        view: GuildConfigurationView

    def __init__(
        self,
        *,
        placeholder: str | None = None,
        min_values: int = 1,
        max_values: int = 1,
        disabled: bool = False,
        callback: Callable[[int | None], Coroutine[Any, Any, None]]
    ) -> None:
        super().__init__(placeholder=placeholder, min_values=min_values, max_values=max_values, disabled=disabled)
        self.__callback = callback

    @override
    async def callback(self, interaction: Interaction):
        selected = self.values[0]
        await self.__callback(selected.id)
        _ = await self.view.refresh_menu(interaction)

class ChannelSelect(discord.ui.ChannelSelect):

    if TYPE_CHECKING:
        view: GuildConfigurationView

    def __init__(
        self,
        *,
        channel_types: list[ChannelType] = MISSING,
        placeholder: str | None = None,
        min_values: int = 1,
        max_values: int = 1,
        disabled: bool = False,
        callback: Callable[[int | None], Coroutine[Any, Any, None]]
    ) -> None:
        super().__init__(channel_types=channel_types, placeholder=placeholder, min_values=min_values, max_values=max_values, disabled=disabled)
        self.__callback = callback

    @override
    async def callback(self, interaction: Interaction):
        selected = self.values[0]
        await self.__callback(selected.id)
        _ = await self.view.refresh_menu(interaction)