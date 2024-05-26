import datetime

from dataclasses import dataclass
from discord import Asset, ChannelFlags, ChannelType, Colour, Embed, Member, Object, PermissionOverwrite, Permissions, Role, User, Guild, VideoQualityMode, abc
from discord.utils import format_dt

from pidroid.constants import EMBED_COLOUR
from pidroid.utils import channel_mention, normalize_permission_name, role_mention, user_mention
from pidroid.utils.aliases import DiscordUser

@dataclass
class BaseData:
    guild: Guild
    user: Member | User | None
    reason: str | None
    created_at: datetime.datetime

@dataclass
class BaseChannelData(BaseData):
    channel: abc.GuildChannel | Object

@dataclass
class ChannelCreateData(BaseChannelData):
    name: str
    type: ChannelType
    overwrites: list[tuple[Member | User | Role | Object, PermissionOverwrite]]

@dataclass
class ChannelDeleteData(BaseChannelData):
    name: str
    type: ChannelType
    overwrites: list[tuple[Member | User | Role | Object, PermissionOverwrite]]
    flags: ChannelFlags
    nsfw: bool
    slowmode_delay: int

@dataclass
class _ChannelData:
    name: str | None
    type: ChannelType | None
    position: int | None
    overwrites: list[tuple[Member | User | Role | Object, PermissionOverwrite]]
    topic: str | None
    bitrate: int | None
    rtc_region: str | None
    video_quality_mode: VideoQualityMode | None
    default_auto_archive_duration: int | None
    nsfw: bool | None
    slowmode_delay: int | None
    user_limit: int | None

@dataclass
class ChannelUpdateData(BaseChannelData):
    before: _ChannelData
    after: _ChannelData

@dataclass
class BaseOverwriteData(BaseData):
    channel: abc.GuildChannel | Object
    role_or_user: Role | Member | Object

@dataclass
class _OverwriteData:
    id: int            # ID of the role or user that is being changed for 
    type: ChannelType  # The type of channel.
    deny: Permissions  # The permissions being denied.
    allow: Permissions # The permissions being allowed.

@dataclass
class OverwriteCreateData(BaseOverwriteData, _OverwriteData):
    pass

@dataclass
class OverwriteDeleteData(BaseOverwriteData, _OverwriteData):
    pass

@dataclass
class OverwriteUpdateData(BaseOverwriteData):
    before: _OverwriteData
    after: _OverwriteData

@dataclass
class BaseMemberData(BaseData):
    member: Member | User | Object

@dataclass
class _MemberUpdateData:
    nick: str | None
    # Whether the member is being server muted.
    mute: bool | None
    # Whether the member is being server deafened.
    deaf: bool | None
    timed_out_until: datetime.datetime | None

@dataclass
class MemberUpdateData(BaseMemberData):
    before: _MemberUpdateData
    after: _MemberUpdateData

@dataclass
class _MemberRoleUpdateData:
    roles: list[Role | Object]

@dataclass
class MemberRoleUpdateData(BaseMemberData):
    before: _MemberRoleUpdateData
    after: _MemberRoleUpdateData

@dataclass
class BaseRoleData(BaseData):
    role: Role | Object

@dataclass
class RoleCreateData(BaseRoleData):
    colour: Colour | None
    mentionable: bool | None
    hoist: bool | None
    icon: Asset | None
    unicode_emoji: str | None
    name: str | None
    permissions: Permissions | None

@dataclass
class RoleDeleteData(BaseRoleData):
    colour: Colour | None
    mentionable: bool | None
    hoist: bool | None
    name: str | None
    permissions: Permissions | None

@dataclass
class _RoleUpdateData:
    colour: Colour | None
    mentionable: bool | None
    hoist: bool | None
    icon: Asset | None
    unicode_emoji: str | None
    name: str | None
    permissions: Permissions | None

@dataclass
class RoleUpdateData(BaseRoleData):
    before: _RoleUpdateData
    after: _RoleUpdateData

@dataclass
class KickData(BaseData):
    user: DiscordUser | None
    target: User | Object

@dataclass
class BanData(BaseData):
    user: DiscordUser | None
    target: User | Object

@dataclass
class UnbanData(BaseData):
    user: DiscordUser | None
    target: User | Object


