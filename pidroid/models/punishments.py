from __future__ import annotations

import datetime
import discord

from datetime import timedelta
from dateutil.relativedelta import relativedelta
from discord import Embed, File, Guild, Member, Role, User
from discord.ext.commands import BadArgument
from discord.utils import format_dt
from enum import Enum
from typing import TYPE_CHECKING, Optional, Union

from pidroid.utils import try_message_user
from pidroid.utils.aliases import MessageableGuildChannel
from pidroid.utils.embeds import PidroidEmbed
from pidroid.utils.file import Resource
from pidroid.utils.time import delta_to_datetime, humanize, time_since, utcnow

if TYPE_CHECKING:
    from pidroid.utils.api import API, PunishmentTable
    DiscordUser = Union[Member, User]
    Moderator = Union[Member, User]
    Length = Union[timedelta, relativedelta]

MAX_REASON_LENGTH = 512

class PunishmentType(Enum):
    ban = "ban"
    kick = "kick"
    warning = "warning"
    jail = "jail"
    timeout = "timeout"
    mute = "mute" # Backwards compatibility
    unknown = "unknown"

class Case:

    if TYPE_CHECKING:
        __id: int
        __case_id: int
        __type: PunishmentType
        __guild_id: int

        __user_id: int
        __moderator_id: int

        __user_name: Optional[str]
        __moderator_name: Optional[str]

        __user: Optional[User]
        __moderator: Optional[User]

        __reason: Optional[str]
        __date_issued: datetime.datetime
        __date_expires: Optional[datetime.datetime]

        __visible: bool
        __handled: bool

    def __init__(self, api: API) -> None:
        self.__api = api

    async def _from_table(self, data: PunishmentTable):
        self.__id = data.id
        self.__case_id = data.case_id
        self.__type = PunishmentType[data.type]
        self.__guild_id = data.guild_id

        self.__user_id = data.user_id
        self.__moderator_id = data.moderator_id

        self.__user_name = data.user_name
        self.__moderator_name = data.moderator_name

        self.__user = await self.__api.client.get_or_fetch_user(self.__user_id)
        self.__moderator = await self.__api.client.get_or_fetch_user(self.__moderator_id)

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
        if self.__user:
            return self.__user_name or str(self.__user)
        return self.__user_name or str(self.__user_id)

    @property
    def moderator_name(self) -> str:
        """Returns moderator name. Priority is given to the one saved in the database."""
        if self.__moderator:
            return self.__moderator_name or str(self.__moderator)
        return self.__moderator_name or str(self.__moderator_id)

    @property
    def user(self) -> Optional[User]:
        return self.__user

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
    def date_expires(self) -> Optional[datetime.datetime]:
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
        if self.type != PunishmentType.warning:
            raise BadArgument("Only warnings can be invalidated!")
        self.__date_expires = utcnow()
        self.__handled = True
        self.__visible = False
        await self._update()

    async def expire(self):
        """Expires the current case."""
        await self.__api.expire_cases_by_type(self.__type, self.__guild_id, self.__user_id)

