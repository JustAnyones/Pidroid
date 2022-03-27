import datetime

from discord import Colour
from discord.embeds import Embed
from discord.types.embed import EmbedType
from typing import Any, Optional

from constants import EMBED_COLOUR

class PidroidEmbed(Embed):

    def __init__(
        self,
        *,
        title: Optional[Any] = None,
        type: EmbedType = 'rich',
        url: Optional[Any] = None,
        description: Optional[Any] = None,
        timestamp: Optional[datetime.datetime] = None
    ):
        super().__init__(colour=EMBED_COLOUR, title=title, type=type, url=url, description=description, timestamp=timestamp)

class SuccessEmbed(Embed):
    def __init__(self, description: str):
        super().__init__(description=description, colour=Colour.green())

class ErrorEmbed(Embed):
    def __init__(self, description: str):
        super().__init__(description=description, colour=Colour.red())

def error(content: str) -> Embed:
    return Embed(description=content, color=Colour.red())