class PidroidLog:

    __logname__ = "A new Pidroid log"

    def __init__(self, data: BaseData) -> None:
        super().__init__()
        self.__guild = data.guild
        self.__embed = Embed(title=self.__logname__, timestamp=data.created_at)
        self.__set_author(data.user)
        self.__embed.colour = Colour(EMBED_COLOUR)

    @property
    def guild(self) -> Guild:
        """Returns the guild object associated with the Pidroid log."""
        return self.__guild

    def __set_author(self, user: Member | User | None):
        """Sets the author of the current Pidroid log."""
        name = "Unknown"
        icon_url = None
        user_id = "Unknown"
        if user:
            name = str(user)
            icon_url = user.display_avatar.url
            user_id = str(user.id)
        _ = self.__embed.set_author(name=name, icon_url=icon_url)
        _ = self.__embed.set_footer(text=f"Perpetrator ID: {user_id}")

    def add_reason_field(self, data: BaseData):
        """Adds a reason field to the end of the embed."""
        if data.reason:
            size = len(self.__embed.fields)
            _ = self.__embed.insert_field_at(size, name="Reason", value=data.reason, inline=False)

    def add_field(self, name: str, value: str):
        """Adds a field to the internal log embed."""
        if len(value) > 1024:
            raise ValueError("Value cannot be longer than 1024 characters!")
        _ = self.__embed.add_field(name=name, value=value)

    def set_colour(self, colour: Colour):
        """Sets the colour of the embed to the specified."""
        self.__embed.colour = colour

    def set_description(self, text: str):
        """Sets the description of the embed."""
        self.__embed.description = text

    def as_embed(self) -> Embed:
        """Returns the internal log embed object."""
        return self.__embed


class RoleCreateLog(PidroidLog):

    __logname__ = "New role created"

    def __init__(self, data: RoleCreateData) -> None:
        super().__init__(data)

        self.set_description(f"Role: {role_mention(data.role.id)} ({data.role.id})")

        if data.name:
            self.add_field("Name", data.name)

        # Colour information
        if isinstance(data.role, Role):
            self.set_colour(data.role.colour)
        if data.colour:
            self.set_colour(data.colour)
            self.add_field("Colour", str(data.colour))

        if data.mentionable is not None:
            self.add_field("Is mentionable?", str(data.mentionable))
        if data.hoist is not None:
            self.add_field("Is hoisted?", str(data.hoist))
        if data.icon:
            self.add_field("Icon", data.icon.url)
        if data.unicode_emoji:
            self.add_field("Emoji", data.unicode_emoji)

        if data.permissions:
            filtered: list[str] = []
            for permission in data.permissions:
                name, value = permission
                filtered.append(f"{normalize_permission_name(name)}: {value}")
            perms_as_string = '\n'.join(filtered)
            if len(perms_as_string) <= 1024: # TODO: figure a better solution out
                self.add_field("Permissions", perms_as_string)

        self.add_reason_field(data)

class RoleDeleteLog(PidroidLog):

    __logname__ = "Role deleted"

    def __init__(self, data: RoleDeleteData) -> None:
        super().__init__(data)

        self.set_description(f"Role: {role_mention(data.role.id)} ({data.role.id})")
        
        if data.name:
            self.add_field("Name", data.name)

        # Colour information
        if isinstance(data.role, Role):
            self.set_colour(data.role.colour)
        if data.colour:
            self.set_colour(data.colour)
            self.add_field("Colour", str(data.colour))

        if data.mentionable is not None:
            self.add_field("Is mentionable?", str(data.mentionable))
        if data.hoist is not None:
            self.add_field("Is hoisted?", str(data.hoist))

        if data.permissions:
            filtered: list[str] = []
            for permission in data.permissions:
                name, value = permission
                filtered.append(f"{normalize_permission_name(name)}: {value}")
            perms_as_string = '\n'.join(filtered)
            if len(perms_as_string) <= 1024: # TODO: figure a better solution out
                self.add_field("Permissions", perms_as_string)
        
        self.add_reason_field(data)

class RoleUpdateLog(PidroidLog):

    __logname__ = "Role updated"

    def __init__(self, data: RoleUpdateData) -> None:
        super().__init__(data)

        before = data.before
        after = data.after

        self.set_description(f"Role: {role_mention(data.role.id)} ({data.role.id})")
        
        # React to name change
        if before.name != after.name:
            self.add_field("Name", f"{before.name} -> {after.name}")

        # Colour information
        if isinstance(data.role, Role):
            self.set_colour(data.role.colour)
        if before.colour != after.colour:
            #self.set_colour(after.colour)
            self.add_field("Colour", f"{before.colour} -> {after.colour}")
        
        # Mentionability change
        if before.mentionable != after.mentionable:
            self.add_field("Is mentionable?", f"{before.mentionable} -> {after.mentionable}")

        # Hoist change
        if before.hoist != after.hoist:
            self.add_field("Is hoisted?", f"{before.hoist} -> {after.hoist}")

        # Role icon change
        if before.icon != after.icon:
            self.add_field("Icon", f"{before.icon} -> {after.icon}")

        # Role emoji change
        if before.unicode_emoji != after.unicode_emoji:
            self.add_field("Role emoji", f"{before.unicode_emoji} -> {after.unicode_emoji}")

        # Permission change
        if before.permissions != after.permissions:
            assert after.permissions is not None
            assert before.permissions is not None
            after_permissions = [p for p in after.permissions]
            filtered: list[str] = []
            for i, before_perm in enumerate(before.permissions):
                before_perm_name, before_perm_value = before_perm
                if before_perm_value != after_permissions[i][1]:
                    marker = "\\-" if after_permissions[i][1] is False else "+"
                    filtered.append(f"{marker} {normalize_permission_name(before_perm_name)}")
            perms_as_string = '\n'.join(filtered)
            if len(perms_as_string) <= 1024: # TODO: figure a better solution out
                self.add_field("Permissions changed", perms_as_string)
        
        self.add_reason_field(data)

