from __future__ import annotations

import datetime
import discord
import enum

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import timedelta
from discord import Embed, File, Guild, Member, Role
from discord.ext.commands import Context
from discord.utils import format_dt
from typing import TYPE_CHECKING, Callable, Literal, override

from pidroid.utils import try_message_user
from pidroid.utils.file import Resource
from pidroid.utils.time import delta_to_datetime, humanize
from pidroid.utils.types import DiscordUser
from pidroid.utils.checks import (
    is_junior_moderator, is_normal_moderator, is_senior_moderator, member_has_guild_permission
)

DateExpire = datetime.datetime | None
Reason = str | None

if TYPE_CHECKING:
    from pidroid.client import Pidroid
    from pidroid.modules.moderation.models.case import Case
    from pidroid.utils.api import API

class PunishmentMode(enum.Enum):
    """Enum representing the mode of the punishment."""
    ISSUE = "issue"
    REVOKE = "revoke"

@dataclass
class PunishmentOptions:
    # Function that returns whether the current user can issue this punishment type based on the context.
    check_issue: Callable[[Context[Pidroid]], bool]
    # Function that returns whether the current user can revoke this punishment type based on the context.
    # Defaults to False, meaning that the punishment type cannot be revoked by the current user.
    check_revoke: Callable[[Context[Pidroid]], bool] = lambda _: False

    # Whether this punishment type can be to a moderator by a moderator.
    can_be_issued_on_moderator: bool = False
    # Whether this punishment type supports moderator-provided expiration.
    supports_expiration: bool = False
    # Whether this punishment type supports deleting messages from the user.
    supports_messages_deletion: bool = False


class PunishmentType2(enum.Enum):
    BAN = "ban"
    KICK = "kick"
    JAIL = "jail"
    TIMEOUT = "timeout"
    WARNING = "warning"
    MUTE = "mute"  # Backwards compatibility

    def can_be_issued(self, ctx: Context[Pidroid]) -> bool:
        """Checks if the current user can issue this punishment type."""
        return self.options.check_issue(ctx)
    
    def can_be_revoked(self, ctx: Context[Pidroid]) -> bool:
        """Checks if the current user can revoke this punishment type."""
        return self.options.check_revoke(ctx)

    @property
    def options(self) -> PunishmentOptions:
        opt = PUNISHMENT_ACTIONS.get(self, None)
        if opt is None:
            raise NotImplementedError(f"Punishment options for {self} are not implemented, shouldn't happen.")
        return opt
    
    @property
    def reasons(self) -> list[tuple[str, str]]:
        """Returns the default reasons for this punishment type."""
        reasons = DEFAULT_PUNISHMENT_REASONS.get(self, None)
        if reasons is None:
            raise NotImplementedError(f"Default reasons for {self} are not implemented, shouldn't happen.")
        return reasons
    
    @property
    def lengths(self) -> list[tuple[str, timedelta | Literal[-1]]]:
        """Returns the default lengths for this punishment type."""
        lengths = DEFAULT_PUNISHMENT_LENGTHS.get(self, None)
        if lengths is None:
            raise NotImplementedError(f"Default lengths for {self} are not implemented, shouldn't happen.")
        return lengths
    
    @property
    def object_constructor(self) -> type[BasePunishment]:
        """Returns the constructor for this punishment type."""
        constructor = PUNISHMENT_CONSTRUCTORS.get(self, None)
        if constructor is None:
            raise NotImplementedError(f"Constructor for {self} is not implemented, shouldn't happen.")
        return constructor
    

