from dataclasses import dataclass
import datetime
from discord import Asset, Colour, Embed, Member, Object, Permissions, Role, User, Color, Guild
from typing import Union, Optional

@dataclass
class BaseData:
    guild: Guild
    user: Union[Member, User, None]
    reason: Optional[str]
    created_at: datetime.datetime

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
        self.guild = data.guild
        self.__embed = Embed()
        self.__embed.title = self.__logname__
        self.__set_author(data.user)

    def __set_author(self, user: Union[Member, User, None]):
        name = "Unknown"
        icon_url = None
        if user:
            name = str(user)
            icon_url = user.display_avatar.url
        self.__embed.set_author(name=name, icon_url=icon_url)

    def add_field(self, name: str, value: str):
        self.__embed.add_field(name=name, value=value)

    def set_colour(self, colour: Colour):
        """Sets the colour of the embed to the specified"""
        self.__embed.colour = colour

    def as_embed(self) -> Embed:
        return self.__embed


class RoleCreateLog(PidroidLog):

    __logname__ = "New role created"

    def __init__(self, data: RoleCreateData) -> None:
        super().__init__(data)

        self.add_field("Name", data.name)

        # Colour information
        self.set_colour(data.colour)
        self.add_field("Colour", str(data.colour))

        self.add_field("Is mentionable?", str(data.mentionable))
        self.add_field("Is hoisted?", str(data.hoist))
        
        data.icon
        data.unicode_emoji
        data.permissions

class RoleDeleteLog(PidroidLog):

    __logname__ = "Role deleted"

    def __init__(self, data: RoleDeleteData) -> None:
        super().__init__(data)

class RoleUpdateLog(PidroidLog):

    __logname__ = "Role updated"

    def __init__(self, data: RoleUpdateData) -> None:
        super().__init__(data)