class BasePunishment:

    __type__: PunishmentType = PunishmentType.unknown

    if TYPE_CHECKING:
        _api: API
        case: Optional[Case]
        _channel: Optional[MessageableGuildChannel]

        guild: Guild
        user: DiscordUser
        moderator: User
        send_message_to_channel: bool

        # These are not to be used
        # They are only useful when creating a punishment, not revoking it
        _expiration_date: Optional[datetime.datetime]
        _reason: Optional[str]

        _appeal_url: Optional[str]

    def __init__(self, api: API, guild: Guild) -> None:
        # Only used internally, we initialize them here
        self.case = None
        self._expiration_date = None
        self._reason = None

        self._api = api
        self.guild = guild

        self._appeal_url = None

    def __str__(self) -> str:
        return self.__type__.value

    @property
    def user_name(self) -> str:
        """Returns user name."""
        return str(self.user)

    @property
    def moderator_name(self) -> str:
        """Returns moderator name."""
        return str(self.moderator)

    def set_length(self, length: Optional[Union[timedelta, relativedelta, None]]) -> None:
        """Sets punishment length."""
        if length is None:
            self._expiration_date = None
        else:
            self._expiration_date = delta_to_datetime(length)

    @property
    def length_as_string(self) -> str:
        if self._expiration_date is None:
            return "permanent"
        return humanize(self._expiration_date, max_units=3)

    @property
    def expiration_date(self) -> Optional[datetime.datetime]:
        """Returns the date of when the punishment expires."""
        return self._expiration_date

    @property
    def reason(self) -> Optional[str]:
        """Returns the reason for the punishment."""
        return self._reason

    @reason.setter
    def reason(self, reason: Optional[str]) -> None:
        if reason and len(reason) > MAX_REASON_LENGTH:
            raise ValueError(
                f"Your reason is too long. Please make sure it's below or equal to {MAX_REASON_LENGTH} characters!"
            )
        self._reason = reason

    async def _create_case_record(self) -> Case:
        return await self._api.insert_punishment_entry(
            self.__type__.value,
            self.guild.id,
            self.user.id, self.user_name,
            self.moderator.id, self.moderator_name,
            self.reason, self.expiration_date
        )

    async def _expire_cases_by_type(self, type: PunishmentType) -> None:
        """Removes all punishments of specified type for the current user."""
        await self._api.expire_cases_by_type(type, self.guild.id, self.user.id)

    def _set_user(self, user: DiscordUser) -> None:
        if isinstance(user, Member):
            self.user = user._user
        self.user = user

    def _set_moderator(self, moderator: DiscordUser) -> None:
        if isinstance(moderator, Member):
            self.moderator = moderator._user
        else:
            self.moderator = moderator

    @property
    def audit_log_issue_reason(self) -> str:
        raise NotImplementedError

    @property
    def audit_log_revoke_reason(self) -> str:
        raise NotImplementedError

    @property
    def public_message_issue_embed(self) -> Embed:
        if self.case is None:
            raise BadArgument("Case object was not retrieved")
        embed = Embed(title=f"Case #{self.case.case_id}", color=discord.Color.green())
        return embed

    @property
    def public_message_issue_file(self) -> Optional[File]:
        return None

    @property
    def public_message_revoke_embed(self) -> Embed:
        return Embed(color=discord.Color.green())

    @property
    def private_message_issue_embed(self) -> Embed:
        embed = Embed(color=discord.Color.red())

        if self.case:
            embed.title = f"New punishment received [case #{self.case.case_id}]"
            if self.case.date_expires is None:
                duration = "Never"
            else:
                duration = format_dt(self.case.date_expires)
        else:
            embed.title = "New punishment received"
            if self.expiration_date is None:
                duration = "Never"
            else:
                duration = format_dt(self.expiration_date)

        embed.add_field(name="Type", value=self.__str__().capitalize())
        embed.add_field(name="Reason", value=self.reason or "No reason specified")
        embed.add_field(name="Expires in", value=duration)
        if self._appeal_url and self.__type__ == PunishmentType.ban:
            embed.add_field(name="You can appeal the punishment here:", value=self._appeal_url)
        embed.set_footer(text=f'Server: {self.guild.name} ({self.guild.id})')
        return embed

    @property
    def private_message_revoke_embed(self) -> Embed:
        embed = Embed(title='Punishment revoked', color=discord.Color.green())
        embed.add_field(name='Type', value=self.__type__.value.capitalize())
        embed.add_field(name='Reason', value=self.reason or "No reason specified")
        embed.set_footer(text=f'Server: {self.guild.name} ({self.guild.id})')
        return embed

    async def create_case(self):
        """Creates an case entry for the punishment in the database."""
        config = await self._api.client.fetch_guild_configuration(self.guild.id)
        self._appeal_url = config.appeal_url

    async def issue(self) -> Case:
        """Issues the punishment for the user."""
        raise NotImplementedError

    async def revoke(self, *, reason: Optional[str] = None) -> None:
        """Revokes the punishment from the user.
        
        Reason for the revocation can be optionally provided."""
        raise NotImplementedError

