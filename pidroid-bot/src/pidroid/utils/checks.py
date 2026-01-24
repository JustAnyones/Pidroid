from __future__ import annotations
import enum

from discord import Member, NotFound, Permissions, User, Guild, GroupChannel
from discord.ext.commands import BotMissingPermissions, MissingPermissions, Context
from discord.flags import flag_value, BaseFlags, flag_value, fill_with_flags, alias_flag_value
from discord.utils import get
from typing import TYPE_CHECKING, Self

from pidroid.constants import THEOTOWN_DEVELOPERS, THEOTOWN_GUILD, PIDROID_ID, TT_MODERATOR_CHAT_ROLE_ID
from pidroid.models.exceptions import MissingUserPermissions
from pidroid.utils.aliases import DiscordUser, GuildChannel

if TYPE_CHECKING:
    from pidroid.client import Pidroid

@fill_with_flags()
class Capabilities(BaseFlags):
    
    def __init__(self, permissions: int = 0):
        if not isinstance(permissions, int):
            raise TypeError(f'Expected int parameter, received {permissions.__class__.__name__} instead.')

        self.value: int = permissions
        for key, kwvalue in kwargs.items():
            try:
                flag = self.VALID_FLAGS[key]
            except KeyError:
                raise TypeError(f'{key!r} is not a valid permission name.') from None
            else:
                self._set_flag(flag, kwvalue)  # type: ignore # TypedDict annoyance where kwvalue is an object instead of bool

    @classmethod
    def none(cls) -> Self:
        return cls(0)

    @classmethod
    def developer(cls) -> Self:
        return cls(0b1_11111)

    @classmethod
    def admin(cls) -> Self:
        return cls(0b0_11111)

    @flag_value
    def access_developer_commands(self) -> int:
        """Permission to access developer commands."""
        return 1 << 0

    @flag_value
    def ban(self) -> int:
        """Permission to ban members."""
        return 1 << 1
    
    @flag_value
    def kick(self) -> int:
        """Permission to kick members."""
        return 1 << 2
    
    @flag_value
    def timeout(self) -> int:
        """Permission to timeout members."""
        return 1 << 3
    
    @flag_value
    def warn(self) -> int:
        """Permission to warn members."""
        return 1 << 4
    
    @flag_value
    def manage_tags(self) -> int:
        """Permission to manage tags."""
        return 1 << 5
    
    @flag_value
    def unban(self) -> int:
        """Permission to unban members."""
        return 1 << 6
    
    @flag_value
    def jail(self) -> int:
        """Permission to jail members."""
        return 1 << 7

capabilities_to_permissions_map: dict[Capabilities, str] = {
    Capabilities.ban: 'ban_members',
    Capabilities.kick: 'kick_members',
    Capabilities.timeout: 'moderate_members',
    Capabilities.warn: 'moderate_members',
    Capabilities.manage_tags: 'manage_messages',
    Capabilities.unban: 'ban_members',
    Capabilities.jail: 'manage_roles',
}

class ModCapability(enum.Enum):
    """These are member capabilities used for checking."""


    DEVELOPER = 'developer'
    ADMINISTRATOR = 'administrator'
    SENIOR_MODERATOR = 'senior_moderator'
    NORMAL_MODERATOR = 'normal_moderator'
    JUNIOR_MODERATOR = 'junior_moderator'
    FOREIGN_CHAT_MODERATOR = 'foreign_chat_moderator'

def capabilities_from_permissions(permissions: Permissions) -> Capabilities:
    """Returns a Capabilities object from the specified permissions integer."""
    caps = Capabilities.none()
    return caps

def get_theotown_member_capabilities(member: Member) -> Capabilities:
    """Returns a set of member capabilities for the specified member."""
    # Developers have all capabilities
    if TheoTownChecks.is_developer(member):
        return Capabilities.developer()
    # Administrators have all capabilities except developer
    if TheoTownChecks.is_administrator_or_higher(member):
        return Capabilities.admin()
    
    # As for moderators, we need to build the capabilities bit by bit
    cap = Capabilities.none()

    # Foreign chat and junior moderators start out with ability to warn and timeout
    if TheoTownChecks.is_foreign_chat_moderator_or_higher(member):
        cap.warn = True
        cap.timeout = True
        cap.jail = True

    # Junior moderators get kick and manage tags ability
    if TheoTownChecks.is_junior_moderator_or_higher(member):
        cap.kick = True
        cap.manage_tags = True

    # Regular moderators get ban ability
    if TheoTownChecks.is_normal_moderator_or_higher(member):
        cap.ban = True

    # Senior moderators get unban ability
    if TheoTownChecks.is_senior_moderator_or_higher(member):
        cap.unban = True
    return cap

