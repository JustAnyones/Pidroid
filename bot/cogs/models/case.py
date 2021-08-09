from __future__ import annotations

from bson.objectid import ObjectId
from discord.embeds import Embed
from discord.ext.commands.errors import BadArgument
from discord.user import User
from typing import TYPE_CHECKING, Union

from client import Pidroid
from cogs.utils.embeds import create_embed
from cogs.utils.time import humanize, time_since, timestamp_to_datetime, utcnow

if TYPE_CHECKING:
    from cogs.utils.api import API

class Case:
    """This class represents a moderation case."""

    if TYPE_CHECKING:
        _id: ObjectId
        id: str
        type: str
        guild_id: int
        user: User
        moderator: User
        date_issued: int
        date_expires: int
        reason: Union[str, None]

    def __init__(self, api: API, data: dict) -> None:
        self._api = api
        self._serialize(data)

    def _serialize(self, c: dict) -> None:
        """Creates object from a case dictionary."""
        self._id = c["_id"]
        self.id = c["id"]
        self.type = c["type"]
        self.guild_id = c["guild_id"]

        self._user_name = c.get("user_name", None)
        self._moderator_name = c.get("moderator_name", None)

        self.user = c["user"]
        self.moderator = c["moderator"]

        self.date_issued = c["date_issued"]
        self.date_expires = c["date_expires"]
        self.reason = c.get("reason", None)

    async def update(self, reason: str) -> None:
        """Updates case reason."""
        self.reason = reason
        await self._api.update_case_reason(self.id, self.reason)

    async def invalidate(self) -> None:
        """Invalidates specified case. Only applicable to warnings."""
        if self.type != 'warning':
            raise BadArgument("The specified case is not a warning!")
        await self._api.invalidate_case(self.id)

    def to_embed(self) -> Embed:
        """Returns an Embed object representation of the class."""
        embed = create_embed(title=f"[{self.type.capitalize()} #{self.id}] {self.user_name}")
        embed.add_field(name="User", value=self.user.mention)
        embed.add_field(name="Moderator", value=self.moderator.mention)
        embed.add_field(name="Reason", value=self.reason)

        if self.date_expires == -1:
            duration = "∞"
        elif self.date_expires <= utcnow().timestamp():
            duration = "Expired."
        else:
            duration = humanize(timestamp_to_datetime(self.date_expires), max_units=3)

        embed.add_field(name='Duration', value=duration)
        embed.set_footer(text=f"Issued {time_since(timestamp_to_datetime(self.date_issued), max_units=3)}")
        return embed

    @property
    def user_name(self) -> str:
        """Returns user name. Priority is given to the one saved in the database."""
        return self._user_name or str(self.moderator)

    @property
    def moderator_name(self) -> str:
        """Returns moderator name. Priority is given to the one saved in the database."""
        return self._moderator_name or str(self.moderator)

    @property
    def clean_reason(self) -> str:
        """Returns reason as string since there are cases where reason is unavailable."""
        return self.reason or "None"


def setup(client: Pidroid) -> None:
    pass

def teardown(client: Pidroid) -> None:
    pass
