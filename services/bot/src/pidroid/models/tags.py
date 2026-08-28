from __future__ import annotations

import datetime

from discord import User
from discord.ext.commands.errors import BadArgument
from discord.utils import MISSING
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pidroid.client import Pidroid
    from pidroid.utils.db.tag import TagTable

FORBIDDEN_CHARS = "!@#$%^&*()-+?_=,<>/"
RESERVED_WORDS = [
    "create", "edit", "remove", "claim", "transfer", "list", "info",
    "add-author", "add_author", "raw",
    "remove-author", "remove_author"
]

class Tag:
    """This class represents a guild tag."""

    def __init__(
        self,
        client: Pidroid,
        *,
        row: int = MISSING,
        guild_id: int,
        name: str,
        content: str,
        authors: list[int],
        aliases: list[str],
        locked: bool,
        date_created: datetime.datetime,
    ) -> None:
        
        self.__client = client
        self.__row = row
        self.__guild_id = guild_id

        self.validate_name(name)
        self.validate_content(content)
        self.__name = name
        self.__content = content

        self.__authors = authors.copy()
        self.__aliases = aliases.copy()
        self.__locked = locked
        self.__date_created = date_created

    @classmethod
    async def create(
        cls,
        client: Pidroid,
        *,
        guild_id: int,
        name: str,
        content: str,
        author: int
    ) -> Tag:
        cls.validate_name(name)
        cls.validate_content(content)

        row = await client.api.insert_tag(guild_id, name, content, [author])
        tag = await client.api.fetch_tag(row)
        assert tag
        return tag

    @classmethod
    def from_table(cls, client: Pidroid, table: TagTable):
        """Creates a Tag object from a table."""
        return cls(
            client,
            row=table.id,
            guild_id=table.guild_id,
            name=table.name,
            content=table.content,
            authors=table.authors,
            aliases=table.aliases,
            locked=table.locked,
            date_created=table.date_created,
        )

    async def edit(
        self,
        *,
        content: str = MISSING,
        authors: list[int] = MISSING,
        owner_id: int = MISSING,
    ) -> None:
        """Edits the tag by updating the entry in the database."""

        if content is not MISSING:
            self.validate_content(content)
            self.__content = content
        
        if authors is not MISSING and owner_id is not MISSING:
            raise BadArgument("Cannot have both authors and owner_id set")

        if authors is not MISSING:
            if len(authors) == 0:
                raise BadArgument("Author list cannot be empty")
            self.__authors = authors.copy()

        if owner_id is not MISSING:
            # If it was in list before hand, like a co-author
            if owner_id in self.co_author_ids:
                self.__authors.remove(owner_id)

            if len(self.__authors) == 0:
                self.__authors.append(owner_id)
            else:
                self.__authors[0] = owner_id

        await self.__client.api.update_tag(self.row, self.content, self.__authors, self.__aliases, self.__locked)

    async def add_co_author(self, author_id: int) -> None:
        """Adds the specified author to tag co-authors.
        
        Will raise BadArgument if author ID is not valid."""
        if self.author_id == author_id:
            raise BadArgument("You cannot add yourself as a co-author!")
        if len(self.__authors) > 4:
            raise BadArgument("A tag can only have up to 4 co-authors!")
        if author_id in self.co_author_ids:
            raise BadArgument("Specifed member is already a co-author!")
        self.__authors.append(author_id)
        await self.edit()

    async def remove_co_author(self, author_id: int) -> None:
        """Removes the specified author ID from co-authors.
        
        Will raise BadArgument if specified member is not a co-author."""
        if author_id not in self.co_author_ids:
            raise BadArgument("Specified member is not a co-author!")
        self.__authors.remove(author_id)
        await self.edit()

    @property
    def row(self) -> int:
        """Returns the database row for the tag."""
        return self.__row

    @property
    def name(self) -> str:
        """Returns the name of the tag."""
        return self.__name

    @property
    def content(self) -> str:
        """Returns the content of the tag."""
        return self.__content

    @property
    def author_id(self) -> int:
        """Returns the user ID of the tag author."""
        return self.__authors[0]

    @property
    def co_author_ids(self) -> list[int]:
        """Returns a list of tag's co-authors' user IDs."""
        return self.__authors[1:]

    @property
    def aliases(self) -> list[str]:
        """Returns the list of tag aliases."""
        return self.__aliases

    @property
    def locked(self) -> bool:
        """Returns true if tag is locked, preventing modifications."""
        return self.__locked

    @property
    def date_created(self) -> datetime.datetime:
        """Returns the datetime object of when the tag was created."""
        return self.__date_created

    @staticmethod
    def validate_name(value: str):
        if len(value) < 3:
            raise ValueError("Tag name is too short! Please keep it above 2 characters!")
        if len(value) > 30:
            raise ValueError("Tag name is too long! Please keep it below 30 characters!")
        if any(w in RESERVED_WORDS for w in value.split(" ")):
            raise ValueError("Tag name cannot contain reserved words!")
        if any(c in FORBIDDEN_CHARS for c in value):
            raise ValueError("Tag name cannot contain forbidden characters!")

    @staticmethod
    def validate_content(value: str):
        if len(value) > 2000:
            raise ValueError("Tag content is too long! Please keep it below 2000 characters!")

    def to_dict(self) -> dict[str, Any]:
        """Returns the dict representation of the object."""
        return {
            "row": self.row,
            "name": self.name,
            "content": self.content,
            "authors": self.__authors,
            "aliases": self.__aliases,
            "locked": self.__locked,
            "date_created": self.__date_created
        }

    def is_author(self, user_id: int) -> bool:
        """Returns true if specified user is an author."""
        return user_id in self.__authors

    def get_authors(self) -> list[User | None]:
        """Returns a list of optional user objects which represent the tag authors."""
        return [self.__client.get_user(auth_id) for auth_id in self.__authors]

    async def fetch_authors(self) -> list[User | None]:
        """Returns a list of optional user objects which represent the tag authors.
        
        This does a fetch if user is not found in cache."""
        return [await self.__client.get_or_fetch_user(auth_id) for auth_id in self.__authors]
