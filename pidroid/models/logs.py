import datetime

from dataclasses import dataclass
from discord import Asset, Colour, Embed, Member, Object, Permissions, Role, User, Color, Guild
from typing import List, Union, Optional

from pidroid.utils import normalize_permission_name, role_mention

@dataclass
class BaseData:
    guild: Guild
    user: Union[Member, User, None]
    reason: Optional[str]
    created_at: datetime.datetime

@dataclass
class BaseMemberData(BaseData):
    member: Union[Member, User, Object]

@dataclass
class _MemberUpdateData:
    nick: Optional[str]
    # Whether the member is being server muted.
    mute: bool
    # Whether the member is being server deafened.
    deaf: bool
    timed_out_until: Optional[datetime.datetime]

@dataclass
class MemberUpdateData(BaseMemberData):
    before: _MemberUpdateData
    after: _MemberUpdateData

@dataclass
class _MemberRoleUpdateData:
    roles: List[Union[Role, Object]]

@dataclass
class MemberRoleUpdateData(BaseMemberData):
    before: _MemberRoleUpdateData
    after: _MemberRoleUpdateData

@dataclass
class BaseRoleData(BaseData):
    role: Union[Role, Object]

@dataclass
class RoleCreateData(BaseRoleData):
    colour: Colour
    mentionable: bool
    hoist: bool
    icon: Asset
    unicode_emoji: str
    name: str
    permissions: Permissions

@dataclass
class RoleDeleteData(BaseRoleData):
    colour: Colour
    mentionable: bool
    hoist: bool
    name: str
    permissions: Permissions

@dataclass
class _RoleUpdateData:
    colour: Colour
    mentionable: bool
    hoist: bool
    icon: Asset
    unicode_emoji: str
    name: str
    permissions: Permissions

@dataclass
class RoleUpdateData(BaseRoleData):
    before: _RoleUpdateData
    after: _RoleUpdateData

class BaseLog:

    def __init__(self, guild: Guild) -> None:
        self.type = "Base log"
        self.embed = Embed(color=Color.red())
        self.guild = guild

    def __str__(self) -> str:
        return self.__class__.__name__

    def __repr__(self) -> str:
        return f'<BaseLog type="{self.type}" title="{self.embed.title}">'

    def set_title(self, title: str) -> None:
        """Sets embed title."""
        self.embed.title = title

    def set_description(self, description: str) -> None:
        """Sets embed description."""
        self.embed.description = description

    def add_field(self, name: str, value: str, inline: bool = True) -> None:
        """Adds an embed field."""
        self.embed.add_field(name=name, value=value, inline=inline)

    def set_footer(self, text: Optional[str] = None, icon_url: Optional[str] = None) -> None:
        """Sets embed footer."""
        self.embed.set_footer(text=text, icon_url=icon_url)

    def set_type(self, log_type: str) -> None:
        """Sets log type. An alias for set_title."""
        self.set_title(log_type)

    def set_author(self, name: str, icon_url: Optional[str] = None) -> None:
        """Sets embed author."""
        self.embed.set_author(name=name, icon_url=icon_url)

    def put_author(self, user: Union[Member, User]) -> None:
        """Sets embed author and specifies the user ID in the footer."""
        self.set_author(str(user), user.display_avatar.url)
        self.embed.set_footer(text=f"User ID: {user.id}")

    def as_embed(self) -> Embed:
        """Returns embed representation of the object."""
        return self.embed

class PidroidLog:

    __logname__ = "A new Pidroid log"

    def __init__(self, data: BaseData) -> None:
        self.__guild = data.guild
        self.__embed = Embed(title=self.__logname__, timestamp=data.created_at)
        self.__set_author(data.user)

    @property
    def guild(self) -> Guild:
        """Returns the guild object associated with the Pidroid log."""
        return self.__guild

    def __set_author(self, user: Union[Member, User, None]):
        """Sets the author of the current Pidroid log."""
        name = "Unknown"
        icon_url = None
        user_id = "Unknown"
        if user:
            name = str(user)
            icon_url = user.display_avatar.url
            user_id = str(user.id)
        self.__embed.set_author(name=name, icon_url=icon_url)
        self.__embed.set_footer(text=f"Perpetrator ID: {user_id}")

    def add_field(self, name: str, value: str):
        """Adds a field to the internal log embed."""
        self.__embed.add_field(name=name, value=value)

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

        self.add_field("Name", data.name)

        # Colour information
        self.set_colour(data.colour)
        self.add_field("Colour", str(data.colour))

        self.add_field("Is mentionable?", str(data.mentionable))
        self.add_field("Is hoisted?", str(data.hoist))
        self.add_field("Icon", data.icon.url)
        self.add_field("Emoji", data.unicode_emoji)

        filtered = []
        for permission in data.permissions:
            name, value = permission
            filtered.append(f"{normalize_permission_name(name)}: {value}")
        self.add_field("Permissions", '\n'.join(filtered))

class RoleDeleteLog(PidroidLog):

    __logname__ = "Role deleted"

    def __init__(self, data: RoleDeleteData) -> None:
        super().__init__(data)

        self.set_description(f"Role: {role_mention(data.role.id)} ({data.role.id})")

        self.add_field("Name", data.name)

        # Colour information
        self.set_colour(data.colour)
        self.add_field("Colour", str(data.colour))

        self.add_field("Is mentionable?", str(data.mentionable))
        self.add_field("Is hoisted?", str(data.hoist))

        filtered = []
        for permission in data.permissions:
            name, value = permission
            filtered.append(f"{normalize_permission_name(name)}: {value}")
        self.add_field("Permissions", '\n'.join(filtered))

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
        self.set_colour(after.colour)
        if before.colour != after.colour:
            self.add_field("Colour", f"{before.colour} -> {after.colour}")
        
        # Mentionability change
        if before.mentionable != after.mentionable:
            self.add_field("Is mentionable?", f"{before.mentionable} -> {after.mentionable}")

        # Hoist change
        if before.hoist != after.hoist:
            self.add_field("Is hoisted?", f"{before.hoist} -> {after.hoist}")

        # Icon change
        if before.icon != after.icon:
            self.add_field("Icon", f"{before.icon.url} -> {after.icon.url}")

        # Emoji change
        if before.unicode_emoji != after.unicode_emoji:
            self.add_field("Emoji", f"{before.unicode_emoji} -> {after.unicode_emoji}")

        # Permission change
        if before.permissions != after.permissions:
            after_permissions = [p for p in after.permissions]
            filtered = []
            for i, before_perm in enumerate(before.permissions):
                before_perm_name, before_perm_value = before_perm
                if before_perm_value != after_permissions[i][1]:
                    filtered.append(f"{normalize_permission_name(before_perm_name)}: {after_permissions[i][0]}")
            self.add_field("Permissions", '\n'.join(filtered))