from dataclasses import dataclass
import datetime

from discord import Guild, Role

from pidroid.modules.moderation.models.types import PunishmentMode, PunishmentType
from pidroid.utils.aliases import DiscordUser


@dataclass
class PunishmentInfo:
    guild: Guild
    channel_id: int

    moderator: DiscordUser
    target: DiscordUser

    punishment_type: PunishmentType | None = None
    punishment_mode: PunishmentMode = PunishmentMode.ISSUE
    reason: str | None = None
    expires_at: datetime.datetime | None = None

    is_public: bool = True
    delete_message_days: int = 1

    jail_role: Role | None = None
    is_kidnapping: bool = False