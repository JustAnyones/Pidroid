from __future__ import annotations

from typing import Optional

class Category:
    def __init__(self, title: str, description: str, emote: Optional[str] = None):
        self.title = title
        self.description = description
        self.emote = emote or ""

class AdministrationCategory(Category):
    def __init__(self):
        super().__init__("Administration", "Commands for server administration.", "🔐")

class BotCategory(Category):
    def __init__(self):
        super().__init__("Bot", "Commands for interacting with the bot itself.", "🤖")

class InformationCategory(Category):
    def __init__(self):
        super().__init__("Information", "Commands for retrieving all sorts of Discord related information.", "📙")

class ModerationCategory(Category):
    def __init__(self):
        super().__init__("Moderation", "Tools for server moderation.", "🛠️")

class RandomCategory(Category):
    def __init__(self):
        super().__init__("Random", "Random, fun and unexpected commands.", "🎲")

class TheoTownCategory(Category):
    def __init__(self):
        super().__init__("TheoTown", "Commands for TheoTown specific information.", "🏙️")

class OwnerCategory(Category):
    def __init__(self):
        super().__init__("Owner", "Commands for my owner.", "⚙️")

class UtilityCategory(Category):
    def __init__(self):
        super().__init__("Utility", "Various useful utilities and tools.", "🧰")

class TagCategory(Category):
    def __init__(self):
        super().__init__("Tags", "Tagging related commands.", "🏷️")

class UncategorizedCategory(Category):
    def __init__(self):
        super().__init__("Uncategorized", "Commands which do not fit in either of the above categories.", "🗑️")

def get_command_categories() -> list[Category]:
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
        TagCategory(),
        UncategorizedCategory()
    ]
