from __future__ import annotations

import abc
import enum

from discord.embeds import Embed
from discord.utils import escape_markdown
from typing import Any, override

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


class AbstractPlugin(abc.ABC):

    def __init__(self, data: dict[str, Any]):
        self._plugin_id: int = data['plugin_id']
        self._revision_id: int = data['revision_id']
        self._version: int = data['version']
        self._author: TheoTownUser = TheoTownUser(data['author_id'], data['username'])

        self._name: str = data['name']
        self._description: str = data['description']
        self._price: int = data['price']
        self._demonetized: bool = data['demonetized'] == 1
        self._min_version: int = data['min_version']
        self._category_id: int = data['category']

        self._submission_time: int = data['submission_time']
        self._approval_time: int = data['approval_time']

        self._preview_file: str = data['preview_file']
        self._platforms: int = data['platforms']

    @property
    def plugin_id(self) -> int:
        """Returns plugin ID."""
        return self._plugin_id

    @property
    def revision_id(self) -> int:
        """Returns plugin revision ID."""
        return self._revision_id
    
    @property
    def submission_time(self) -> int:
        """Returns plugin submission time."""
        return self._submission_time

    @property
    def approval_time(self) -> int:
        """Returns plugin approval time."""
        return self._approval_time

    @property
    def clean_name(self) -> str:
        """Returns plugin name with all of the inline translations removed."""
        return clean_inline_translations(self._name)

    @property
    def clean_description(self) -> str:
        """Returns plugin description with all of the inline translations removed."""
        return clean_inline_translations(self._description)

    @property
    def preview(self) -> str:
        """Returns a plugin preview image URL."""
        return f"https://api.theotown.com/store/get_file?name={self._preview_file}"

    @property
    def url(self) -> str:
        """Returns a plugin URL for the plugin store."""
        return f"https://forum.theotown.com/plugins/list?term=%3A{self._plugin_id}"

    @property
    def download_url(self) -> str:
        """Returns a URL to download the plugin with."""
        return f"https://forum.theotown.com/plugins/list?download={self._revision_id}"

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
        name = truncate_string(self.clean_name)
        description = truncate_string(escape_markdown(self.clean_description), 1024)
        author = f'[{escape_markdown(self._author.username)}]({self._author.url})'
        if self._price == 0:
            price = "🎁 Free"
        else:
            price = f'{self._price:,} <:diamond:423898110293704724>'
            if self._demonetized:
                price += " 🚫"
        footer = f'#{self._plugin_id}:{self._version} [{self.revision_id}]'

        embed = (
            PidroidEmbed(title=name, url=self.url)
            .add_field(name='**Description**', value=description, inline=False)
            .add_field(name='**Price**', value=price, inline=False)
            .add_field(name='**Author**', value=author, inline=False)
        )

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

        if self._min_version != 0:
            if self._min_version > 400:
                min_version = format_version_code(self._min_version)
                embed.add_field(name='**Minimal version required**', value=min_version)
        embed.set_footer(text=footer)
        embed.set_image(url=self.preview)
        return embed

class NewPlugin(AbstractPlugin):
    """This class represents a new TheoTown plugin. This class differs from Plugin class since it additionally contains time property."""

    def __init__(self, data: dict[str, Any]):
        super().__init__(data)

class Plugin(AbstractPlugin):
    """This class represents a new TheoTown plugin. This class differs from Plugin class since it additionally contains time property."""

    def __init__(self, data: dict[str, Any]):
        super().__init__(data)
        self._download_count: int = data['downloads']

    @override
    def to_embed(self) -> Embed:
        embed = super().to_embed()
        embed.add_field(name='**Downloads**', value=f'{self._download_count:,}', inline=False)
        return embed

class NewPluginRevision(AbstractPlugin):
    """This class represents a new TheoTown plugin revision."""

    def __init__(self, data: dict[str, Any]):
        super().__init__(data)
        self._author_comments: str = data["author_comments"]
        self._approval_author_id: int = data["approval_author"]

    @override
    def to_embed(self) -> Embed:
        embed = super().to_embed()
        if self._author_comments != "":
            author_comments = truncate_string(escape_markdown(self._author_comments), 1024)
            embed.add_field(name='**Author Comments**', value=author_comments, inline=False)
        return embed
