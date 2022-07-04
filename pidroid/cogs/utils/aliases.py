from discord import (
    CategoryChannel, ForumChannel, StageChannel, TextChannel, Thread, VoiceChannel,
    Member, User
)

from typing import Union
from typing_extensions import TypeAlias

GuildChannel: TypeAlias = Union[TextChannel, VoiceChannel, CategoryChannel, StageChannel, Thread, ForumChannel]
GuildTextChannel = Union[TextChannel, Thread]
DiscordUser: TypeAlias = Union[Member, User]
