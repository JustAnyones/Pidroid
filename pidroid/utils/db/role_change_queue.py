from __future__ import annotations

import datetime

from enum import Enum
from sqlalchemy import BigInteger, DateTime, Integer
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column
from typing import TYPE_CHECKING

from pidroid.utils.db.base import Base

if TYPE_CHECKING:
    from pidroid.utils.api import API

class RoleAction(Enum):
    remove  = 0
    add     = 1

class RoleQueueState(Enum):
    enqueued = 0
    processing = 1
    finished = 2

class RoleChangeQueue(Base):
    __tablename__ = "RoleChangeQueue"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    action: Mapped[int] = mapped_column(Integer) # RoleAction
    status: Mapped[int] = mapped_column(Integer) # RoleQueueState
    guild_id: Mapped[int]= mapped_column(BigInteger)
    member_id: Mapped[int] = mapped_column(BigInteger)
    role_id: Mapped[int] = mapped_column(BigInteger)
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=func.now()) # pyright: ignore[reportAny]

class MemberRoleChanges:

    def __init__(
        self,
        api: API,
        guild_id: int,
        member_id: int,
        ids: list[int],
        roles_added: list[int] | None, roles_removed: list[int] | None
    ) -> None:
        super().__init__()
        self.__api = api
        self.__guild_id = guild_id
        self.__member_id = member_id
        self.__row_ids = ids

        self.__roles_added: set[int] = set(roles_added or [])
        self.__roles_removed: set[int] = set(roles_removed or [])

    @property
    def member_id(self) -> int:
        """Returns the ID of the member."""
        return self.__member_id

    @property
    def roles_added(self) -> list[int]:
        """Returns a list of role IDs that are queued to be added."""
        return [r for r in self.__roles_added]
    
    @property
    def roles_removed(self) -> list[int]:
        """Returns a list of role IDs that are queued to be removed."""
        return [r for r in self.__roles_removed]

    async def pop(self):
        """Removes the member changes from the queue."""
        #raise NotImplementedError
        await self.__api.delete_role_changes(self.__row_ids)