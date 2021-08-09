from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from client import Pidroid


class Category:
    def __init__(self, title, description, hidden=False):
        self.title = title
        self.description = description
        self.hidden = hidden


class AdministrationCategory(Category):
    def __init__(self):
        super().__init__(
            'Administration', 'Tools for server administrators.'
        )


class BotCategory(Category):
    def __init__(self):
        super().__init__(
            'Bot', 'Generic Discord bot commands and tools.'
        )

class InformationCategory(Category):
    def __init__(self):
        super().__init__(
            'Information', 'Commands for retrieving various discord related information.'
        )

class ModerationCategory(Category):
    def __init__(self):
        super().__init__(
            'Moderation', 'Tools for server moderators.'
        )


class RandomCategory(Category):
    def __init__(self):
        super().__init__(
            'Random', 'Random and unexpected commands.'
        )


class TheoTownCategory(Category):
    def __init__(self):
        super().__init__(
            'TheoTown', 'Commands for TheoTown specific information.'
        )


class OwnerCategory(Category):
    def __init__(self):
        super().__init__(
            'Owner', 'Bot owner specific commands.'
        )


class UtilityCategory(Category):
    def __init__(self):
        super().__init__(
            'Utility', 'Various useful utilities and tools.'
        )


class UncategorizedCategory(Category):
    def __init__(self):
        super().__init__(
            'Uncategorized', 'Commands which do not fit in either of the above categories.'
        )


def get_command_categories() -> list:
    """Returns a list of new command category objects."""
    return [
        AdministrationCategory(),
        BotCategory(),
        InformationCategory(),
        ModerationCategory(),
        RandomCategory(),
        TheoTownCategory(),
        OwnerCategory(),
        UtilityCategory(),
        UncategorizedCategory()
    ]


def setup(client: Pidroid) -> None:
    client.command_categories = get_command_categories()

def teardown(client: Pidroid) -> None:
    pass
