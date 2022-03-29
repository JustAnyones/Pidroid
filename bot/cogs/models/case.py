from __future__ import annotations
import datetime

import bson
import discord

from bson.objectid import ObjectId
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from discord.channel import TextChannel
from discord.embeds import Embed
from discord.ext.commands.context import Context
from discord.ext.commands.errors import BadArgument
from discord.file import File
from discord.guild import Guild
from discord.member import Member
from discord.role import Role
from discord.threads import Thread
from discord.user import User
from typing import TYPE_CHECKING, List, Optional, Union

from ..utils.embeds import PidroidEmbed, SuccessEmbed
from ..utils.paginators import ListPageSource, PidroidPages
from ..utils.time import delta_to_datetime, humanize, time_since, timestamp_to_date, timestamp_to_datetime, utcnow

if TYPE_CHECKING:
    from ..utils.api import API
    Channel = Union[TextChannel, Thread]
    PunishmentChannel = Union[TextChannel, Thread]
    DiscordUser = Union[Member, User]
    Moderator = Union[Member, User]
    Length = Union[int, timedelta, relativedelta]

class BaseCase:

    if TYPE_CHECKING:
        _id: ObjectId
        case_id: str
        type: str
        guild_id: int

        user_id: int
        moderator_id: int

        _user_name: Optional[str]
        _moderator_name: Optional[str]

        date_issued: int
        date_expires: int
        reason: Optional[str]

    def __init__(self, api: API, data: dict) -> None:
        self._api = api
        self._update(data)

    def _update(self, data: dict):
        self._id = data["_id"]
        self.case_id = data["id"]
        self.type = data["type"]
        self.guild_id = data["guild_id"]

        self.user_id = data["user_id"]
        self.moderator_id = data["moderator_id"]

        self._user_name = data.get("user_name", None)
        self._moderator_name = data.get("moderator_name", None)

        self.date_issued = data["date_issued"]
        self.date_expires = data["date_expires"]
        self.reason = data.get("reason", None)

    @property
    def has_expired(self) -> bool:
        """Returns true if the punishment expired."""
        if self.date_expires == -1:
            return False
        return self.date_expires <= utcnow().timestamp()

    @property
    def user_name(self) -> str:
        """Returns user name. Priority is given to the one saved in the database."""
        return self._user_name or str(self.user_id)

    @property
    def moderator_name(self) -> str:
        """Returns moderator name. Priority is given to the one saved in the database."""
        return self._moderator_name or str(self.moderator_id)

    @property
    def clean_reason(self) -> str:
        """Returns reason as string since there are cases where reason is unavailable."""
        return self.reason or "None"

    def to_embed(self) -> Embed:
        """Returns an Embed representation of the class."""
        embed = PidroidEmbed(title=f"[{self.type.capitalize()} #{self.case_id}] {self.user_name}")
        embed.add_field(name="User", value=self.user_name)
        embed.add_field(name="Moderator", value=self.moderator_name)
        embed.add_field(name="Reason", value=self.clean_reason)

        if self.has_expired:
            duration = "Expired."
        elif self.date_expires == -1:
            duration = "∞"
        else:
            duration = humanize(timestamp_to_datetime(self.date_expires), max_units=3)

        embed.add_field(name='Duration', value=duration)
        embed.set_footer(text=f"Issued {time_since(timestamp_to_datetime(self.date_issued), max_units=3)}")
        return embed

