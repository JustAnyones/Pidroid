import datetime

from discord import Colour
from discord.embeds import Embed
from discord.types.embed import EmbedType
from typing import Any

from pidroid.constants import EMBED_COLOUR

class PidroidEmbed(Embed):

    def __init__(
        self,
        *,
        title: Any | None = None,
        type: EmbedType = 'rich',
        url: Any | None = None,
        description: Any | None = None,
        timestamp: datetime.datetime | None = None
    ):
        super().__init__(colour=EMBED_COLOUR, title=title, type=type, url=url, description=description, timestamp=timestamp)

    @classmethod
    def from_error(cls, description: str):
        return Embed(description=description, colour=Colour.red())

    @classmethod
    def from_success(cls, description: str):
        return Embed(description=description, colour=Colour.green())

class SuccessEmbed(Embed):
    def __init__(self, description: str | None = None):
        super().__init__(description=description, colour=Colour.green())

class ErrorEmbed(Embed):
    def __init__(self, description: str | None = None):
        super().__init__(description=description, colour=Colour.red())

