from __future__ import annotations

import bson
import discord

from bson.objectid import ObjectId
from datetime import timedelta
from discord.embeds import Embed
from discord.ext.commands.context import Context
from discord.ext.commands.errors import BadArgument
from discord.file import File
from discord.member import Member
from discord.role import Role
from discord.user import User
from pymongo.results import InsertOneResult
from typing import TYPE_CHECKING, List, Optional, Union

from ..utils.embeds import create_embed, success
from ..utils.paginators import ListPageSource, PidroidPages
from ..utils.time import humanize, time_since, timedelta_to_datetime, timestamp_to_date, timestamp_to_datetime, utcnow

if TYPE_CHECKING:
    from cogs.utils.api import API


class BaseModerationEntry:

    if TYPE_CHECKING:
        _id: ObjectId
        case_id: str
        type: str
        guild_id: int

        _user_name: Optional[str]
        _moderator_name: Optional[str]

        user: User
        moderator: User

        date_issued: int
        date_expires: int
        reason: Optional[str]

    def __init__(self) -> None:
        self.case_id = None
        self.reason = None
        self.date_expires = None

    def _serialize(self, data: dict):
        """Serializes an object from a dictionary."""
        self._id = data["_id"]
        self.case_id = data["id"]
        self.type = data["type"]

        self.guild_id = data["guild_id"]

        self._user_name = data.get("user_name", None)
        self._moderator_name = data.get("moderator_name", None)

        self.user = data["user"]
        self.moderator = data["moderator"]

        self.date_issued = data["date_issued"]
        self.date_expires = data["date_expires"]
        self.reason = data.get("reason", None)

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

    def to_embed(self) -> Embed:
        """Returns an Embed object representation of the class."""
        embed = create_embed(title=f"[{self.type.capitalize()} #{self.case_id}] {self.user_name}")
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


class Case(BaseModerationEntry):

    def __init__(self, api: API, data: dict) -> None:
        super().__init__()
        self._api = api
        self._serialize(data)

    def _add_embed_field(self, embed: Embed, show_compact: bool = False) -> None:
        if show_compact:
            name = f"#{self.case_id} issued by {self.moderator_name}"
            value = f"\"{self.reason}\" issued on {timestamp_to_date(self.date_issued)}"
        else:
            name = f"Case #{self.case_id}: {self.type}"
            value = (
                f"**Issued by:** {self.moderator_name}\n"
                f"**Issued on:** {timestamp_to_date(self.date_issued)}\n"
                f"**Reason:** {self.clean_reason.capitalize()}"
            )
        embed.add_field(name=name, value=value, inline=False)

    async def update(self, reason: str) -> None:
        """Updates the case reason."""
        self.reason = reason
        await self._api.punishments.update_one(
            {"_id": self._id},
            {'$set': {'reason': reason}}
        )

    async def invalidate(self) -> None:
        """Invalidates specified warning."""
        if self.type != "warning":
            raise BadArgument("Only warnings can be invalidated!")
        await self._api.punishments.update_one(
            {"_id": self._id},
            {'$set': {'date_expires': 0, "visible": False}}
        )


class CasePaginator(ListPageSource):
    def __init__(self, paginator_title: str, cases: List[Case], warnings: bool = False):
        super().__init__(cases, per_page=6)
        self.warnings = warnings
        self.embed = create_embed(title=paginator_title)

    async def format_page(self, menu: PidroidPages, cases: List[Case]) -> Embed:
        self.embed.clear_fields()

        for case in cases:
            case._add_embed_field(self.embed, self.warnings)

        if self.get_max_pages() > 1:
            self.embed.set_footer(text=f'{len(self.entries)} entries')
        return self.embed


