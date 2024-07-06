from discord import (
    CategoryChannel, ForumChannel, StageChannel, TextChannel, Thread, VoiceChannel, DMChannel, GroupChannel, PartialMessageable,
    Member, User
)

from typing import TypeAlias

GuildChannel: TypeAlias     = TextChannel | VoiceChannel | CategoryChannel | StageChannel | Thread | ForumChannel
AllChannels: TypeAlias      = TextChannel | VoiceChannel | CategoryChannel | StageChannel | Thread | ForumChannel | DMChannel | GroupChannel | PartialMessageable
WebhookGuildChannel: TypeAlias = StageChannel | TextChannel | VoiceChannel
MessageableGuildChannel: TypeAlias = StageChannel | TextChannel | Thread | VoiceChannel
# workaround for stupid mypy bug https://github.com/python/mypy/issues/11673, used in assertions
MessageableGuildChannelTuple       = (StageChannel, TextChannel, Thread, VoiceChannel)

DiscordUser: TypeAlias             = Member | User