PUNISHMENT_ACTIONS: dict[PunishmentType2, PunishmentOptions] = {
    PunishmentType2.BAN: PunishmentOptions(
        check_issue=lambda ctx: is_normal_moderator(ctx, ban_members=True) and member_has_guild_permission(ctx.me, "ban_members"), # pyright: ignore[reportArgumentType]
        check_revoke=lambda ctx: is_senior_moderator(ctx, ban_members=True) and member_has_guild_permission(ctx.me, "ban_members"), # pyright: ignore[reportArgumentType]
        supports_expiration=True, supports_messages_deletion=True
    ),
    PunishmentType2.KICK: PunishmentOptions(
        check_issue=lambda ctx: is_junior_moderator(ctx, kick_members=True) and member_has_guild_permission(ctx.me, "kick_members"), # pyright: ignore[reportArgumentType]
    ),
    PunishmentType2.JAIL: PunishmentOptions(
        check_issue=lambda ctx: member_has_guild_permission(ctx.me, "manage_roles"), # pyright: ignore[reportArgumentType]
        check_revoke=lambda ctx: member_has_guild_permission(ctx.me, "manage_roles"), # pyright: ignore[reportArgumentType]
    ),
    PunishmentType2.TIMEOUT: PunishmentOptions(
        check_issue=lambda ctx: is_junior_moderator(ctx, moderate_members=True) and member_has_guild_permission(ctx.me, "moderate_members"), # pyright: ignore[reportArgumentType]
        check_revoke=lambda ctx: is_junior_moderator(ctx, moderate_members=True) and member_has_guild_permission(ctx.me, "moderate_members"), # pyright: ignore[reportArgumentType]
        supports_expiration=True
    ),
    PunishmentType2.WARNING: PunishmentOptions(
        check_issue=lambda _: True, # Any moderator can warn
    ),
}

# Default reasons for punishments. Tuples are (name, description).
DEFAULT_PUNISHMENT_REASONS: dict[PunishmentType2, list[tuple[str, str]]] = {
    PunishmentType2.BAN: [
        ("Ignoring moderator's orders", "Ignoring moderator's orders."),
        ("Hacked content", "Sharing, spreading or using hacked content."),
        ("Offensive content or hate-speech", "Posting or spreading offensive content or hate-speech."),
        ("Harassing other members", "Harassing other members."),
        ("Scam or phishing", "Sharing or spreading scams or phishing content."),
        ("Continued or repeat offences", "Continued or repeat offences."),
        ("Spam", "Spam."),
        ("Alternative account", "Alternative accounts are not allowed."),
        ("Underage user", "You are under the allowed age as defined in Discord's Terms of Service."),
    ],
    PunishmentType2.KICK: [
        ("Spam", "Spam."),
        ("Alternative account", "Alternative accounts are not allowed."),
        (
            "Underage",
            "You are under the allowed age as defined in Discord's Terms of Service. Please rejoin when you're older."
        ),
    ],
    PunishmentType2.JAIL: [],
    PunishmentType2.TIMEOUT: [
        ("Being emotional or upset", "Being emotional or upset."),
        ("Spam", "Spam."),
        ("Disrupting the chat", "Disrupting the chat."),
    ],
    PunishmentType2.WARNING: [
        ("Spam", "Spam."),
        ("Failure to follow orders", "Failure to follow orders."),
        ("Failure to comply with verbal warning", "Failure to comply with a verbal warning."),
        ("Hateful content", "Sharing or spreading hateful content."),
        ("Repeat use of wrong channels", "Repeat use of wrong channels."),
        ("NSFW content", "Sharing or spreading NSFW content."),
        ("Politics", "Politics or political content."),
    ]
}

# Default length of punishments. Tuples are (name, length). -1 means permanent.
DEFAULT_PUNISHMENT_LENGTHS: dict[PunishmentType2, list[tuple[str, timedelta | Literal[-1]]]] = {
    PunishmentType2.TIMEOUT: [
        ("30 minutes", timedelta(minutes=30)),
        ("An hour", timedelta(hours=1)),
        ("2 hours", timedelta(hours=2)),
        ("12 hours", timedelta(hours=12)),
        ("A day", timedelta(hours=24)),
        ("A week", timedelta(weeks=1)),
        ("4 weeks (max)", timedelta(weeks=4)),
    ],
    PunishmentType2.BAN: [
        ("24 hours", timedelta(hours=24)),
        ("A week", timedelta(weeks=1)),
        ("2 weeks", timedelta(weeks=2)),
        ("A month", timedelta(days=30)),
        ("Permanent", -1),
    ]
}