class Case(BaseCase):

    if TYPE_CHECKING:
        user: User
        moderator: User

    def __init__(self, api: API, data: dict) -> None:
        super().__init__(api, data)

    def _update(self, data: dict):
        super()._update(data)

        self.user = data["user"]
        self.moderator = data["moderator"]

    @property
    def user_name(self) -> str:
        """Returns user name. Priority is given to the one saved in the database."""
        return self._user_name or str(self.user)

    @property
    def moderator_name(self) -> str:
        """Returns moderator name. Priority is given to the one saved in the database."""
        return self._moderator_name or str(self.moderator)

    async def update_reason(self, reason: str) -> None:
        """Updates the case reason."""
        self.reason = reason
        await self._api.punishments.update_one(
            {"_id": self._id},
            {'$set': {'reason': reason}}
        )

    async def invalidate(self) -> None:
        """Invalidates specified case.

        Note, this only works for warnings."""
        if self.type != "warning":
            raise BadArgument("Only warnings can be invalidated!")
        await self._api.punishments.update_one(
            {"_id": self._id},
            {'$set': {'date_expires': 0, "visible": False}}
        )


class CasePaginator(ListPageSource):
    def __init__(self, paginator_title: str, cases: List[Case], compact: bool = False):
        super().__init__(cases, per_page=6)
        self.compact = compact
        self.embed = PidroidEmbed(title=paginator_title)

    async def format_page(self, menu: PidroidPages, cases: List[Case]) -> Embed:
        self.embed.clear_fields()
        for case in cases:
            if self.compact:
                name = f"#{case.case_id} issued by {case.moderator_name}"
                value = f"\"{case.reason}\" issued on {timestamp_to_date(case.date_issued)}"
            else:
                name = f"Case #{case.case_id}: {case.type}"
                value = (
                    f"**Issued by:** {case.moderator_name}\n"
                    f"**Issued on:** {timestamp_to_date(case.date_issued)}\n"
                    f"**Reason:** {case.clean_reason.capitalize()}"
                )
            self.embed.add_field(name=name, value=value, inline=False)
        self.embed.set_footer(text=f'{len(self.entries)} entry(-ies)')
        return self.embed

class BasePunishment2:

    if TYPE_CHECKING:
        _api: API
        type: str
        case: Optional[Case]
        _channel: PunishmentChannel

        guild: Guild
        user: DiscordUser
        moderator: User
        silent: bool

        # These are not to be used
        # They are only useful when creating a punishment, not revoking it
        _date_expires: Optional[int]
        _reason: Optional[str]

    def __init__(self, ctx: Optional[Context] = None, user: Optional[DiscordUser] = None) -> None:
        # Only used internally, we initialize them here
        self.type = None
        self.case = None
        self._date_expires = None
        self._reason = None

        if ctx is not None:
            self._fill(ctx.bot.api, ctx.guild, ctx.channel, ctx.author, user)

    def _fill(self, api: API, guild: Guild, channel: Optional[PunishmentChannel], moderator: User, user: DiscordUser) -> None:
        self._api: API = api
        self.guild = guild
        self._channel = channel

        self.set_moderator(moderator)
        self.set_user(user)

        self.silent = self._channel is None

    def __str__(self) -> str:
        return self.type or "unknown"

    @property
    def user_name(self) -> str:
        """Returns user name."""
        return str(self.user)

    @property
    def moderator_name(self) -> str:
        """Returns moderator name."""
        return str(self.moderator)

    @property
    def length(self) -> int:
        if self._date_expires is None:
            return -1
        return self._date_expires

    @property
    def length_as_datetime(self) -> Optional[datetime.datetime]:
        if self._date_expires is None:
            return None
        return timestamp_to_datetime(self._date_expires)

    @length.setter
    def length(self, length: Union[int, timedelta, relativedelta]) -> None:
        if isinstance(length, (timedelta, relativedelta)):
            length = delta_to_datetime(length).timestamp()
        self._date_expires = int(length)

    @property
    def reason(self) -> str:
        return self._reason

    @reason.setter
    def reason(self, reason: str) -> None:
        if len(reason) > 512:
            raise BadArgument("Your reason is too long. Please make sure it's below or equal to 512 characters!")
        self._reason = reason

    async def _create_db_entry(self) -> Case:
        case_id = await self._api.get_unique_id(self._api.punishments)
        await self._api.punishments.insert_one({
            "id": case_id,
            "type": self.type,

            "guild_id": bson.Int64(self.guild.id),
            "user_id": bson.Int64(self.user.id),
            "moderator_id": bson.Int64(self.moderator.id),

            "user_name": self.user_name,
            "moderator_name": self.moderator_name,

            "reason": self.reason,
            "date_issued": bson.Int64(int(utcnow().timestamp())),
            "date_expires": self.length,
            "visible": True
        })
        return await self._api.fetch_case(self.guild.id, case_id)

    async def _revoke_punishment_db_entry(self, type: str) -> None:
        """Removes all punishments of specified type for the current user."""
        await self._api.revoke_punishment(type, self.guild.id, self.user.id)

    """Would rather stick these user notification features into an event listener of sorts."""
    async def _notify_user(self, message: str):
        try:
            await self.user.send(message)
        except Exception: # nosec
            pass

    async def _notify_chat(self, message: str, image_file: Optional[File] = None):
        if self.silent:
            return

        embed = SuccessEmbed(message)
        if self.case:
            embed.title = f"Case #{self.case.case_id}"
            if image_file is not None:
                embed.set_image(url=f"attachment://{image_file.filename}")
        try:
            await self._channel.send(embed=embed, file=image_file)
        except Exception: # nosec
            pass

    def set_member(self, member: Member) -> None:
        if isinstance(member, User):
            raise BadArgument("Member required, got user")
        self.user = member

    def set_user(self, user: DiscordUser) -> None:
        if isinstance(user, Member):
            self.user = user._user
        self.user = user

    def set_moderator(self, moderator: DiscordUser) -> None:
        self.moderator = moderator
        if isinstance(moderator, Member):
            self.moderator = moderator._user

    async def issue(self) -> Case:
        raise NotImplementedError

    async def revoke(self) -> None:
        raise NotImplementedError

