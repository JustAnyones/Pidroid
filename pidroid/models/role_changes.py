from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Set

if TYPE_CHECKING:
    from pidroid.utils.api import API

class RoleAction(Enum):
    remove  = 0
    add     = 1

class RoleQueueState(Enum):
    enqueued = 0
    processing = 1
    finished = 2

class MemberRoleChanges:

    def __init__(
        self,
        api: API,
        guild_id: int, member_id: int,
        ids: List[int],
        roles_added: Optional[List[int]], roles_removed: Optional[List[int]]
    ) -> None:
        self.__api = api
        self.__guild_id = guild_id
        self.__member_id = member_id
        self.__row_ids = ids

        self.__roles_added: Set[int] = set(roles_added or [])
        self.__roles_removed: Set[int] = set(roles_removed or [])

    @property
    def member_id(self) -> int:
        """Returns the ID of the member."""
        return self.__member_id # type: ignore

    @property
    def roles_added(self) -> List[int]:
        """Returns a list of role IDs that are queued to be added."""
        return [r for r in self.__roles_added]
    
    @property
    def roles_removed(self) -> List[int]:
        """Returns a list of role IDs that are queued to be removed."""
        return [r for r in self.__roles_removed]

    async def pop(self):
        """Removes the member changes from the queue."""
        #raise NotImplementedError
        await self.__api.delete_role_changes(self.__row_ids)