def format_dm_embed(
    guild: Guild,
    punishment_type: PunishmentType2,
    reason: Reason,
) -> Embed:
    """Creates an embed for the punishment revoke DM."""
    embed = Embed()
    embed.add_field(name="Type", value=punishment_type.value.capitalize())
    embed.add_field(name="Reason", value=reason or "No reason specified")
    embed.set_footer(text=f"Server: {guild.name} ({guild.id})")
    return embed

def format_dm_revoke_embed(
    guild: Guild,
    punishment_type: PunishmentType2,
    reason: Reason
) -> Embed:
    """Creates an embed for the punishment revocation private message."""
    embed = format_dm_embed(guild, punishment_type, reason)
    embed.color = discord.Color.green()
    embed.title = "Punishment Revoked"
    return embed

def format_audit_log_reason(action: str, moderator_name: str, reason: Reason, date_expire: DateExpire) -> str:
    formatted = f"{action} on behalf of {moderator_name}" 
    if reason:
        formatted += f" for the following reason: {reason}"
    else:
        formatted += ", reason was not specified"
    if date_expire:
        formatted += f", expires in {humanize(date_expire, max_units=2)}."
    return formatted

class IssueablePunishment(ABC):
    """An interface for punishments that can be issued."""

    @property
    @abstractmethod
    def public_issue_message(self) -> str:
        """Returns the message to be sent in public channels when the punishment is issued."""
        pass

    @property
    @abstractmethod
    def public_issue_file(self) -> File | None:
        """Returns the file to be sent in public channels when the punishment is issued."""
        pass

    @property
    @abstractmethod
    def private_issue_embed(self) -> Embed:
        """Returns the embed to be sent to user when the punishment is issued."""
        pass


    @abstractmethod
    async def issue(self) -> Case:
        """Issues the punishment for the user."""
        pass

class RevokeablePunishment(ABC):
    """An interface for punishments that can be revoked."""

    @property
    @abstractmethod
    def public_revoke_message(self) -> str:
        """Returns the message to be sent in public channels when the punishment is revoked."""
        pass

    @property
    @abstractmethod
    def private_revoke_embed(self) -> Embed:
        """Returns the embed to be sent to user when the punishment is revoked."""
        pass

    @abstractmethod
    async def revoke(self) -> None:
        """Revokes the punishment from the user."""
        pass

class ExpiringPunishment(ABC):
    """An interface for punishments that can expire."""

class BasePunishment(IssueablePunishment, ABC):
    
    def __init__(
        self,
        api: API,
        *,
        guild: Guild,
        target: DiscordUser,
        moderator: DiscordUser,
        reason: str | None = None,
    ) -> None:
        super().__init__()
        self._api: API = api
        self._guild: Guild = guild
        self._target: DiscordUser = target
        self._moderator: DiscordUser = moderator
        self._reason: str | None = reason

    @property
    def target_name(self) -> str:
        """Returns the name of the user being punished."""
        return str(self._target)
    
    @property
    def moderator_name(self) -> str:
        """Returns the name of the moderator issuing the punishment."""
        return str(self._moderator)

    @property
    @abstractmethod
    def punishment_type(self) -> PunishmentType2:
        """Returns the type of the punishment."""
        pass

    @property
    @override
    def public_issue_file(self) -> File | None:
        return None # by default, no file is sent with the punishment issue message

    @property
    @override
    def private_issue_embed(self) -> Embed:
        embed = format_dm_embed(self._guild, self.punishment_type, self._reason)
        embed.color = discord.Color.red()
        embed.title = "Punishment Received"
        return embed

    async def _expire_cases_by_type(self, type: PunishmentType2) -> None:
        """Removes all punishments of specified type for the current user."""
        await self._api.expire_cases_by_type(type, self._guild.id, self._target.id)

    async def _create_case_record(self) -> Case:
        """Creates a case record in the database."""
        return await self._api.insert_punishment_entry(
            self.punishment_type.value,
            self._guild.id,
            self._target.id, self.target_name,
            self._moderator.id, self.moderator_name,
            self._reason, None
        )
    
    async def _register_case(self) -> Case:
        """Registers the case in the API."""
        return await self._create_case_record()