class BasePunishment:

    if TYPE_CHECKING:
        _api: API
        _channel: PunishmentChannel

        guild: Guild
        user: DiscordUser
        moderator: User
        silent: bool

        # These are not to be used
        # They are only useful when creating a punishment, not revoking it
        _case_id: Optional[str]
        _type: Optional[str]
        _date_expires: Optional[int]
        _date_issued: Optional[int]
        _reason: Optional[str]

    def __init__(self, ctx: Optional[Context] = None, user: Optional[DiscordUser] = None) -> None:
        # Only used internally, we initialize them here
        self._case_id = None
        self._type = None
        self._date_expires = None
        self._date_issued = None
        self._reason = None

        if ctx is not None:
            self._fill(ctx.bot.api, ctx.channel, ctx.guild, user, ctx.author)

    def _fill(self, api: API, channel: Optional[PunishmentChannel], guild: Guild, user: DiscordUser, moderator: User) -> None:
        self._api: API = api
        self._channel = channel
        self.guild = guild

        self.set_user(user)
        self.set_moderator(moderator)

        self.silent = self._channel is None

    @property
    def user_name(self) -> str:
        """Returns user name."""
        return str(self.user)

    @property
    def moderator_name(self) -> str:
        """Returns moderator name."""
        return str(self.moderator)

    @property
    def length(self) -> int:
        if self._date_expires is None:
            return -1
        return self._date_expires

    @length.setter
    def length(self, length: Union[int, timedelta, relativedelta]) -> None:
        if isinstance(length, (timedelta, relativedelta)):
            length = delta_to_datetime(length).timestamp()
        self._date_expires = int(length)

    @property
    def reason(self) -> str:
        return self._reason

    @reason.setter
    def reason(self, reason: str) -> None:
        if len(reason) > 512:
            raise BadArgument("Your reason is too long. Please make sure it's below or equal to 512 characters!")
        self._reason = reason

    def _deserialize(self) -> dict:
        return {
            "id": self._case_id,
            "type": self._type,

            "guild_id": bson.Int64(self.guild.id),
            "user_id": bson.Int64(self.user.id),
            "moderator_id": bson.Int64(self.moderator.id),

            "user_name": self.user_name,
            "moderator_name": self.moderator_name,

            "reason": self.reason,
            "date_issued": self._date_issued,
            "date_expires": self.length,
            "visible": True
        }

    async def _create_punishment(self, p_type: str, length: Union[int, timedelta] = None, reason: Optional[str] = None) -> Case:
        self._type = p_type

        if length:
            self.length = length

        if reason:
            self.reason = reason

        self._date_issued = int(utcnow().timestamp())

        self._case_id = await self._api.get_unique_id(self._api.punishments)
        await self._api.punishments.insert_one(self._deserialize())
        return await self._api.fetch_case(self.guild.id, self._case_id)

    async def _remove_punishment(self, p_type: str) -> None:
        """Removes all punishments of specified type for the current user."""
        await self._api.revoke_punishment(p_type, self.guild.id, self.user.id)

    async def _notify_user(self, message: str):
        try:
            await self.user.send(message)
        except Exception: # nosec
            pass

    async def _notify_chat(self, message: str, image_file: Optional[File] = None):
        if self.silent:
            return

        embed = SuccessEmbed(message)
        if self._case_id:
            embed.title = f"Case #{self._case_id}"
            if image_file is not None:
                embed.set_image(url=f"attachment://{image_file.filename}")
        try:
            await self._channel.send(embed=embed, file=image_file)
        except Exception: # nosec
            pass

    def set_member(self, member: Member) -> None:
        if isinstance(member, User):
            raise BadArgument("Member required, got user")
        self.user = member

    def set_user(self, user: DiscordUser) -> None:
        if isinstance(user, Member):
            self.user = user._user
        self.user = user

    def set_moderator(self, moderator: DiscordUser) -> None:
        self.moderator = moderator
        if isinstance(moderator, Member):
            self.moderator = moderator._user

    async def issue(self) -> Case:
        raise NotImplementedError

    async def revoke(self) -> None:
        raise NotImplementedError