def get_member_capabilities(member: Member) -> set[ModCapability]:
    """Returns a set of member capabilities for the specified member."""
    capabilities: set[ModCapability] = set()

    if member.guild.id != THEOTOWN_GUILD:
        return capabilities

    cap: Capabilities = Capabilities.none()

    if TheoTownChecks.is_developer(member):
        cap = Capabilities.developer()
        capabilities.add(ModCapability.DEVELOPER)
    if TheoTownChecks.is_administrator_or_higher(member):
        cap = Capabilities.admin()
        capabilities.add(ModCapability.ADMINISTRATOR)
    if TheoTownChecks.is_senior_moderator_or_higher(member):
        capabilities.add(ModCapability.SENIOR_MODERATOR)
    if TheoTownChecks.is_normal_moderator_or_higher(member):
        capabilities.add(ModCapability.NORMAL_MODERATOR)
    if TheoTownChecks.is_junior_moderator_or_higher(member):
        capabilities.add(ModCapability.JUNIOR_MODERATOR)
    if TheoTownChecks.is_foreign_chat_moderator_or_higher(member):
        capabilities.add(ModCapability.FOREIGN_CHAT_MODERATOR)

    return capabilities

"""These are helper utilities to be used only within this scope."""

def _member_has_role(member: Member, role_id: int) -> bool:
    """Returns true if member has the specified role by ID."""
    return get(member.guild.roles, id=role_id) in member.roles

def member_has_guild_permission(member: Member, permission: str | flag_value) -> bool:
    """Returns true if member has the specified guild permission.
    
    This only takes into consideration the guild permissions and
    not most of the implied permissions or any of the channel permission overwrites.
    For 100% accurate permission calculation, please use member_has_channel_permission.

    This does take into consideration guild ownership,
    the administrator implication, and whether the member is timed out."""
    permissions = member.guild_permissions
    if isinstance(permission, flag_value):
        return permissions.value & permission.flag != 0
    value = getattr(permissions, permission) # pyright: ignore[reportAny]
    assert isinstance(value, bool)
    return value

def member_has_channel_permission(channel: GuildChannel, member: Member, permission: str | flag_value) -> bool:
    """Returns true if member has the specified channel permission.
    
    This function takes into consideration the following cases:

    - Guild owner
    - Guild roles
    - Channel overrides
    - Member overrides
    - Member timeout"""
    permissions = channel.permissions_for(member)
    if isinstance(permission, flag_value):
        return permissions.value & permission.flag != 0
    value = getattr(permissions, permission) # pyright: ignore[reportAny]
    assert isinstance(value, bool)
    return value



def assert_guild_permissions(ctx: Context[Pidroid], **perms: bool):
    """Checks message author permissions for the guild.
    
    This only takes into consideration the guild permissions and
    not most of the implied permissions or any of the channel permission overwrites.
    For 100% accurate permission calculation, please use member_has_channel_permission.

    This does take into consideration guild ownership,
    the administrator implication, and whether the member is timed out.
    """
    assert isinstance(ctx.author, Member)

    permissions = ctx.author.guild_permissions

    missing = [perm for perm, value in perms.items() if getattr(permissions, perm) != value]

    if missing:
        raise MissingPermissions(missing)
    return

def assert_channel_permissions(ctx: Context[Pidroid], **perms: bool):
    """Checks message author permissions for the channel.
    
    This function takes into consideration the following cases:

    - Guild owner
    - Guild roles
    - Channel overrides
    - Member overrides
    - Member timeout"""
    assert isinstance(ctx.author, Member)
    assert not isinstance(ctx.channel, (GroupChannel))

    permissions = ctx.channel.permissions_for(ctx.author)

    missing = [perm for perm, value in perms.items() if getattr(permissions, perm) != value]

    if missing:
        raise MissingPermissions(missing)
    return

def assert_bot_channel_permissions(bot: Member, channel: GuildChannel, **perms: bool):
    """Checks bot permissions for the channel.
    
    This function takes into consideration the following cases:

    - Guild owner
    - Guild roles
    - Channel overrides
    - Member overrides
    - Member timeout"""
    permissions = channel.permissions_for(bot)

    missing = [perm for perm, value in perms.items() if getattr(permissions, perm) != value]

    if missing:
        raise BotMissingPermissions(missing)
    return




def is_client_pidroid(client: Pidroid) -> bool:
    """Returns true if the current client user is Pidroid."""
    assert client.user is not None
    return client.user.id == PIDROID_ID

def is_guild_theotown(guild: Guild | None) -> bool:
    """Returns true if the specified guild is the TheoTown guild."""
    if guild:
        return guild.id == THEOTOWN_GUILD
    return False

