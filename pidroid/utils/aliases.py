from discord import (
    CategoryChannel, ForumChannel, StageChannel, TextChannel, Thread, VoiceChannel, DMChannel, GroupChannel, PartialMessageable,
    Member, User
)

from typing import Union
from typing_extensions import TypeAlias

GuildChannel: TypeAlias     = Union[TextChannel, VoiceChannel, CategoryChannel, StageChannel, Thread, ForumChannel]
AllChannels: TypeAlias      = Union[TextChannel, VoiceChannel, CategoryChannel, StageChannel, Thread, ForumChannel, DMChannel, GroupChannel, PartialMessageable]
WebhookGuildChannel: TypeAlias = Union[StageChannel, TextChannel, VoiceChannel]
MessageableGuildChannel: TypeAlias = Union[StageChannel, TextChannel, Thread, VoiceChannel]
# workaround for stupid mypy bug https://github.com/python/mypy/issues/11673, used in assertions
MessageableGuildChannelTuple       = (StageChannel, TextChannel, Thread, VoiceChannel)

DiscordUser: TypeAlias             = Member | User
