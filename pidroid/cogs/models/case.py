from __future__ import annotations

import datetime
import discord

from datetime import timedelta
from dateutil.relativedelta import relativedelta # type: ignore
from discord.embeds import Embed
from discord.ext.commands.context import Context # type: ignore
from discord.ext.commands.errors import BadArgument # type: ignore
from discord.file import File
from discord.guild import Guild
from discord.member import Member
from discord.role import Role
from discord.user import User
from discord.utils import format_dt
from typing import TYPE_CHECKING, List, Optional, Union

from pidroid.cogs.utils.aliases import GuildTextChannel
from pidroid.cogs.utils.embeds import PidroidEmbed, SuccessEmbed
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
        self._id = data.id
        self.case_id = data.case_id
        self.type = data.type
        self.guild_id = data.guild_id

        self.user_id = data.user_id
        self.moderator_id = data.moderator_id

        self._user_name = data.user_name
        self._moderator_name = data.moderator_name

        self.reason = data.reason
        self.date_issued = data.issue_date
        self.date_expires = data.expire_date

        self.visible = data.visible
        self.handled = data.handled

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
        self.embed.set_footer(text=f'{len(self.entries)} entry(-ies)')
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

    def __init__(self, ctx: Optional[Context] = None, user: Optional[DiscordUser] = None) -> None:
        # Only used internally, we initialize them here
        self.type = "unknown"
        self.case = None
        self._expiration_date = None
        self._reason = None

        if ctx is not None and user is not None:
            self._fill(ctx.bot.api, ctx.guild, ctx.channel, ctx.author, user)

    def _fill(self, api: API, guild: Guild, channel: Optional[GuildTextChannel], moderator: Moderator, user: DiscordUser) -> None:
        self._api = api
        self.guild = guild
        self._channel = channel

        self._set_moderator(moderator)
        self._set_user(user)

        self.send_message_to_channel = self._channel is None

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

    def set_length(self, length: Optional[Union[timedelta, relativedelta]]):
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
    def reason(self, reason: str) -> None:
        if len(reason) > 512:
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

    """Would rather stick these user notification features into an event listener of sorts."""
    async def _notify_user(self, message: str):
        try:
            await self.user.send(message)
        except Exception: # nosec
            pass

    async def _notify_chat(self, message: str, image_file: Optional[File] = None):
        if self.send_message_to_channel or self._channel is None:
            return

        embed = SuccessEmbed(message)
        if self.case:
            embed.title = f"Case #{self.case.case_id}"

        try:
            if image_file is not None:
                embed.set_image(url=f"attachment://{image_file.filename}")
                return await self._channel.send(embed=embed, file=image_file)
            await self._channel.send(embed=embed)
        except Exception: # nosec
            pass

    def _set_user(self, user: DiscordUser) -> None:
        if isinstance(user, Member):
            self.user = user._user
        self.user = user

    def _set_moderator(self, moderator: DiscordUser) -> None:
        if isinstance(moderator, Member):
            self.moderator = moderator._user
        else:
            self.moderator = moderator

    async def issue(self) -> Case:
        raise NotImplementedError

    async def revoke(self) -> None:
        raise NotImplementedError

class Mute(BasePunishment):

    if TYPE_CHECKING:
        user: Member

    def __init__(self, ctx: Optional[Context] = None, member: Optional[Member] = None) -> None:
        super().__init__(ctx, member)
        self.type = "mute"

    async def revoke(self, role: Role) -> None: # type: ignore
        await self._revoke_punishment_db_entry("mute")
        await self.user.remove_roles(role, reason=f"Unmuted by {self.moderator_name}") # type: ignore

        await self._notify_chat(f"{self.user_name} was unmuted!")
        await self._notify_user(f"You have been unmuted in {self.guild.name} server!")

