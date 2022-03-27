from __future__ import annotations

from discord.embeds import Embed
from discord.utils import escape_markdown
from typing import TYPE_CHECKING, Optional

from cogs.utils.embeds import PidroidEmbed
from cogs.utils.parsers import clean_inline_translations, format_version_code, truncate_string

URL_TO_USER = 'https://forum.theotown.com/memberlist.php?mode=viewprofile&u='


class Platforms:
    ANDROID = 1 << 0
    IOS     = 1 << 1 # noqa
    DESKTOP = 1 << 2


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
        self._download_url = None
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

    @property
    def download_url(self) -> Optional[str]:
        """Returns plugin download url.

        Note that this property is only available if plugin has been acquired
        by fetching it with an ID."""
        return self._download_url

    @property
    def is_ubiquitous(self) -> bool:
        """Returns true if plugin is available on every platform."""
        return self._platforms == 7

    @property
    def is_on_android(self) -> bool:
        """Returns true if plugin is available on Android."""
        return self._platforms & Platforms.ANDROID != 0

    @property
    def is_on_ios(self) -> bool:
        """Returns true if plugin is available on iOS."""
        return self._platforms & Platforms.IOS != 0

    @property
    def is_on_desktop(self) -> bool:
        """Returns true if plugin is available on desktop."""
        return self._platforms & Platforms.DESKTOP != 0

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
        self._platforms = p['platforms']
        # Only available when fetched with API.fetch_plugin_by_id
        if "download_url" in p:
            self._download_url = p["download_url"]
        return self

    def to_embed(self) -> Embed:
        """Returns a discord Embed object."""
        name = truncate_string(self.clean_title)
        description = truncate_string(self.clean_description, 1024)
        author = f'[{escape_markdown(self.author.username)}]({self.author.url})'
        if self.price == 0:
            price = "🎁 Free"
        else:
            price = f'{self.price:,} <:diamond:423898110293704724>'
        footer = f'#{self.id}:{self.version} [{self.revision_id}]'

        embed = PidroidEmbed(title=name, url=self.url)
        embed.add_field(name='**Description**', value=description, inline=False)
        embed.add_field(name='**Price**', value=price, inline=False)
        embed.add_field(name='**Author**', value=author, inline=False)

        availability = "???"
        if self.is_ubiquitous:
            availability = "All platforms"
        else:
            platforms = [self.is_on_android, self.is_on_ios, self.is_on_desktop]
            names = ["Android", "iOS", "Desktop"]
            availability = ', '.join(
                [names[i] for i, p in enumerate(platforms) if p]
            )
        embed.add_field(name="**Availability**", value=availability)

        if self.min_version is not None and self.min_version != 0:
            if self.min_version > 400:
                min_version = format_version_code(self.min_version)
                embed.add_field(name='**Minimal version required**', value=min_version)
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