class Warning(BasePunishment):

    if TYPE_CHECKING:
        user: Member

    def __init__(self, ctx: Optional[Context] = None, member: Optional[Member] = None) -> None:
        super().__init__(ctx, member)
        if ctx is not None:
            self.set_member(member)

    def __str__(self) -> str:
        return "warning"

    async def issue(self, reason: str) -> Case:
        """Warns the member."""
        case = await self._create_punishment("warning", timedelta(days=90), reason)
        await self._notify_chat(f"{self.user_name} has been warned: {self.reason}")
        await self._notify_user(f"You have been warned in {self.guild.name} server: {self.reason}")
        return case

class Ban(BasePunishment):

    def __init__(self, ctx: Optional[Context] = None, user: Optional[DiscordUser] = None) -> None:
        super().__init__(ctx, user)

    def __str__(self) -> str:
        return "ban"

    async def issue(self, length: Union[int, timedelta] = None, reason: str = None) -> Case:
        """Bans the user."""
        await self._remove_punishment("jail")
        await self._remove_punishment("mute")
        case = await self._create_punishment("ban", length, reason)

        if self.reason is None:
            await self._notify_chat(f"{self.user_name} was banned!")
            await self._notify_user(f"You have been banned from {self.guild.name} server!")
        else:
            await self._notify_chat(f'{self.user_name} was banned for the following reason: {self.reason}')
            await self._notify_user(f"You have been banned from {self.guild.name} server for the following reason: {self.reason}")

        await self.guild.ban(user=self.user, reason=self.reason)
        return case

class Kick(BasePunishment):

    if TYPE_CHECKING:
        user: Member

    def __init__(self, ctx: Optional[Context] = None, member: Optional[Member] = None) -> None:
        super().__init__(ctx, member)
        if ctx is not None:
            self.set_member(member)

    def __str__(self) -> str:
        return "kick"

    async def issue(self, reason: str = None) -> Case:
        await self._remove_punishment('jail')
        await self._remove_punishment('mute')
        case = await self._create_punishment('kick', reason=reason)

        if self.reason is None:
            await self._notify_chat(f"{self.user_name} was kicked!")
            await self._notify_user(f"You have been kicked from {self.guild.name} server!")
        else:
            await self._notify_chat(f'{self.user_name} was kicked for the following reason: {self.reason}')
            await self._notify_user(f"You have been kicked from {self.guild.name} server for the following reason: {self.reason}")

        await self.user.kick(reason=self.reason)
        return case

