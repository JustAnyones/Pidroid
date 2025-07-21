from __future__ import annotations

import enum

from discord.embeds import Embed
from discord.utils import escape_markdown
from typing import Any

from pidroid.utils import clean_inline_translations, format_version_code, truncate_string
from pidroid.utils.embeds import PidroidEmbed

URL_TO_USER = 'https://forum.theotown.com/memberlist.php?mode=viewprofile&u='


class Platforms(enum.Enum):
    ANDROID = 1 << 0
    IOS     = 1 << 1 # noqa
    DESKTOP = 1 << 2


class TheoTownUser:
    """This class represents a TheoTown user."""

    def __init__(self, user_id: int, username: str | None):
        self.id = user_id
        if username is None:
            self.username = 'Former Member'
        else:
            self.username = username

    @property
    def url(self) -> str:
        """Returns a URL to the user profile on forums."""
        return f'{URL_TO_USER}{self.id}'


class Plugin:
    """This class represents a TheoTown plugin."""

    def __init__(self, data: dict[str, Any]):
        self.id: int = data['plugin_id']
        self.title: str = data['name']
        self.description: str = data['description']
        self.author = TheoTownUser(data['author_id'], data['username'])
        self.price: int = data['price']
        self.version: int = data['version']
        self.revision_id: int = data['revision_id']
        self._preview_file: str = data['preview_file']
        self.min_version: int = data['min_version']
        self._platforms: int = data['platforms']
        self._demonetized: bool = data['demonetized'] == 1
        self.__download_count: int | None = data.get('downloads', None)

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
        return f"https://api.theotown.com/store/get_file?name={self._preview_file}"

    @property
    def url(self) -> str:
        """Returns a plugin URL for the plugin store."""
        return f"https://forum.theotown.com/plugins/list?term=%3A{self.id}"

    @property
    def download_url(self) -> str:
        """Returns a URL to download the plugin with."""
        return f"https://forum.theotown.com/plugins/list?download={self.revision_id}"

    @property
    def is_ubiquitous(self) -> bool:
        """Returns true if plugin is available on every platform."""
        return self._platforms == 7

    @property
    def is_on_android(self) -> bool:
        """Returns true if plugin is available on Android."""
        return self._platforms & Platforms.ANDROID.value != 0

    @property
    def is_on_ios(self) -> bool:
        """Returns true if plugin is available on iOS."""
        return self._platforms & Platforms.IOS.value != 0

    @property
    def is_on_desktop(self) -> bool:
        """Returns true if plugin is available on desktop."""
        return self._platforms & Platforms.DESKTOP.value != 0

    def to_embed(self) -> Embed:
        """Returns a discord Embed object."""
        name = truncate_string(self.clean_title)
        description = truncate_string(escape_markdown(self.clean_description), 1024)
        author = f'[{escape_markdown(self.author.username)}]({self.author.url})'
        if self.price == 0:
            price = "🎁 Free"
        else:
            price = f'{self.price:,} <:diamond:423898110293704724>'
            if self._demonetized:
                price += " 🚫"
        footer = f'#{self.id}:{self.version} [{self.revision_id}]'

        embed = (
            PidroidEmbed(title=name, url=self.url)
            .add_field(name='**Description**', value=description, inline=False)
            .add_field(name='**Price**', value=price, inline=False)
            .add_field(name='**Author**', value=author, inline=False)
        )

        if self.__download_count is not None:
            embed.add_field(name='**Downloads**', value=f'{self.__download_count:,}', inline=False)

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

        if self.min_version != 0:
            if self.min_version > 400:
                min_version = format_version_code(self.min_version)
                embed.add_field(name='**Minimal version required**', value=min_version)
        embed.set_footer(text=footer)
        embed.set_image(url=self.preview)
        return embed

class NewPlugin(Plugin):
    """This class represents a new TheoTown plugin. This class differs from Plugin class since it additionally contains time property."""

    def __init__(self, data: dict[str, Any]):
        super().__init__(data)
        self._time: int = data["time"]
        self.approval_author_id: int = data["approval_author"]

    @property
    def time(self) -> int:
        """Returns plugin approval time."""
        return self._time