class MemberUpdateLog(PidroidLog):

    __logname__ = "Member updated"

    def __init__(self, data: MemberUpdateData) -> None:
        super().__init__(data)

        self.set_description(f"Member: {user_mention(data.member.id)} ({data.member.id})")

        before = data.before
        after = data.after

        # Nick related
        if before.nick is None and after.nick is not None:
            self.add_field("Nickname added", after.nick)
        elif before.nick is not None and after.nick is None:
            self.add_field("Nickname cleared", f"Was: {before.nick}")
        elif before.nick != after.nick:
            self.add_field("Nickname changed", f"{before.nick} -> {after.nick}")

        if before.mute != after.mute:
            self.add_field("Server muted", f"{before.mute} -> {after.mute}")

        if before.deaf != after.deaf:
            self.add_field("Server deafened", f"{before.deaf} -> {after.deaf}")

        # Timeout related
        if before.timed_out_until is None and after.timed_out_until is None:
            # If both are none, do nothing
            pass
        # If timeout was set but now its not
        elif before.timed_out_until is not None and after.timed_out_until is None:
            self.add_field("Timed out until", "Timeout removed")
        # If timeout wasn't set, but now it is
        elif before.timed_out_until is None and after.timed_out_until is not None:
            self.add_field("Timed out until", format_dt(after.timed_out_until))
        # If timeout was set before and changed now
        elif before.timed_out_until and after.timed_out_until and before.timed_out_until != after.timed_out_until:
            self.add_field("Timed out until", f"{format_dt(before.timed_out_until)} -> {format_dt(after.timed_out_until)}")

        self.add_reason_field(data)

class MemberRoleUpdateLog(PidroidLog):

    __logname__ = "Member roles updated"

    def __init__(self, data: MemberRoleUpdateData) -> None:
        super().__init__(data)

        self.set_description(f"Member: {user_mention(data.member.id)} ({data.member.id})")

        roles_before = data.before.roles
        roles_after = data.after.roles

        if len(roles_before) > 0:
            msg = ""
            for role in roles_before:
                msg += f"{role_mention(role.id)} ({role.id})\n"
            self.add_field("Roles removed", msg.strip())

        if len(roles_after) > 0:
            msg = ""
            for role in roles_after:
                msg += f"{role_mention(role.id)} ({role.id})\n"
            self.add_field("Roles added", msg.strip())

        self.add_reason_field(data)

class _OverwriteLog(PidroidLog):

    @staticmethod
    def _is_role(data: BaseOverwriteData):
        """Returns true if the target is a role."""
        if isinstance(data.role_or_user, Object):
            if data.role_or_user.type == "role":
                return True
            return False
        return isinstance(data.role_or_user, Role)

class OverwriteCreateLog(_OverwriteLog):

    __logname__ = "New channel overwrite created"

    def __init__(self, data: OverwriteCreateData) -> None:
        super().__init__(data)

        self.set_description(f"Channel: {channel_mention(data.channel.id)} ({data.channel.id})")

        if self._is_role(data):
            self.add_field("Role", f"{role_mention(data.role_or_user.id)} ({data.role_or_user.id})")
        else:
            self.add_field("Member", f"{user_mention(data.role_or_user.id)} ({data.role_or_user.id})")


        filtered: list[str] = []
        for permission in data.deny:
            name, value = permission
            filtered.append(f"{normalize_permission_name(name)}: {value}")
        perms_as_string = '\n'.join(filtered)
        print(perms_as_string)
        if len(perms_as_string) <= 1024: # TODO: figure a better solution out
            self.add_field("Permissions 1", perms_as_string)

        filtered = []
        for permission in data.allow:
            name, value = permission
            filtered.append(f"{normalize_permission_name(name)}: {value}")
        perms_as_string = '\n'.join(filtered)
        print(perms_as_string)
        if len(perms_as_string) <= 1024: # TODO: figure a better solution out
            self.add_field("Permissions 2", perms_as_string)

        print(data.deny, data.allow)

        self.add_reason_field(data)