class Jail(BasePunishment):

    if TYPE_CHECKING:
        user: Member

    def __init__(self, ctx: Optional[Context] = None, member: Optional[Member] = None) -> None:
        super().__init__(ctx, member)
        if ctx is not None:
            self.set_member(member)

    def __str__(self) -> str:
        return "jail"

    async def issue(self, role: Role, reason: str = None, kidnap: bool = False) -> Case:
        """Jails the member."""
        case = await self._create_punishment("jail", reason=reason)
        await self.user.add_roles(
            discord.utils.get(self.guild.roles, id=role.id),
            reason=f"Jailed by {self.moderator_name}"
        )

        if kidnap:
            await self._notify_chat(f"{self.user_name} was kidnapped!", image_file=discord.File('./resources/bus.png'))
            if self.reason is None:
                await self._notify_user(f"You have been kidnapped in {self.guild.name} server!")
                return case
            await self._notify_user(f"You have been kidnapped in {self.guild.name} server for the following reason: {self.reason}")
            return case

        if self.reason is None:
            await self._notify_chat(f"{self.user_name} was jailed!")
            await self._notify_user(f"You have been jailed in {self.guild.name} server!")
        else:
            await self._notify_chat(f"{self.user_name} was jailed for the following reason: {self.reason}")
            await self._notify_user(f"You have been jailed in {self.guild.name} server for the following reason: {self.reason}")
        return case

    async def revoke(self, role: Role) -> None:
        await self._remove_punishment("jail")
        await self.user.remove_roles(
            discord.utils.get(self.guild.roles, id=role.id),
            reason=f"Released by {self.moderator_name}"
        )
        await self._notify_chat(f"{self.user_name} was unjailed!")
        await self._notify_user(f"You have been unjailed in {self.guild.name} server!")

class Mute(BasePunishment):

    if TYPE_CHECKING:
        user: Member

    def __init__(self, ctx: Optional[Context] = None, member: Optional[Member] = None) -> None:
        super().__init__(ctx, member)
        if ctx is not None:
            self.set_member(member)

    def __str__(self) -> str:
        return "mute"

    async def issue(self, role: Role, length: Union[int, timedelta] = None, reason: str = None) -> Case:
        case = await self._create_punishment("mute", length, reason)
        await self.user.add_roles(
            discord.utils.get(self.guild.roles, id=role.id),
            reason=f"Muted by {self.moderator_name}"
        )

        if self.reason is None:
            await self._notify_chat(f"{self.user_name} was muted!")
            await self._notify_user(f"You have been muted in {self.guild.name} server!")
        else:
            await self._notify_chat(f"{self.user_name} was muted for the following reason: {self.reason}")
            await self._notify_user(f"You have been muted in {self.guild.name} server for the following reason: {self.reason}")
        return case

    async def revoke(self, role: Role) -> None:
        await self._remove_punishment("mute")
        await self.user.remove_roles(
            discord.utils.get(self.guild.roles, id=role.id),
            reason=f"Unmuted by {self.moderator_name}"
        )

        await self._notify_chat(f"{self.user_name} was unmuted!")
        await self._notify_user(f"You have been unmuted in {self.guild.name} server!")