async def is_user_banned(guild: Guild, user: DiscordUser) -> bool:
    """Returns true if user is currently banned in the specified guild."""
    try:
        _ = await guild.fetch_ban(user)
        return True
    except NotFound:
        return False


class TheoTownChecks:
    """This class implements role-based checks for TheoTown guild."""

    @staticmethod
    def is_developer(user: Member | User) -> bool:
        """Returns true if the member is a developer."""
        return user.id in THEOTOWN_DEVELOPERS

    @staticmethod
    def is_administrator_or_higher(member: Member) -> bool:
        """Returns true if the member is considered to be at least an administrator on TheoTown guild."""
        return (
            TheoTownChecks.is_developer(member)              # Any TheoTown developer that is hardcoded
            or _member_has_role(member, 415194893917356052)  # City Council
            or _member_has_role(member, 365482773206532096)  # Mayor
            or _member_has_role(member, 710914534394560544)  # Elder
        )

    @staticmethod
    def is_senior_moderator_or_higher(member: Member) -> bool:
        """Returns true if the member is considered to be at least a senior moderator on TheoTown guild."""
        return (
            _member_has_role(member, 381899421992091669)
            or TheoTownChecks.is_administrator_or_higher(member)
        )

    @staticmethod
    def is_normal_moderator_or_higher(member: Member) -> bool:
        """Returns true if the member is considered to be at least a normal moderator on TheoTown guild."""
        return (
            _member_has_role(member, 368799288127520769)
            or TheoTownChecks.is_senior_moderator_or_higher(member)
        )

    @staticmethod
    def is_junior_moderator_or_higher(member: Member) -> bool:
        """Returns true if the member is considered to be at least a junior moderator on TheoTown guild."""
        return (
            _member_has_role(member, 410512375083565066)
            or TheoTownChecks.is_normal_moderator_or_higher(member)
        )
    
    @staticmethod
    def is_foreign_chat_moderator_or_higher(member: Member) -> bool:
        """Returns true if the member is considered to be at least a foreign chat moderator on TheoTown guild."""
        return (
            _member_has_role(member, TT_MODERATOR_CHAT_ROLE_ID)
            or TheoTownChecks.is_junior_moderator_or_higher(member)
        )

    @staticmethod
    def is_event_manager(member: Member) -> bool:
        """Returns true if the member is considered to be an event manager."""
        return _member_has_role(member, 584109249903198210)

    @staticmethod
    def is_event_voter(member: Member) -> bool:
        """Returns true if the member is authorized to vote in events."""
        return _member_has_role(member, 647443361627766804)




def is_guild_administrator(member: Member) -> bool:
    """Returns true if a member is considered to be a guild adminstrator by Pidroid.
    
    Pidroid only considers members with guild level administrator or manage_guild permissions
    to be guild administrators.
    
    This should not be used for anything except for a very generic check
    to see if a member is definitely an administrator."""
    if is_guild_theotown(member.guild):
        return TheoTownChecks.is_administrator_or_higher(member)

    return (
        member_has_guild_permission(member, 'administrator')
        or member_has_guild_permission(member, 'manage_guild')
    )

def is_guild_moderator(member: Member) -> bool:
    """Returns true if a member is considered to be a guild moderator by Pidroid.
    
    Pidroid only considers members with guild level kick_members, ban_members or moderate_members permissions
    to be guild moderators. It also checks if the member is a guild administrator.
    
    This should not be used for anything except for a very generic check
    to see if a member is definitely a moderator."""
    if is_guild_theotown(member.guild):
        return TheoTownChecks.is_foreign_chat_moderator_or_higher(member) # Foreign moderator by design can be considered to be a minimal moderation role
    
    return (
        is_guild_administrator(member)
        or member_has_guild_permission(member, 'kick_members')
        or member_has_guild_permission(member, 'ban_members')
        or member_has_guild_permission(member, 'moderate_members')
    )



def has_moderator_guild_permissions(ctx: Context[Pidroid], **perms: bool) -> bool:
    """Returns true if the author is a moderator and has the specified guild permissions."""
    assert isinstance(ctx.author, Member)
    if is_guild_theotown(ctx.guild):
        return TheoTownChecks.is_junior_moderator_or_higher(ctx.author)

    # Ugly, I don't care
    try:
        assert_guild_permissions(ctx, **perms)
        return True
    except MissingPermissions:
        return False