class OverwriteDeleteLog(_OverwriteLog):

    __logname__ = "Channel overwrite deleted"

    def __init__(self, data: OverwriteDeleteData) -> None:
        super().__init__(data)

        self.set_description(f"Channel: {channel_mention(data.channel.id)} ({data.channel.id})")

        if self._is_role(data):
            self.add_field("Role", f"{role_mention(data.role_or_user.id)} ({data.role_or_user.id})")
        else:
            self.add_field("Member", f"{user_mention(data.role_or_user.id)} ({data.role_or_user.id})")


        filtered: list[str] = []
        for permission in data.deny:
            name, value = permission
            filtered.append(f"{normalize_permission_name(name)}: {value}")
        perms_as_string = '\n'.join(filtered)
        print("Perms 1", perms_as_string)
        print()
        if len(perms_as_string) <= 1024: # TODO: figure a better solution out
            self.add_field("Permissions 1", perms_as_string)

        filtered = []
        for permission in data.allow:
            name, value = permission
            filtered.append(f"{normalize_permission_name(name)}: {value}")
        perms_as_string = '\n'.join(filtered)
        print("Perms 2", perms_as_string)
        print()
        if len(perms_as_string) <= 1024: # TODO: figure a better solution out
            self.add_field("Permissions 2", perms_as_string)

        print(data.deny, data.allow)


        self.add_reason_field(data)

class OverwriteUpdateLog(_OverwriteLog):

    __logname__ = "Channel overwrite updated"

    def __init__(self, data: OverwriteUpdateData) -> None:
        super().__init__(data)

        self.set_description(f"Channel: {channel_mention(data.channel.id)} ({data.channel.id})")

        if self._is_role(data):
            self.add_field("Role", f"{role_mention(data.role_or_user.id)} ({data.role_or_user.id})")
        else:
            self.add_field("Member", f"{user_mention(data.role_or_user.id)} ({data.role_or_user.id})")

        #filtered = []
        #for permission in data.deny:
        #    name, value = permission
        #    filtered.append(f"{normalize_permission_name(name)}: {value}")
        #perms_as_string = '\n'.join(filtered)
        #if len(perms_as_string) <= 1024: # TODO: figure a better solution out
        #    self.add_field("Permissions 1", perms_as_string)

        #filtered = []
        #for permission in data.allow:
        #    name, value = permission
        #    filtered.append(f"{normalize_permission_name(name)}: {value}")
        #perms_as_string = '\n'.join(filtered)
        #if len(perms_as_string) <= 1024: # TODO: figure a better solution out
        #    self.add_field("Permissions 2", perms_as_string)

        print(data.before.deny, data.before.allow)
        print(data.after.deny, data.after.allow)

        self.add_reason_field(data)



class ChannelCreateLog(_OverwriteLog):

    __logname__ = "New channel created"

    def __init__(self, data: ChannelCreateData) -> None:
        super().__init__(data)

        self.set_description(f"Channel: {channel_mention(data.channel.id)} ({data.channel.id})")

        if data.name:
            self.add_field("Name", data.name)

        if data.type:
            self.add_field("Channel type", str(data.type))

        for target, overwrite in data.overwrites:
            # TODO: implement
            pass

        self.add_reason_field(data)

class ChannelDeleteLog(_OverwriteLog):

    __logname__ = "Channel deleted"

    def __init__(self, data: ChannelDeleteData) -> None:
        super().__init__(data)

        self.set_description(f"Channel: {channel_mention(data.channel.id)} ({data.channel.id})")

        if data.name:
            self.add_field("Name", data.name)

        if data.type:
            self.add_field("Channel type", str(data.type))

        for target, overwrite in data.overwrites:
            # TODO: implement
            pass

        self.add_field("Was age-restricted?", str(data.nsfw))
        self.add_field("Slowmode delay", "Not set" if data.slowmode_delay == 0 else f"{data.slowmode_delay} seconds")

        self.add_reason_field(data)

class ChannelUpdateLog(_OverwriteLog):

    __logname__ = "Channel updated"

    def __init__(self, data: ChannelUpdateData) -> None:
        super().__init__(data)

        self.set_description(f"Channel: {channel_mention(data.channel.id)} ({data.channel.id})")

        before = data.before
        after = data.after

        # If name changed
        if before.name != after.name:
            self.add_field("Name", f"{before.name} -> {after.name}")

        #if data.name:
        #    self.add_field("Name", data.name)

        #if data.type:
        #    self.add_field("Channel type", str(data.type))

        #for target, overwrite in data.overwrites:
        #    # TODO: implement
        #    pass

        #self.add_field("Was age-restricted?", str(data.nsfw))
        #self.add_field("Slowmode delay", "Not set" if data.slowmode_delay == 0 else f"{data.slowmode_delay} seconds")

        self.add_reason_field(data)