class Ban(BasePunishment):

    __type__ = PunishmentType.ban

    if TYPE_CHECKING:
        user: DiscordUser

    def __init__(
        self,
        api: API,
        guild: Guild,
        *,
        channel: Optional[MessageableGuildChannel],
        moderator: Moderator,
        user: DiscordUser
    ) -> None:
        super().__init__(api, guild)
        self._channel = channel
        self._set_moderator(moderator)
        self._set_user(user)

    @property
    def audit_log_issue_reason(self) -> str:
        reason = f"Banned on behalf of {self.moderator_name}"
        if reason:
            reason += f" for the following reason: {self.reason}"
        else:
            reason += ", reason was not specified"
        if self.expiration_date:
            reason += f", expires in {humanize(self.expiration_date, max_units=2)}."
        return reason

    @property
    def audit_log_revoke_reason(self) -> str:
        reason = f"Unbanned on behalf of {self.moderator_name}"
        if reason:
            reason += f" for the following reason: {self.reason}"
        else:
            reason += ", reason was not specified"
        return reason

    @property
    def public_message_issue_embed(self) -> Embed:
        embed = super().public_message_issue_embed
        embed.description = f"{self.user_name} was banned"
        if self.reason:
            embed.description += f" for the following reason: {self.reason}"
        if self.expiration_date:
            embed.description += f"\nExpires {format_dt(self.expiration_date, style='R')}."
        return embed

    @property
    def public_message_revoke_embed(self) -> Embed:
        embed = super().public_message_revoke_embed
        embed.description = f"{self.user_name} was unbanned"
        return embed

    async def create_case(self) -> Case:
        await super().create_case()
        # When we ban the user, we will remove their jail, mute punishments
        await self._expire_cases_by_type(PunishmentType.jail)
        await self._expire_cases_by_type(PunishmentType.mute)
        # Actually, Discord persists timeouts during bans
        return await self._create_case_record()

    async def issue(self) -> Case:
        """Bans the user and creates new database entry."""
        message = await try_message_user(self.user, embed=self.private_message_issue_embed)
        try:
            await self.guild.ban(user=self.user, reason=self.audit_log_issue_reason, delete_message_days=1) # type: ignore
        except Exception as e:
            if message:
                await message.delete()
            raise e
        self.case = await self.create_case()
        self._api.client.dispatch("pidroid_ban_issue", self)
        return self.case

    async def revoke(self, *, reason: Optional[str] = None) -> None:
        """Unbans the user and updates database entry."""
        self.reason = reason
        await self.guild.unban(self.user, reason=self.audit_log_revoke_reason) # type: ignore
        await self._expire_cases_by_type(PunishmentType.ban)
        self._api.client.dispatch("pidroid_ban_revoke", self)

class Kick(BasePunishment):

    __type__ = PunishmentType.kick

    if TYPE_CHECKING:
        user: Member

    def __init__(
        self,
        api: API,
        guild: Guild,
        *,
        channel: Optional[MessageableGuildChannel],
        moderator: Moderator,
        user: DiscordUser
    ) -> None:
        super().__init__(api, guild)
        self._channel = channel
        self._set_moderator(moderator)
        self._set_user(user)

    @property
    def audit_log_issue_reason(self) -> str:
        reason = f"Kicked on behalf of {self.moderator_name}"
        if reason:
            return reason + f" for the following reason: {self.reason}"
        return reason + ", reason was not specified"

    @property
    def public_message_issue_embed(self) -> Embed:
        embed = super().public_message_issue_embed
        embed.description = f"{self.user_name} was kicked"
        if self.reason:
            embed.description += f" for the following reason: {self.reason}"
        return embed

    async def create_case(self) -> Case:
        await super().create_case()
        # When we ban the user, we will remove their jail, mute punishments
        await self._expire_cases_by_type(PunishmentType.jail)
        await self._expire_cases_by_type(PunishmentType.mute)
        return await self._create_case_record()

    async def issue(self) -> Case:
        message = await try_message_user(self.user, embed=self.private_message_issue_embed)
        try:
            await self.user.kick(reason=self.audit_log_issue_reason)
        except Exception as e:
            if message:
                await message.delete()
            raise e
        self.case = await self.create_case()
        self._api.client.dispatch("pidroid_kick_issue", self)
        return self.case