class Kick2(BasePunishment):

    def __init__(
        self,
        api: API,
        *,
        guild: Guild,
        target: Member,
        moderator: DiscordUser,
        reason: str | None = None,
    ) -> None:
        super().__init__(api, guild=guild, target=target, moderator=moderator, reason=reason)

    @property
    @override
    def punishment_type(self) -> PunishmentType2:
        """Returns the type of the punishment."""
        return PunishmentType2.KICK

    @property
    def audit_log_issue_reason(self) -> str:
        return format_audit_log_reason(
            "Kicked",
            self.moderator_name,
            self._reason,
            None
        )

    @property
    @override
    def public_issue_message(self) -> str:
        msg = f"{self.target_name} was kicked"
        if self._reason:
            msg += f" for the following reason: {self._reason}"
        return msg
    
    @override
    async def _register_case(self) -> Case:
        # When we ban the user, we will remove their jail, mute punishments
        await self._expire_cases_by_type(PunishmentType2.JAIL)
        await self._expire_cases_by_type(PunishmentType2.MUTE)
        return await self._create_case_record()

    @override
    async def issue(self) -> Case:
        """Issues the kick punishment."""
        message = await try_message_user(self._target, embed=self.private_issue_embed)
        try:
            assert isinstance(self._target, Member), "Target must be a Member instance"
            await self._target.kick(reason=self.audit_log_issue_reason)
        except Exception as e:
            if message:
                await message.delete()
            raise e
        case = await self._register_case()
        self._api.client.dispatch("pidroid_kick_issue", self)
        return case

class Warning2(BasePunishment, ExpiringPunishment):

    def __init__(
        self,
        api: API,
        *,
        guild: Guild,
        target: Member,
        moderator: DiscordUser,
        reason: str | None = None,
        date_expire: DateExpire | None = None
    ) -> None:
        super().__init__(api, guild=guild, target=target, moderator=moderator, reason=reason)
        if date_expire is None:
            date_expire = delta_to_datetime(timedelta(days=90))
        self._date_expire: DateExpire | None = date_expire

    @property
    @override
    def punishment_type(self) -> PunishmentType2:
        return PunishmentType2.WARNING

    @property
    @override
    def public_issue_message(self) -> str:
        return f"{self.target_name} has been warned: {self._reason}"

    @override
    async def _create_case_record(self) -> Case:
        return await self._api.insert_punishment_entry(
            self.punishment_type.value,
            self._guild.id,
            self._target.id, self.target_name,
            self._moderator.id, self.moderator_name,
            self._reason, self._date_expire
        )

    @override
    async def issue(self) -> Case:
        case = await self._register_case()
        await try_message_user(
            self._target, embed=self.private_issue_embed
        )
        return case

