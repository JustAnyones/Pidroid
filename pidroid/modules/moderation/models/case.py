from __future__ import annotations

import datetime

from discord import Embed
from discord.ext.commands import BadArgument
from typing import TYPE_CHECKING

from pidroid.modules.moderation.models.types import PunishmentType
from pidroid.utils.embeds import PidroidEmbed
from pidroid.utils.time import humanize, time_since, utcnow
from pidroid.utils.types import DiscordUser

if TYPE_CHECKING:
    from pidroid.utils.api import API, PunishmentTable
    Moderator = DiscordUser

MAX_REASON_LENGTH = 512

class Case:
    def __init__(
        self,
        api: API,
        data: PunishmentTable
    ) -> None:
        self.__api = api
        self.__id = data.id
        self.__case_id = data.case_id
        self.__type = PunishmentType[data.type.upper()]
        self.__guild_id = data.guild_id

        self.__user_id = data.user_id
        self.__moderator_id = data.moderator_id

        self.__user_name = data.user_name
        self.__moderator_name = data.moderator_name

        self.__reason = data.reason
        self.__date_issued = data.issue_date
        self.__date_expires = data.expire_date

        self.__visible = data.visible
        self.__handled = data.handled

    async def _update(self) -> None:
        await self.__api.update_case_by_internal_id(self.__id, self.__reason, self.__date_expires, self.__visible, self.__handled)

    @property
    def case_id(self) -> int:
        """Returns the ID of the case."""
        return self.__case_id

    @property
    def type(self) -> PunishmentType:
        """Returns the type of the punishment."""
        return self.__type

    @property
    def user_name(self) -> str:
        """Returns user name. Priority is given to the one saved in the database."""
        return self.__user_name or str(self.__user_id)

    @property
    def moderator_name(self) -> str:
        """Returns moderator name. Priority is given to the one saved in the database."""
        return self.__moderator_name or str(self.__moderator_id)

    @property
    def user_id(self) -> int:
        """Returns the ID of the punished user."""
        return self.__user_id

    @property
    def clean_reason(self) -> str:
        """Returns reason as string since there are cases where reason is unavailable."""
        return self.__reason or "None"

    @property
    def date_issued(self) -> datetime.datetime:
        """Returns the date of when the punishment was issued."""
        return self.__date_issued

    @property
    def date_expires(self) -> datetime.datetime | None:
        """Returns the date of when the punishment expires."""
        return self.__date_expires

    @property
    def has_expired(self) -> bool:
        """Returns true if the punishment expired."""
        # If case expired by getting explicitly handled
        if self.__handled:
            return True
        # If the date of expiration is set to none, then it never expires
        if self.date_expires is None:
            return False
        # Otherwise, if current date is above or equal to the date is should expire, then it IS expired
        return self.date_expires <= utcnow()

    def to_embed(self) -> Embed:
        """Returns an Embed representation of the class."""
        embed = PidroidEmbed(title=f"[{self.type.value.capitalize()} #{self.case_id}] {self.user_name}")
        embed.add_field(name="User", value=self.user_name)
        embed.add_field(name="Moderator", value=self.moderator_name)
        embed.add_field(name="Reason", value=self.clean_reason)

        if self.has_expired:
            duration = "Expired."
        elif self.date_expires is None:
            duration = "∞"
        else:
            duration = humanize(self.date_expires, max_units=3)

        embed.add_field(name='Duration', value=duration)
        embed.set_footer(text=f"Issued {time_since(self.date_issued, max_units=3)}")
        return embed

    async def update_reason(self, reason: str) -> None:
        """Updates the case reason."""
        if len(reason) > MAX_REASON_LENGTH:
            raise BadArgument(f"Reason can only be {MAX_REASON_LENGTH} characters!")
        self.__reason = reason
        await self._update()

    async def invalidate(self) -> None:
        """Invalidates the specified case.

        Note, this only works for warnings."""
        if self.type != PunishmentType.WARNING:
            raise BadArgument("Only warnings can be invalidated!")
        self.__date_expires = utcnow()
        self.__handled = True
        self.__visible = False
        await self._update()

    async def expire(self):
        """Expires the current case."""
        await self.__api.expire_cases_by_type(self.__type, self.__guild_id, self.__user_id)