class Ban(BasePunishment):

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

        await self.guild.ban(user=self.user, reason=self.reason, delete_message_days=1) # type: ignore
        return self.case

    async def revoke(self, reason: str = None) -> None:
        await self._revoke_punishment_db_entry("ban")
        await self.guild.unban(self.user, reason=reason) # type: ignore

        await self._notify_chat(f"{self.user_name} was unbanned!")
        await self._notify_user(f"You have been unbanned from {self.guild.name} server!")

class Kick(BasePunishment):

    if TYPE_CHECKING:
        user: Member

    def __init__(self, ctx: Optional[Context] = None, member: Optional[Member] = None) -> None:
        super().__init__(ctx, member)
        self.type = "kick"

    async def issue(self) -> Case:
        await self._revoke_punishment_db_entry('jail')
        await self._revoke_punishment_db_entry('mute')
        await self._revoke_punishment_db_entry('timeout')
        self.case = await self._create_db_entry()

        if self.reason is None:
            await self._notify_chat(f"{self.user_name} was kicked!")
            await self._notify_user(f"You have been kicked from {self.guild.name} server!")
        else:
            await self._notify_chat(f'{self.user_name} was kicked for the following reason: {self.reason}')
            await self._notify_user(f"You have been kicked from {self.guild.name} server for the following reason: {self.reason}")

        await self.user.kick(reason=self.reason)
        return self.case

class Jail(BasePunishment):

    if TYPE_CHECKING:
        user: Member

    def __init__(self, ctx: Optional[Context] = None, member: Optional[Member] = None, kidnapping: bool = False) -> None:
        super().__init__(ctx, member)
        self.type = "jail"
        self._kidnapping = kidnapping

    async def issue(self, role: Role) -> Case: # type: ignore
        """Jails the member."""
        self.case = await self._create_db_entry()
        await self.user.add_roles(role, reason=self.reason) # type: ignore

        if self._kidnapping:
            await self._notify_chat(f"{self.user_name} was kidnapped!", image_file=discord.File(Resource('bus.png')))
            if self.reason is None:
                await self._notify_user(f"You have been kidnapped in {self.guild.name} server!")
                return self.case
            await self._notify_user(f"You have been kidnapped in {self.guild.name} server for the following reason: {self.reason}")
            return self.case

        if self.reason is None:
            await self._notify_chat(f"{self.user_name} was jailed!")
            await self._notify_user(f"You have been jailed in {self.guild.name} server!")
        else:
            await self._notify_chat(f"{self.user_name} was jailed for the following reason: {self.reason}")
            await self._notify_user(f"You have been jailed in {self.guild.name} server for the following reason: {self.reason}")
        return self.case

    async def revoke(self, role: Role, reason: str = None) -> None: # type: ignore
        await self._revoke_punishment_db_entry("jail")
        await self.user.remove_roles(role, reason=reason) # type: ignore
        await self._notify_chat(f"{self.user_name} was unjailed!")
        await self._notify_user(f"You have been unjailed in {self.guild.name} server!")

class Warning(BasePunishment):

    if TYPE_CHECKING:
        user: Member

    def __init__(self, ctx: Optional[Context] = None, member: Optional[Member] = None) -> None:
        super().__init__(ctx, member)
        self.type = "warning"

    async def issue(self) -> Case:
        """Warns the member."""
        if self.expiration_date is None:
            self.set_length(timedelta(days=90))
        self.case = await self._create_db_entry()
        await self._notify_chat(f"{self.user_name} has been warned: {self.reason}")
        await self._notify_user(f"You have been warned in {self.guild.name} server: {self.reason}")
        return self.case

class Timeout(BasePunishment):

    if TYPE_CHECKING:
        user: Member

    def __init__(self, ctx: Optional[Context] = None, member: Optional[Member] = None) -> None:
        super().__init__(ctx, member)
        self.type = "timeout"

    async def issue(self) -> Case:
        self.case = await self._create_db_entry()
        await self.user.timeout(self.expiration_date, reason=self.reason)

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

