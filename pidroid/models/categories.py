from __future__ import annotations

from discord import PartialEmoji
from discord.ext.commands import Command
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pidroid.client import Pidroid

def get_full_command_name(command: Command) -> str:
    """Returns full command name including any command groups."""
    name = ''
    if len(command.parents) > 0:
        for parent in reversed(command.parents):
            name += f'{parent.name} '
    return name + command.name

def get_command_usage(prefix: str, command: Command) -> str:
    """Returns command usage."""
    usage = '`' + prefix + get_full_command_name(command) + '`'
    if command.usage is not None:
        usage += ' `' + command.usage + '`'
    return usage

def get_command_documentation(command: Command) -> tuple[str, str]:
    """Returns command documentation for display in lists."""
    usage = command.usage or ""
    name = get_full_command_name(command) + " " + usage
    value = command.brief or 'Not documented.'
    return name, value

class Category:
    def __init__(
        self,
        client: Pidroid,
        title: str,
        description: str,
        emote: PartialEmoji | str | None = None
    ):
        super().__init__()
        self.client = client
        self.title = title
        self.description = description
        self.emote = emote
        self.__cached_commands: list[Command] = []

    def get_visible_commands(self) -> list[Command]:
        """Returns a list of visible bot commands."""
        if self.__cached_commands:
            return self.__cached_commands

        # Create a command list, sort it and cache it
        cmd_list: list[Command] = []
        for command in self.client.walk_commands():
            if command.hidden:
                continue

            if get_full_command_name(command).startswith("jishaku"):
                continue

            orig_kwargs: dict = command.__original_kwargs__
            command_category = orig_kwargs.get("category", UncategorizedCategory)
            if not isinstance(self, command_category):
                continue
            cmd_list.append(command)
        self.__cached_commands = sorted(cmd_list, key=lambda c: get_full_command_name(c))
        return self.__cached_commands

class AdministrationCategory(Category):
    def __init__(self, client: Pidroid):
        super().__init__(client, "Administration", "Commands for server administration.", "🔐")

class BotCategory(Category):
    def __init__(self, client: Pidroid):
        super().__init__(client, "Bot", "Commands for interacting with the bot itself.", "🤖")

class InformationCategory(Category):
    def __init__(self, client: Pidroid):
        super().__init__(client, "Information", "Commands for retrieving all sorts of Discord related information.", "📙")

class ModerationCategory(Category):
    def __init__(self, client: Pidroid):
        super().__init__(client, "Moderation", "Tools for server moderation.", "🛠️")

class RandomCategory(Category):
    def __init__(self, client: Pidroid):
        super().__init__(client, "Random", "Random, fun and unexpected commands.", "🎲")

class TheoTownCategory(Category):
    def __init__(self, client: Pidroid):
        super().__init__(
            client,
            "TheoTown",
            "Commands for TheoTown specific information.",
            PartialEmoji.from_str("theotown:1137770633988689960")
        )

class OwnerCategory(Category):
    def __init__(self, client: Pidroid):
        super().__init__(client, "Owner", "Commands for my owner.", "⚙️")

class UtilityCategory(Category):
    def __init__(self, client: Pidroid):
        super().__init__(client, "Utility", "Various useful utilities and tools.", "🧰")

class TagCategory(Category):
    def __init__(self, client: Pidroid):
        super().__init__(client, "Tags", "Tagging related commands.", "🏷️")

class LevelCategory(Category):
    def __init__(self, client: Pidroid):
        super().__init__(client, "Level", "Leveling related commands.", "🌟")

class UncategorizedCategory(Category):
    def __init__(self, client: Pidroid):
        super().__init__(client, "Uncategorized", "Commands which do not fit in either of the above categories.", "🗑️")

def register_categories(client: Pidroid) -> list[Category]:
    """Returns a list of new command category objects."""
    return [
        AdministrationCategory(client),
        BotCategory(client),
        InformationCategory(client),
        ModerationCategory(client),
        RandomCategory(client),
        TheoTownCategory(client),
        OwnerCategory(client),
        UtilityCategory(client),
        TagCategory(client),
        LevelCategory(client),
        UncategorizedCategory(client)
    ]