class Jail(BasePunishment):

    __type__ = PunishmentType.jail

    if TYPE_CHECKING:
        user: Member

    def __init__(
        self,
        api: API,
        guild: Guild,
        *,
        channel: Optional[MessageableGuildChannel],
        moderator: Moderator,
        user: DiscordUser,
        role: Role,
        kidnapping: bool = False
    ) -> None:
        super().__init__(api, guild)
        self._channel = channel
        self._set_moderator(moderator)
        self._set_user(user)
        self.__role = role
        self.__is_kidnapping = kidnapping

    @property
    def audit_log_issue_reason(self) -> str:
        reason = f"Jailed on behalf of {self.moderator_name}"
        if reason:
            reason += f" for the following reason: {self.reason}"
        else:
            reason += ", reason was not specified"
        if self.expiration_date:
            reason += f", expires in {humanize(self.expiration_date, max_units=2)}."
        return reason

    @property
    def audit_log_revoke_reason(self) -> str:
        reason = f"Released from jail on behalf of {self.moderator_name}"
        if reason:
            reason += f" for the following reason: {self.reason}"
        else:
            reason += ", reason was not specified"
        return reason

    @property
    def public_message_issue_embed(self) -> Embed:
        embed = super().public_message_issue_embed
        if self.__is_kidnapping:
            embed.description = f"{self.user_name} was kidnapped"
            embed.set_image(url='attachment://bus.png')
        else:
            embed.description = f"{self.user_name} was jailed"
        if self.reason:
            embed.description += f" for the following reason: {self.reason}"
        if self.expiration_date:
            embed.description += f"\nExpires {format_dt(self.expiration_date, 'R')}."
        return embed

    @property
    def public_message_issue_file(self) -> File:
        return File(Resource('bus.png'))

    @property
    def public_message_revoke_embed(self) -> Embed:
        embed = super().public_message_revoke_embed
        embed.description = f"{self.user_name} was released from jail"
        return embed

    @property
    def is_kidnapping(self) -> bool:
        """Returns true if kidnapping specific messages and assets should be sent."""
        return self.__is_kidnapping

    async def create_case(self) -> Case:
        await super().create_case()
        return await self._create_case_record()

    async def issue(self) -> Case:
        """Jails the member."""
        await self.user.add_roles(self.__role, reason=self.audit_log_issue_reason) # type: ignore
        self.case = await self.create_case()
        self._api.client.dispatch("pidroid_jail_issue", self)
        return self.case

    async def revoke(self, *, reason: Optional[str] = None):
        self.reason = reason
        await self.user.remove_roles(self.__role, reason=self.audit_log_revoke_reason) # type: ignore
        await self._expire_cases_by_type(PunishmentType.jail)
        self._api.client.dispatch("pidroid_jail_revoke", self)

class Warning(BasePunishment):

    __type__ = PunishmentType.warning

    if TYPE_CHECKING:
        user: Member

    def __init__(
        self,
        api: API,
        guild: Guild,
        *,
        channel: Optional[MessageableGuildChannel],
        moderator: Moderator,
        user: DiscordUser
    ) -> None:
        super().__init__(api, guild)
        self._channel = channel
        self._set_moderator(moderator)
        self._set_user(user)

    @property
    def public_message_issue_embed(self) -> Embed:
        embed = super().public_message_issue_embed
        embed.description = f"{self.user_name} has been warned: {self.reason}"
        return embed

    async def create_case(self) -> Case:
        await super().create_case()
        return await self._create_case_record()

    async def issue(self) -> Case:
        """Warns the member."""
        if self.expiration_date is None:
            self.set_length(timedelta(days=90))
        self.case = await self.create_case()
        self._api.client.dispatch("pidroid_warning_issue", self)
        return self.case

class Timeout(BasePunishment):

    __type__ = PunishmentType.timeout

    if TYPE_CHECKING:
        user: Member

    def __init__(
        self,
        api: API,
        guild: Guild,
        *,
        channel: Optional[MessageableGuildChannel],
        moderator: Moderator,
        user: DiscordUser
    ) -> None:
        super().__init__(api, guild)
        self._channel = channel
        self._set_moderator(moderator)
        self._set_user(user)

    @property
    def audit_log_issue_reason(self) -> str:
        reason = f"Timed out on behalf of {self.moderator_name}"
        if reason:
            reason += f" for the following reason: {self.reason}"
        else:
            reason += ", reason was not specified"
        if self.expiration_date:
            reason += f", expires in {humanize(self.expiration_date, max_units=2)}."
        return reason

    @property
    def audit_log_revoke_reason(self) -> str:
        reason = f"Time out removed on behalf of {self.moderator_name}"
        if reason:
            reason += f" for the following reason: {self.reason}"
        else:
            reason += ", reason was not specified"
        return reason

    @property
    def public_message_issue_embed(self) -> Embed:
        embed = super().public_message_issue_embed
        embed.description = f"{self.user_name} was timed out"
        if self.reason:
            embed.description += f" for the following reason: {self.reason}"
        if self.expiration_date:
            embed.description += f"\nExpires {format_dt(self.expiration_date, 'R')}."
        return embed

    @property
    def public_message_revoke_embed(self) -> Embed:
        embed = super().public_message_revoke_embed
        embed.description = f"Timeout for {self.user_name} was removed"
        return embed

    async def create_case(self) -> Case:
        await super().create_case()
        return await self._create_case_record()

    async def issue(self) -> Case:
        await self.user.timeout(self.expiration_date, reason=self.audit_log_issue_reason)
        self.case = await self.create_case()
        self._api.client.dispatch("pidroid_timeout_issue", self)
        return self.case

    async def revoke(self, *, reason: Optional[str] = None) -> None:
        self.reason = reason
        await self.user.edit(timed_out_until=None, reason=self.audit_log_revoke_reason)
        await self._expire_cases_by_type(PunishmentType.timeout)
        self._api.client.dispatch("pidroid_timeout_revoke", self)
