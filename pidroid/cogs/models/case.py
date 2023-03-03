from __future__ import annotations

import datetime
import discord

from datetime import timedelta
from dateutil.relativedelta import relativedelta # type: ignore
from discord.embeds import Embed
from discord.ext.commands.errors import BadArgument # type: ignore
from discord.file import File
from discord.guild import Guild
from discord.member import Member
from discord.role import Role
from discord.user import User
from discord.utils import format_dt
from typing import TYPE_CHECKING, List, Optional, Union

from pidroid.cogs.utils.aliases import GuildTextChannel
from pidroid.cogs.utils.embeds import PidroidEmbed
from pidroid.cogs.utils.file import Resource
from pidroid.cogs.utils.paginators import ListPageSource, PidroidPages
from pidroid.cogs.utils.time import delta_to_datetime, humanize, time_since, utcnow

if TYPE_CHECKING:
    from pidroid.cogs.utils.api import API, PunishmentTable
    DiscordUser = Union[Member, User]
    Moderator = Union[Member, User]
    Length = Union[timedelta, relativedelta]

class BaseCase:

    if TYPE_CHECKING:
        _id: int
        case_id: int
        type: str
        guild_id: int

        user_id: int
        moderator_id: int

        _user_name: Optional[str]
        _moderator_name: Optional[str]

        reason: Optional[str]
        date_issued: datetime.datetime
        date_expires: Optional[datetime.datetime]

        visible: bool
        handled: bool

    def __init__(self, api: API, data: PunishmentTable) -> None:
        self._api = api
        self._deserialize(data)

    def _deserialize(self, data: PunishmentTable):
        self._id = data.id # type: ignore
        self.case_id = data.case_id # type: ignore
        self.type = data.type # type: ignore
        self.guild_id = data.guild_id # type: ignore

        self.user_id = data.user_id # type: ignore
        self.moderator_id = data.moderator_id # type: ignore

        self._user_name = data.user_name # type: ignore
        self._moderator_name = data.moderator_name # type: ignore

        self.reason = data.reason # type: ignore
        self.date_issued = data.issue_date # type: ignore
        self.date_expires = data.expire_date # type: ignore

        self.visible = data.visible # type: ignore
        self.handled = data.handled # type: ignore

    async def _update(self) -> None:
        await self._api.update_case_by_internal_id(self._id, self.reason, self.date_expires, self.visible, self.handled)

    @property
    def has_expired(self) -> bool:
        """Returns true if the punishment expired."""
        # If case expired by getting explicitly handled
        if self.handled:
            return True
        # If the date of expiration is set to none, then it never expires
        if self.date_expires is None:
            return False
        # Otherwise, if current date is above or equal to the date is should expire, then it IS expired
        return self.date_expires <= utcnow()

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
        elif self.date_expires is None:
            duration = "∞"
        else:
            duration = humanize(self.date_expires, max_units=3)

        embed.add_field(name='Duration', value=duration)
        embed.set_footer(text=f"Issued {time_since(self.date_issued, max_units=3)}")
        return embed

class Case(BaseCase):

    if TYPE_CHECKING:
        user: Optional[User]
        moderator: Optional[User]

    def __init__(self, api: API, data: PunishmentTable) -> None:
        super().__init__(api, data)

    async def _fetch_users(self) -> None:
        self.user = await self._api.client.get_or_fetch_user(self.user_id)
        self.moderator = await self._api.client.get_or_fetch_user(self.moderator_id)

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
        await self._update()

    async def invalidate(self) -> None:
        """Invalidates specified case.

        Note, this only works for warnings."""
        if self.type != "warning":
            raise BadArgument("Only warnings can be invalidated!")
        self.date_expires = utcnow()
        self.handled = True
        self.visible = False
        await self._update()


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
                value = f"\"{case.reason}\" issued on {format_dt(case.date_issued)}"
            else:
                name = f"Case #{case.case_id}: {case.type}"
                value = (
                    f"**Issued by:** {case.moderator_name}\n"
                    f"**Issued on:** {format_dt(case.date_issued)}\n"
                    f"**Reason:** {case.clean_reason.capitalize()}"
                )
            self.embed.add_field(name=name, value=value, inline=False)
        
        entry_count = len(self.entries)
        if entry_count == 1:
            self.embed.set_footer(text=f'{entry_count} entry')
        else:
            self.embed.set_footer(text=f'{entry_count:,} entries')
        return self.embed