class Ban2(BasePunishment, ExpiringPunishment, RevokeablePunishment):

    def __init__(
        self,
        api: API,
        *,
        guild: Guild,
        target: DiscordUser,
        moderator: DiscordUser,
        reason: str | None = None,
        date_expire: DateExpire | None = None
    ) -> None:
        super().__init__(api, guild=guild, target=target, moderator=moderator, reason=reason)
        self._date_expire: DateExpire | None = date_expire
        self._appeal_url: str | None = None

    @property
    @override
    def punishment_type(self) -> PunishmentType2:
        return PunishmentType2.BAN
    
    @property
    def audit_log_issue_reason(self) -> str:
        return format_audit_log_reason(
            "Banned",
            self.moderator_name,
            self._reason,
            self._date_expire
        )
    
    @property
    def audit_log_revoke_reason(self) -> str:
        return format_audit_log_reason(
            "Unbanned",
            self.moderator_name,
            self._reason,
            self._date_expire
        )

    @property
    @override
    def public_issue_message(self) -> str:
        msg = f"{self.target_name} was banned"
        if self._reason:
            msg += f" for the following reason: {self._reason}"
        if self._date_expire:
            msg += f"\nExpires {format_dt(self._date_expire, style='R')}."
        return msg
    
    @property
    @override
    def private_issue_embed(self) -> Embed:
        embed = super().private_issue_embed
        embed.add_field(
            name="Expires at",
            value=format_dt(self._date_expire) if self._date_expire else "Never"
        )
        if self._appeal_url:
            embed.add_field(
                name="You can appeal the punishment here:",
                value=self._appeal_url
            )
        return embed

    @property
    @override
    def private_revoke_embed(self) -> Embed:
        return format_dm_revoke_embed(
            self._guild, self.punishment_type, self._reason
        )

    @property
    @override
    def public_revoke_message(self) -> str:
        msg = f"{self.target_name} was unbanned"
        if self._reason:
            msg += f" for the following reason: {self._reason}"
        return msg

    @override
    async def _create_case_record(self):
        return await self._api.insert_punishment_entry(
            self.punishment_type.value,
            self._guild.id,
            self._target.id, self.target_name,
            self._moderator.id, self.moderator_name,
            self._reason, self._date_expire
        )

    @override
    async def _register_case(self):
        # When we ban the user, we will remove their jail, mute punishments
        await self._expire_cases_by_type(PunishmentType2.JAIL)
        await self._expire_cases_by_type(PunishmentType2.MUTE)
        # Actually, Discord persists timeouts during bans
        return await self._create_case_record()

    @override
    async def issue(self) -> Case:
        conf = await self._api.fetch_guild_configuration(self._guild.id)
        if conf:
            self._appeal_url = conf.appeal_url
        message = await try_message_user(self._target, embed=self.private_issue_embed)
        try:
            await self._guild.ban(user=self._target, reason=self.audit_log_issue_reason, delete_message_days=1)
        except Exception as e:
            if message:
                await message.delete()
            raise e
        case = await self._register_case()
        return case

    @override
    async def revoke(self) -> None:
        await self._guild.unban(self._target, reason=self.audit_log_revoke_reason)
        await self._expire_cases_by_type(PunishmentType2.BAN)
        await try_message_user(self._target, embed=self.private_revoke_embed)

class Jail2(BasePunishment, RevokeablePunishment):

    def __init__(
        self,
        api: API,
        *,
        guild: Guild,
        target: Member,
        moderator: DiscordUser,
        reason: str | None = None,
        jail_role: Role,
        is_kidnapping: bool = False
    ) -> None:
        super().__init__(api, guild=guild, target=target, moderator=moderator, reason=reason)
        self._jail_role: Role = jail_role
        self._is_kidnapping: bool = is_kidnapping

    @property
    @override
    def punishment_type(self) -> PunishmentType2:
        return PunishmentType2.JAIL

    @property
    def audit_log_issue_reason(self) -> str:
        return format_audit_log_reason(
            "Jailed",
            self.moderator_name,
            self._reason,
            None
        )

    @property
    def audit_log_revoke_reason(self) -> str:
        return format_audit_log_reason(
            "Released from jail",
            self.moderator_name,
            self._reason,
            None
        )

    @property
    @override
    def public_issue_message(self) -> str:
        msg = ""
        if self._is_kidnapping:
            msg = f"{self.target_name} was kidnapped"
        else:
            msg = f"{self.target_name} was jailed"
        if self._reason:
            msg += f" for the following reason: {self._reason}"
        return msg

    @property
    @override
    def public_issue_file(self) -> File:
        return File(Resource('bus.png'))

    @property
    @override
    def public_revoke_message(self) -> str:
        msg = f"{self.target_name} was released from jail"
        if self._reason:
            msg += f" for the following reason: {self._reason}"
        return msg

    @property
    @override
    def private_revoke_embed(self) -> Embed:
        return format_dm_revoke_embed(
            self._guild, self.punishment_type, self._reason
        )

    @override
    async def issue(self) -> Case:
        """Jails the member."""
        assert isinstance(self._target, Member), "Target must be a Member instance"
        await self._target.add_roles(self._jail_role, reason=self.audit_log_issue_reason)
        case = await self._register_case()
        await try_message_user(
            self._target, embed=self.private_issue_embed
        )
        return case

    @override
    async def revoke(self):
        assert isinstance(self._target, Member), "Target must be a Member instance"
        await self._target.remove_roles(self._jail_role, reason=self.audit_log_revoke_reason)
        await self._expire_cases_by_type(PunishmentType2.JAIL)
        await try_message_user(
            self._target, embed=self.private_revoke_embed
        )

