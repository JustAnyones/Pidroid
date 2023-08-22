from __future__ import annotations

import datetime

from discord import User
from discord.ext.commands.errors import BadArgument
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from pidroid.client import Pidroid
    from pidroid.utils.api import TagTable

FORBIDDEN_CHARS = "!@#$%^&*()-+?_=,<>/"
RESERVED_WORDS = [
    "create", "edit", "remove", "claim", "transfer", "list", "info",
    "add-author", "add_author", "raw",
    "remove-author", "remove_author"
]

class Tag:
    """This class represents a guild tag."""

    if TYPE_CHECKING:
        _id: int
        guild_id: int
        _name: str
        _content: str
        _author_ids: List[int]
        aliases: List[str]
        locked: bool
        _date_created: datetime.datetime

    def __init__(self, client: Pidroid, data: Optional[TagTable] = None) -> None:
        self._client = client
        self._api = client.api
        self._author_ids = []
        if data:
            self._deserialize(data)

    def to_dict(self) -> dict:
        """Returns the dict representation of the object."""
        return {
            "row": self.row,
            "name": self.name,
            "content": self.content,
            "author_ids": self._author_ids,
            "aliases": self.aliases,
            "locked": self.locked,
            "date_created": self._date_created
        }

    @property
    def row(self) -> int:
        """Returns the database row for the tag."""
        return self._id

    @property
    def name(self) -> str:
        """Returns the name of the tag."""
        return self._name

    @name.setter
    def name(self, value: str):
        """Sets the name of the tag.
        
        Will raise BadArgument if the name is deemed invalid."""
        if len(value) < 3:
            raise BadArgument("Tag name is too short! Please keep it above 2 characters!")
        if len(value) > 30:
            raise BadArgument("Tag name is too long! Please keep it below 30 characters!")
        if any(w in RESERVED_WORDS for w in value.split(" ")):
            raise BadArgument("Tag name cannot contain reserved words!")
        if any(c in FORBIDDEN_CHARS for c in value):
            raise BadArgument("Tag name cannot contain forbidden characters!")
        self._name = value

    @property
    def content(self) -> str:
        """Returns the content of the tag."""
        return self._content

    @content.setter
    def content(self, value: str):
        """Sets the content of the tag.
        
        Will raise BadArgument if the content string is too long."""
        if len(value) > 2000:
            raise BadArgument("Tag content is too long! Please keep it below 2000 characters!")
        self._content = value

    @property
    def author_id(self) -> int:
        """Returns the user ID of the tag author."""
        return self._author_ids[0]

    @author_id.setter
    def author_id(self, value: int) -> None:
        """Sets the tag author to the specified user ID."""
        # If it was in list before hand, like a co-author
        if value in self.co_author_ids:
            self._author_ids.remove(value)

        if len(self._author_ids) == 0:
            return self._author_ids.append(value)
        self._author_ids[0] = value

    @property
    def co_author_ids(self) -> List[int]:
        """Returns a list of tag's co-authors' user IDs."""
        return self._author_ids[1:]

    def add_co_author(self, author_id: int) -> None:
        """Adds the specified author to tag co-authors.
        
        Will raise BadArgument if author ID is not valid."""
        if self.author_id == author_id:
            raise BadArgument("You cannot add yourself as a co-author!")
        if len(self._author_ids) > 4:
            raise BadArgument("A tag can only have up to 4 co-authors!")
        if author_id in self.co_author_ids:
            raise BadArgument("Specifed member is already a co-author!")
        self._author_ids.append(author_id)

    def remove_co_author(self, author_id: int) -> None:
        """Removes the specified author ID from co-authors.
        
        Will raise BadArgument if specified member is not a co-author."""
        if author_id not in self.co_author_ids:
            raise BadArgument("Specified member is not a co-author!")
        self._author_ids.remove(author_id)

    def is_author(self, user_id: int) -> bool:
        """Returns true if specified user is an author."""
        return user_id in self._author_ids

    async def fetch_authors(self) -> List[Optional[User]]:
        """Returns a list of optional user objects which represent the tag authors."""
        return [await self._client.get_or_fetch_user(auth_id) for auth_id in self._author_ids]

    def _deserialize(self, data: TagTable) -> None:
        self._id = data.id # type: ignore
        self.guild_id = data.guild_id # type: ignore
        self._name = data.name # type: ignore
        self._content = data.content # type: ignore
        self._author_ids = data.authors # type: ignore
        self.aliases = data.aliases # type: ignore
        self.locked = data.locked # type: ignore
        self._date_created = data.date_created # type: ignore

    async def create(self) -> None:
        """Creates a tag by inserting an entry to the database."""
        self._id = await self._api.insert_tag(self.guild_id, self.name, self.content, self._author_ids)

    async def edit(self) -> None:
        """Edits the tag by updating the entry in the database."""
        await self._api.update_tag(self._id, self.content, self._author_ids, self.aliases, self.locked)

    async def remove(self) -> None:
        """Removes the tag entry from the database."""
        if not self._api:
            raise BadArgument("API attribute is missing!")
        await self._api.delete_tag(self._id)