class BasePunishment:

    if TYPE_CHECKING:
        _api: API
        type: str
        case: Optional[Case]
        _channel: Optional[GuildTextChannel]

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
        self.type = "unknown"
        self.case = None
        self._expiration_date = None
        self._reason = None

        self._api = api
        self.guild = guild

        self._appeal_url = None

    def __str__(self) -> str:
        return self.type

    @property
    def user_name(self) -> str:
        """Returns user name."""
        return str(self.user)

    @property
    def moderator_name(self) -> str:
        """Returns moderator name."""
        return str(self.moderator)

    def set_length(self, length: Optional[Union[timedelta, relativedelta, None]]):
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
        if reason and len(reason) > 512:
            raise BadArgument("Your reason is too long. Please make sure it's below or equal to 512 characters!")
        self._reason = reason

    async def _create_db_entry(self) -> Case:
        return await self._api.insert_punishment_entry(
            self.type,
            self.guild.id,
            self.user.id, self.user_name,
            self.moderator.id, self.moderator_name,
            self.reason, self.expiration_date
        )

    async def _revoke_punishment_db_entry(self, type: str) -> None:
        """Removes all punishments of specified type for the current user."""
        await self._api.revoke_cases_by_type(type, self.guild.id, self.user.id)

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
        if self.case is None:
            raise BadArgument("Case object was not retrieved")
        embed = Embed(title=f"New punishment received [case #{self.case.case_id}]", color=discord.Color.red())
        embed.add_field(name='Type', value=self.case.type.capitalize())
        embed.add_field(name="Reason", value=self.reason or "No reason specified")
        if self.case.date_expires is None:
            duration = "Never"
        else:
            duration = format_dt(self.case.date_expires)
        embed.add_field(name='Expires in', value=duration)
        if self._appeal_url:
            embed.add_field(name='You can appeal the punishment here:', value=self._appeal_url)
        embed.set_footer(text=f'Guild: {self.guild.name} ({self.guild.id})')
        return embed

    @property
    def private_message_revoke_embed(self) -> Embed:
        embed = Embed(title=f"Punishment revoked", color=discord.Color.green())
        embed.add_field(name='Type', value=self.type.capitalize())
        embed.add_field(name='Reason', value=self.reason or "No reason specified")
        embed.set_footer(text=f'Guild: {self.guild.name} ({self.guild.id})')
        return embed

    async def create_entry(self):
        config = await self._api.client.fetch_guild_configuration(self.guild.id)
        self._appeal_url = config.appeal_url

    async def issue(self) -> Case:
        raise NotImplementedError

    async def revoke_entry(self) -> None:
        raise NotImplementedError

    async def revoke(self) -> None:
        raise NotImplementedError

class Ban(BasePunishment):

    if TYPE_CHECKING:
        user: DiscordUser

    def __init__(
        self,
        api: API,
        guild: Guild, channel: Optional[GuildTextChannel],
        moderator: Moderator, user: DiscordUser
    ) -> None:
        super().__init__(api, guild)
        self.type = "ban"
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

    async def create_entry(self) -> Case:
        """Creates new database entry for the case."""
        await super().create_entry()
        await self._revoke_punishment_db_entry("jail")
        await self._revoke_punishment_db_entry("mute")
        await self._revoke_punishment_db_entry("timeout")
        return await self._create_db_entry()

    async def issue(self) -> Case:
        """Bans the user and creates new database entry."""
        await self.guild.ban(user=self.user, reason=self.audit_log_issue_reason, delete_message_days=1) # type: ignore
        self.case = await self.create_entry()
        self._api.emit("on_ban_issued", self)
        return self.case

    async def revoke_entry(self) -> None:
        """Revokes ban in the database."""
        await self._revoke_punishment_db_entry("ban")

    async def revoke(self, reason: Optional[str] = None) -> None:
        """Unbans the user and updates database entry."""
        self.reason = reason
        await self.guild.unban(self.user, reason=self.audit_log_revoke_reason) # type: ignore
        await self.revoke_entry()
        self._api.emit("on_ban_revoked", self)