class Timeout2(BasePunishment, ExpiringPunishment, RevokeablePunishment):

    def __init__(
        self,
        api: API,
        *,
        guild: Guild,
        target: Member,
        moderator: DiscordUser,
        reason: str | None = None,
        date_expire: DateExpire,
    ) -> None:
        super().__init__(api, guild=guild, target=target, moderator=moderator, reason=reason)
        self._date_expire: DateExpire = date_expire

    @property
    @override
    def punishment_type(self) -> PunishmentType2:
        return PunishmentType2.TIMEOUT
    
    @property
    def audit_log_issue_reason(self) -> str:
        return format_audit_log_reason(
            "Timed out",
            self.moderator_name,
            self._reason,
            self._date_expire
        )
    
    @property
    def audit_log_revoke_reason(self) -> str:
        return format_audit_log_reason(
            "Timeout removed",
            self.moderator_name,
            self._reason,
            None
        )
    
    @property
    @override
    def public_issue_message(self) -> str:
        msg = f"{self.target_name} was timed out"
        if self._reason:
            msg += f" for the following reason: {self._reason}"
        if self._date_expire:
            msg += f"\nExpires {format_dt(self._date_expire, style='R')}."
        return msg
    
    @property
    @override
    def public_revoke_message(self) -> str:
        msg = f"Timeout for {self.target_name} was removed"
        if self._reason:
            msg += f" for the following reason: {self._reason}"
        return msg
    
    @property
    @override
    def private_issue_embed(self) -> Embed:
        embed = super().private_issue_embed
        embed.add_field(
            name="Expires at",
            value=format_dt(self._date_expire) if self._date_expire else "Never"
        )
        return embed
    
    @property
    @override
    def private_revoke_embed(self) -> Embed:
        return format_dm_revoke_embed(
            self._guild, self.punishment_type, self._reason
        )

    @override
    async def _create_case_record(self) -> Case:
        return await self._api.insert_punishment_entry(
            self.punishment_type.value,
            self._guild.id,
            self._target.id, self.target_name,
            self._moderator.id, self.moderator_name,
            self._reason, self._date_expire
        )

    @override
    async def issue(self) -> Case:
        assert isinstance(self._target, Member), "Target must be a Member instance"
        await self._target.timeout(self._date_expire, reason=self.audit_log_issue_reason)
        case = await self._register_case()
        await try_message_user(
            self._target, embed=self.private_issue_embed
        )
        return case

    @override
    async def revoke(self) -> None:
        assert isinstance(self._target, Member), "Target must be a Member instance"
        await self._target.edit(timed_out_until=None, reason=self.audit_log_revoke_reason)
        await self._expire_cases_by_type(PunishmentType2.TIMEOUT)
        await try_message_user(
            self._target, embed=self.private_revoke_embed
        )

PUNISHMENT_CONSTRUCTORS: dict[PunishmentType2, type[BasePunishment]] = {
    PunishmentType2.BAN: Ban2,
    PunishmentType2.KICK: Kick2,
    PunishmentType2.JAIL: Jail2,
    PunishmentType2.TIMEOUT: Timeout2,
    PunishmentType2.WARNING: Warning2,
}