class Punishment(BaseModerationEntry):

    if TYPE_CHECKING:
        _api: API
        silent: bool

        user: Union[Member, User]

    def __init__(self, ctx: Context, user: Union[Member, User]) -> None:
        super().__init__()
        self._ctx = ctx
        self._api = ctx.bot.api
        self.silent = False

        self.guild_id = ctx.guild.id

        self.user = user
        self.moderator = ctx.author

        self._user_name = str(self.user)
        self._moderator_name = str(self.moderator)

    def _deserialize(self) -> dict:
        return {
            "id": self.case_id,
            "type": self.type,
            "guild_id": bson.Int64(self.guild_id),
            "user_id": bson.Int64(self.user.id),
            "user_name": str(self.user),
            "moderator_id": bson.Int64(self.moderator.id),
            "moderator_name": str(self.moderator),
            "reason": self.reason,
            "date_issued": self.date_issued,
            "date_expires": self.length,
            "visible": True
        }

    @property
    def length(self) -> int:
        if self.date_expires is None:
            return -1
        return self.date_expires

    @length.setter
    def length(self, length: Union[int, timedelta]):
        if isinstance(length, timedelta):
            length = timedelta_to_datetime(length).timestamp()
        self.date_expires = int(length)

    async def _notify_chat(self, message: str, image_file: Optional[File] = None):
        if self.silent:
            return

        embed = success(message)
        if self.case_id:
            embed.title = f"Case #{self.case_id}"
            if image_file is not None:
                embed.set_image(url=f"attachment://{image_file.filename}")
        try:
            await self._ctx.send(embed=embed, file=image_file)
        except Exception: # nosec
            pass

    async def _notify_user(self, message: str):
        try:
            await self.user.send(message)
        except Exception: # nosec
            pass

    async def issue(self, type: str, length: Union[int, timedelta] = None, reason: Optional[str] = None) -> Case:
        self.date_issued = int(utcnow().timestamp())

        self.type = type

        if length:
            self.length = length

        if reason:
            if len(reason) > 512:
                raise BadArgument("Your reason is too long. Please make sure it's below or equal to 512 characters!")
            self.reason = reason

        self.case_id = await self._api.get_unique_id(self._api.punishments)
        res: InsertOneResult = await self._api.punishments.insert_one(self._deserialize())
        self._id = res.inserted_id

    async def _revoke(self, type: str) -> None:
        """Revokes all punishments of specified type for the user."""
        self.type = type
        await self._api.punishments.update_many(
            {'type': self.type, 'guild_id': self._ctx.guild.id, 'user_id': self.user.id},
            {'$set': {'date_expires': 0}}
        )

    async def warn(self, reason: str):
        """Warns the member."""
        await self.issue("warning", timedelta(days=120), reason)
        await self._notify_chat(f"{self.user_name} has been warned: {self.reason}")
        await self._notify_user(f"You have been warned in {self._ctx.guild.name} server: {self.reason}")

    async def ban(self, length: Union[int, timedelta] = None, reason: str = None):
        """Bans the user."""
        await self._revoke("jail")
        await self._revoke("mute")
        await self.issue("ban", length, reason)

        guild = self._ctx.guild

        if self.reason is None:
            await self._notify_chat(f"{self.user_name} was banned!")
            await self._notify_user(f"You have been banned from {guild.name} server!")
        else:
            await self._notify_chat(f'{self.user_name} was banned for the following reason: {self.reason}')
            await self._notify_user(f"You have been banned from {guild.name} server for the following reason: {self.reason}")

        await guild.ban(user=self.user, reason=self.reason)

    async def kick(self, reason: str = None):
        """Kicks the member."""
        await self._revoke('jail')
        await self._revoke('mute')
        await self.issue('kick', reason=reason)

        if self.reason is None:
            await self._notify_chat(f"{self.user_name} was kicked!")
            await self._notify_user(f"You have been kicked from {self._ctx.guild.name} server!")
        else:
            await self._notify_chat(f'{self.user_name} was kicked for the following reason: {self.reason}')
            await self._notify_user(f"You have been kicked from {self._ctx.guild.name} server for the following reason: {self.reason}")

        await self.user.kick(reason=self.reason)

    async def jail(self, role: Role, reason: str = None, kidnap: bool = False):
        """Jails the member."""
        await self.issue("jail", reason=reason)
        guild = self._ctx.guild
        await self.user.add_roles(
            discord.utils.get(guild.roles, id=role.id),
            reason=f"Jailed by {self.moderator_name}"
        )

        if kidnap:
            await self._notify_chat(f"{self.user_name} was kidnapped!", image_file=discord.File('./resources/bus.png'))
            if self.reason is None:
                return await self._notify_user(f"You have been kidnapped in {self._ctx.guild.name} server!")
            return await self._notify_user(f"You have been kidnapped in {self._ctx.guild.name} server for the following reason: {self.reason}")

        if self.reason is None:
            await self._notify_chat(f"{self.user_name} was jailed!")
            await self._notify_user(f"You have been jailed in {guild.name} server!")
        else:
            await self._notify_chat(f"{self.user_name} was jailed for the following reason: {self.reason}")
            await self._notify_user(f"You have been jailed in {guild.name} server for the following reason: {self.reason}")

    async def unjail(self, role: Role):
        """Unjails the member."""
        await self._revoke("jail")
        await self.user.remove_roles(
            discord.utils.get(self._ctx.guild.roles, id=role.id),
            reason=f"Released by {self.moderator_name}"
        )

        await self._notify_chat(f"{self.user_name} was unjailed!")
        await self._notify_user(f"You have been unjailed in {self._ctx.guild.name} server!")

    async def mute(self, role: Role, length: Union[int, timedelta] = None, reason: str = None):
        """Mutes the member."""
        await self.issue("mute", length, reason)
        guild = self._ctx.guild
        await self.user.add_roles(
            discord.utils.get(guild.roles, id=role.id),
            reason=f"Muted by {self.moderator_name}"
        )

        if self.reason is None:
            await self._notify_chat(f"{self.user_name} was muted!")
            await self._notify_user(f"You have been muted in {guild.name} server!")
        else:
            await self._notify_chat(f"{self.user_name} was muted for the following reason: {self.reason}")
            await self._notify_user(f"You have been muted in {guild.name} server for the following reason: {self.reason}")

    async def unmute(self, role: Role):
        """Unmutes the member."""
        await self._revoke("mute")
        await self.user.remove_roles(
            discord.utils.get(self._ctx.guild.roles, id=role.id),
            reason=f"Unmuted by {self.moderator_name}"
        )

        await self._notify_chat(f"{self.user_name} was unmuted!")
        await self._notify_user(f"You have been unmuted in {self._ctx.guild.name} server!")


def setup(client) -> None:
    pass

def teardown(client) -> None:
    pass