class Kick(BasePunishment):

    if TYPE_CHECKING:
        user: Member
        
    def __init__(
        self,
        api: API,
        guild: Guild, channel: Optional[GuildTextChannel],
        moderator: Moderator, user: DiscordUser
    ) -> None:
        super().__init__(api, guild)
        self.type = "kick"
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

    async def create_entry(self) -> Case:
        await super().create_entry()
        await self._revoke_punishment_db_entry('jail')
        await self._revoke_punishment_db_entry('mute')
        await self._revoke_punishment_db_entry('timeout')
        return await self._create_db_entry()

    async def issue(self) -> Case:
        await self.user.kick(reason=self.audit_log_issue_reason)
        self.case = await self.create_entry()
        self._api.emit("on_kick_issued", self)
        return self.case

class Jail(BasePunishment):

    if TYPE_CHECKING:
        user: Member

    def __init__(
        self,
        api: API,
        guild: Guild, channel: Optional[GuildTextChannel],
        moderator: Moderator, user: DiscordUser,
        kidnapping: bool = False
    ) -> None:
        super().__init__(api, guild)
        self.type = "jail"
        self._kidnapping = kidnapping
        self._channel = channel
        self._set_moderator(moderator)
        self._set_user(user)

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
        if self._kidnapping:
            embed.description = f"{self.user_name} was kidnapped"
            embed.set_image(url=f"attachment://bus.png")
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
        return self._kidnapping

    async def create_entry(self) -> Case:
        await super().create_entry()
        return await self._create_db_entry()

    async def issue(self, role: Role) -> Case: # type: ignore
        """Jails the member."""
        await self.user.add_roles(role, reason=self.audit_log_issue_reason) # type: ignore
        self.case = await self.create_entry()
        self._api.emit("on_jail_issued", self)
        return self.case

    async def revoke_entry(self) -> None:
        await self._revoke_punishment_db_entry("jail")

    async def revoke(self, role: Role, reason: Optional[str] = None) -> None: # type: ignore
        self.reason = reason
        await self.user.remove_roles(role, reason=self.audit_log_revoke_reason) # type: ignore
        await self.revoke_entry()
        self._api.emit("on_jail_revoked", self)

class Warning(BasePunishment):

    if TYPE_CHECKING:
        user: Member

    def __init__(
        self,
        api: API,
        guild: Guild, channel: Optional[GuildTextChannel],
        moderator: Moderator, user: DiscordUser
    ) -> None:
        super().__init__(api, guild)
        self.type = "warning"
        self._channel = channel
        self._set_moderator(moderator)
        self._set_user(user)

    @property
    def public_message_issue_embed(self) -> Embed:
        embed = super().public_message_issue_embed
        embed.description = f"{self.user_name} has been warned: {self.reason}"
        return embed

    async def create_entry(self) -> Case:
        await super().create_entry()
        return await self._create_db_entry()

    async def issue(self) -> Case:
        """Warns the member."""
        if self.expiration_date is None:
            self.set_length(timedelta(days=90))
        self.case = await self.create_entry()
        self._api.emit("on_warning_issued", self)
        return self.case

class Timeout(BasePunishment):

    if TYPE_CHECKING:
        user: Member

    def __init__(
        self,
        api: API,
        guild: Guild, channel: Optional[GuildTextChannel],
        moderator: Moderator, user: DiscordUser
    ) -> None:
        super().__init__(api, guild)
        self.type = "timeout"
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

    async def create_entry(self) -> Case:
        await super().create_entry()
        return await self._create_db_entry()

    async def issue(self) -> Case:
        await self.user.timeout(self.expiration_date, reason=self.audit_log_issue_reason)
        self.case = await self.create_entry()
        self._api.emit("on_timeout_issued", self)
        return self.case

    async def revoke_entry(self) -> None:
        await self._revoke_punishment_db_entry("timeout")

    async def revoke(self, reason: Optional[str] = None) -> None:
        self.reason = reason
        await self.user.edit(timed_out_until=None, reason=self.audit_log_revoke_reason)
        await self.revoke_entry()
        self._api.emit("on_timeout_revoked", self)