class Ban2(BasePunishment2):

    if TYPE_CHECKING:
        user: DiscordUser

    def __init__(self, ctx: Optional[Context] = None, user: Optional[DiscordUser] = None) -> None:
        super().__init__(ctx, user)
        self.type = "ban"

    async def issue(self) -> Case:
        """Bans the user."""
        await self._revoke_punishment_db_entry("jail")
        await self._revoke_punishment_db_entry("mute")
        await self._revoke_punishment_db_entry("timeout")
        self.case = await self._create_db_entry()

        if self.reason is None:
            await self._notify_chat(f"{self.user_name} was banned!")
            await self._notify_user(f"You have been banned from {self.guild.name} server!")
        else:
            await self._notify_chat(f'{self.user_name} was banned for the following reason: {self.reason}')
            await self._notify_user(f"You have been banned from {self.guild.name} server for the following reason: {self.reason}")

        await self.guild.ban(user=self.user, reason=self.reason)
        return self.case

    async def revoke(self, reason: str = None) -> None:
        await self._revoke_punishment_db_entry("ban")
        await self.user.unban(reason=reason)

        await self._notify_chat(f"{self.user_name} was unbanned!")
        await self._notify_user(f"You have been unbanned from {self.guild.name} server!")

class Timeout(BasePunishment2):

    if TYPE_CHECKING:
        user: Member

    def __init__(self, ctx: Optional[Context] = None, member: Optional[Member] = None) -> None:
        super().__init__(ctx, member)
        self.type = "timeout"

    async def issue(self) -> Case:
        self.case = await self._create_db_entry()
        await self.user.timeout(self.length_as_datetime, reason=self.reason)

        if self.reason is None:
            await self._notify_chat(f"{self.user_name} was timed out!")
            await self._notify_user(f"You have been timed out in {self.guild.name} server!")
        else:
            await self._notify_chat(f"{self.user_name} was timed out for the following reason: {self.reason}")
            await self._notify_user(f"You have been timed out in {self.guild.name} server for the following reason: {self.reason}")
        return self.case

    async def revoke(self, reason: str = None) -> None:
        await self._revoke_punishment_db_entry("timeout")
        await self.user.edit(timed_out_until=None, reason=reason)

        await self._notify_chat(f"Timeout for {self.user_name} was removed!")
        await self._notify_user(f"Your timeout has been removed in {self.guild.name} server!")

async def create_ban(api: API, guild: Guild, channel: PunishmentChannel, moderator: Moderator, user: Member, length: Length, reason: str) -> Case:
    ban = Ban()
    ban._fill(api, channel, guild, user, moderator)
    ban.length = length
    ban.reason = reason
    return await ban.issue()

async def remove_ban(api: API, guild: Guild, channel: PunishmentChannel, moderator: Moderator, user: Member, reason: str = None):
    ban = Ban()
    ban._fill(api, guild, channel, moderator, user)
    await ban.revoke(reason)

async def create_timeout(api: API, guild: Guild, channel: PunishmentChannel, moderator: Moderator, user: Member, length: Length, reason: str) -> Case:
    timeout = Timeout()
    timeout._fill(api, channel, guild, user, moderator)
    timeout.length = length
    timeout.reason = reason
    return await timeout.issue()

async def remove_timeout(api: API, guild: Guild, channel: PunishmentChannel, moderator: Moderator, user: Member, reason: str = None):
    timeout = Timeout()
    timeout._fill(api, guild, channel, moderator, user)
    await timeout.revoke(reason)

async def create_ban_from_context(ctx: Context, user: Member, length: Length, reason: str) -> Case:
    return await create_ban(ctx.bot.api, ctx.guild, ctx.channel, ctx.author, user, length, reason)

async def create_timeout_from_context(ctx: Context, user: Member, length: Length, reason: str) -> Case:
    return await create_timeout(ctx.bot.api, ctx.guild, ctx.channel, ctx.author, user, length, reason)

async def remove_ban_from_context(ctx: Context, user: Member, reason: str):
    return await remove_ban(ctx.bot.api, ctx.guild, ctx.channel, ctx.author, user, reason)

async def remove_timeout_from_context(ctx: Context, user: Member, reason: str):
    return await remove_timeout(ctx.bot.api, ctx.guild, ctx.channel, ctx.author, user, reason)