async def create_ban(api: API, guild: Guild, channel: GuildTextChannel, moderator: Moderator, user: DiscordUser, length: Length, reason: str) -> Case:
    ban = Ban()
    ban._fill(api, guild, channel, moderator, user)
    ban.set_length(length)
    ban.reason = reason
    return await ban.issue()

async def remove_ban(api: API, guild: Guild, channel: GuildTextChannel, moderator: Moderator, user: DiscordUser, reason: str = None):
    ban = Ban()
    ban._fill(api, guild, channel, moderator, user)
    await ban.revoke(reason)

async def create_kick(api: API, guild: Guild, channel: GuildTextChannel, moderator: Moderator, user: Member, reason: str) -> Case:
    kick = Kick()
    kick._fill(api, guild, channel, moderator, user)
    kick.reason = reason
    return await kick.issue()

async def create_jail(api: API, guild: Guild, channel: GuildTextChannel, moderator: Moderator, user: Member, role: Role, reason: str) -> Case:
    jail = Jail()
    jail._fill(api, guild, channel, moderator, user)
    jail.reason = reason
    return await jail.issue(role)

async def remove_jail(api: API, guild: Guild, channel: GuildTextChannel, moderator: Moderator, user: Member, role: Role, reason: str = None):
    jail = Jail()
    jail._fill(api, guild, channel, moderator, user)
    return await jail.revoke(role, reason)

async def create_timeout(api: API, guild: Guild, channel: GuildTextChannel, moderator: Moderator, user: Member, length: Length, reason: str) -> Case:
    timeout = Timeout()
    timeout._fill(api, guild, channel, user, moderator)
    timeout.set_length(length)
    timeout.reason = reason
    return await timeout.issue()

async def remove_timeout(api: API, guild: Guild, channel: GuildTextChannel, moderator: Moderator, user: Member, reason: str = None):
    timeout = Timeout()
    timeout._fill(api, guild, channel, moderator, user)
    await timeout.revoke(reason)

async def create_warning(api: API, guild: Guild, channel: GuildTextChannel, moderator: Moderator, user: Member, reason: str) -> Case:
    warning = Warning()
    warning._fill(api, guild, channel, moderator, user)
    warning.reason = reason
    return await warning.issue()

async def create_ban_from_context(ctx: Context, user: DiscordUser, length: Length, reason: str) -> Case:
    return await create_ban(ctx.bot.api, ctx.guild, ctx.channel, ctx.author, user, length, reason)

async def create_kick_from_context(ctx: Context, user: Member, reason: str) -> Case:
    return await create_kick(ctx.bot.api, ctx.guild, ctx.channel, ctx.author, user, reason)

async def create_jail_from_context(ctx: Context, user: Member, role: Role, reason: str) -> Case:
    return await create_jail(ctx.bot.api, ctx.guild, ctx.channel, ctx.author, user, role, reason)

async def create_timeout_from_context(ctx: Context, user: Member, length: Length, reason: str) -> Case:
    return await create_timeout(ctx.bot.api, ctx.guild, ctx.channel, ctx.author, user, length, reason)

async def create_warning_from_context(ctx: Context, user: Member, reason: str) -> Case:
    return await create_warning(ctx.bot.api, ctx.guild, ctx.channel, ctx.author, user, reason)

async def remove_ban_from_context(ctx: Context, user: DiscordUser, reason: str):
    return await remove_ban(ctx.bot.api, ctx.guild, ctx.channel, ctx.author, user, reason)

async def remove_jail_from_context(ctx: Context, user: Member, role: Role, reason: str):
    return await remove_jail(ctx.bot.api, ctx.guild, ctx.channel, ctx.author, user, role, reason)

async def remove_timeout_from_context(ctx: Context, user: Member, reason: str):
    return await remove_timeout(ctx.bot.api, ctx.guild, ctx.channel, ctx.author, user, reason)
