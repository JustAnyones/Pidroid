from __future__ import annotations

from discord.embeds import Embed
from discord.utils import escape_markdown
from typing import TYPE_CHECKING

from cogs.utils.embeds import create_embed
from cogs.utils.parsers import clean_inline_translations, format_version_code, truncate_string

if TYPE_CHECKING:
    from client import Pidroid

URL_TO_USER = 'https://forum.theotown.com/memberlist.php?mode=viewprofile&u='


class TheoTownUser:
    """This class represents a TheoTown user."""

    def __init__(self, user_id: int, username: str):
        self.id = user_id
        self.username = username

    @property
    def url(self) -> str:
        """Returns a URL to the user profile on forums."""
        return f'{URL_TO_USER}{self.id}'


class Plugin:
    """This class represents a TheoTown plugin."""

    def __init__(self, data: dict):
        self._deserialize(data)

    @property
    def clean_title(self) -> str:
        """Returns plugin title with all of the inline translations removed."""
        return clean_inline_translations(self.title)

    @property
    def clean_description(self) -> str:
        """Returns plugin description with all of the inline translations removed."""
        return clean_inline_translations(self.description)

    @property
    def preview(self) -> str:
        """Returns a plugin preview image URL."""
        return f"https://store.theotown.com/get_file?name={self._preview_file}"

    @property
    def url(self) -> str:
        """Returns a plugin URL for the plugin store."""
        return f"https://forum.theotown.com/plugins/list?term=%3A{self.id}"

    def _deserialize(self, p: dict) -> Plugin:
        """Deserializes a plugin dictionary to a Plugin object."""
        self.id = p['plugin_id']
        self.title = p['name']
        self.description = p['description']
        self.author = TheoTownUser(p['author_id'], p['username'])
        self.price = p['price']
        self.version = p['version']
        self.revision_id = p['revision_id']
        self._preview_file = p['preview_file']
        self.min_version = p['min_version']
        return self

    def to_embed(self) -> Embed:
        """Returns a discord Embed object."""
        name = truncate_string(self.clean_title)
        description = truncate_string(self.clean_description, 1024)
        author = f'[{escape_markdown(self.author.username)}]({self.author.url})'
        price = f'{self.price:,} <:diamond:423898110293704724>'
        footer = f'#{self.id}:{self.version} [{self.revision_id}]'

        embed = create_embed(title=name, url=self.url)
        embed.add_field(name='**Description**', value=description, inline=False)
        embed.add_field(name='**Price**', value=price, inline=False)
        embed.add_field(name='**Author**', value=author, inline=False)
        if self.min_version is not None and self.min_version != 0:
            min_version = format_version_code(self.min_version)
            embed.add_field(name='**Minimal version required**', value=min_version, inline=False)
        embed.set_footer(text=footer)
        embed.set_image(url=self.preview)
        return embed

class NewPlugin(Plugin):
    """This class represents a new TheoTown plugin. This class differs from Plugin class since it additionally contains time property."""

    if TYPE_CHECKING:
        approval_author_id: int

    def __init__(self, data: dict):
        super().__init__(data)
        self._time = data["time"]
        self.approval_author_id = data["approval_author"]

    @property
    def time(self) -> int:
        """Returns plugin approval time."""
        return self._time


def setup(client: Pidroid) -> None:
    pass

def teardown(client: Pidroid) -> None:
    pass