async def check_can_modify_tags(ctx: Context[Pidroid]):
    """Checks whether author has the permission to modify tags.

    It first checks if public can edit tags,
    if they can't it will resolve to moderators with manage_messages permission.
    
    Raises exception on failure."""
    assert ctx.guild is not None
    assert isinstance(ctx.author, Member)

    client: Pidroid = ctx.bot
    conf = await client.fetch_guild_configuration(ctx.guild.id)
    if conf.public_tags:
        return True

    if is_guild_theotown(ctx.guild):
        if not TheoTownChecks.is_junior_moderator_or_higher(ctx.author):
            raise MissingUserPermissions('You need to be at least a junior moderator to run this command!')
        return True
    assert_guild_permissions(ctx, manage_messages=True)
    return True

def assert_junior_moderator_permissions(ctx: Context[Pidroid], **perms: bool):
    """Checks whether author has junior moderator permissions in TheoTown guild channel
    or the equivalent permissions in other guild channels.
    
    Raises exception on failure."""
    assert isinstance(ctx.author, Member)
    if is_guild_theotown(ctx.guild):
        if not TheoTownChecks.is_junior_moderator_or_higher(ctx.author):
            raise MissingUserPermissions('You need to be at least a junior moderator to run this command!')
        return
    assert_channel_permissions(ctx, **perms)

def assert_normal_moderator_permissions(ctx: Context[Pidroid], **perms: bool):
    """Checks whether author has normal moderator permissions in TheoTown guild channel
    or the equivalent permissions in other guild channels.
    
    Raises exception on failure."""
    assert isinstance(ctx.author, Member)
    if is_guild_theotown(ctx.guild):
        if not TheoTownChecks.is_normal_moderator_or_higher(ctx.author):
            raise MissingUserPermissions('You need to be at least a moderator to run this command!')
        return
    assert_channel_permissions(ctx, **perms)

def assert_senior_moderator_permissions(ctx: Context[Pidroid], **perms: bool):
    """Checks whether author has senior moderator permissions in TheoTown guild channel
    or the equivalent permissions in other guild channels.
    
    Raises exception on failure."""
    assert isinstance(ctx.author, Member)
    if is_guild_theotown(ctx.guild):
        if not TheoTownChecks.is_senior_moderator_or_higher(ctx.author):
            raise MissingUserPermissions('You need to be at least a senior moderator to run this command!')
        return
    assert_channel_permissions(ctx, **perms)

def assert_moderator_permissions(ctx: Context[Pidroid], *, required_capability: ModCapability, **perms: bool):
    """Checks whether author has moderator permissions in TheoTown guild channel
    or the equivalent permissions in other guild channels.
    
    Raises exception on failure."""
    assert isinstance(ctx.author, Member)
    if is_guild_theotown(ctx.guild):
        capabilities = get_theotown_member_capabilities(ctx.author)
        if not getattr(capabilities, required_capability.value):
            raise MissingUserPermissions(f"You are missing '{required_capability.value}' capability to run this command!")


        capabilities = get_member_capabilities(ctx.author)
        if required_capability not in capabilities:
            raise MissingUserPermissions(f"You are missing '{required_capability.value}' capability to run this command!")
        return
    assert_channel_permissions(ctx, **perms)

def is_junior_moderator(ctx: Context[Pidroid], **perms: bool) -> bool:
    """Returns whether the author is a junior moderator based on role in TheoTown and permissions in other guilds."""
    try:
        assert_junior_moderator_permissions(ctx, **perms)
        return True
    except (MissingUserPermissions, MissingPermissions):
        return False

def is_moderator(ctx: Context[Pidroid], *, required_capability: ModCapability, **perms: bool) -> bool:
    """Returns whether the author is a moderator based on role in TheoTown and permissions in other guilds."""
    try:
        assert_moderator_permissions(ctx, required_capability=required_capability, **perms)
        return True
    except (MissingUserPermissions, MissingPermissions):
        return False
    


def assert_capability(ctx: Context[Pidroid], *, required_capability: Capabilities):
    """Checks whether author has moderator permissions in TheoTown guild channel
    or the equivalent permissions in other guild channels.
    
    Raises exception on failure."""
    assert isinstance(ctx.author, Member)
    capabilities = Capabilities.none()
    if is_guild_theotown(ctx.guild):
        capabilities = get_theotown_member_capabilities(ctx.author)
    else:
        perms  = ctx.channel.permissions_for(ctx.author)
        capabilities = capabilities_from_permissions(perms)
    if (capabilities & required_capability) != required_capability:
        raise MissingUserPermissions(f"You are missing '{required_capability.value}' capability to run this command!")

def has_capability(ctx: Context[Pidroid], *, required_capability: Capabilities) -> bool:
    """Returns whether the author is a moderator based on role in TheoTown and permissions in other guilds."""
    try:
        assert_capability(ctx, required_capability=required_capability)
        return True
    except (MissingUserPermissions, MissingPermissions):
        return False