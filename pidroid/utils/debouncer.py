import asyncio
import logging

from discord import Object
from enum import Enum
from typing import TypedDict, Any

from pidroid.client import Pidroid

class RoleAction(Enum):
    remove  = 0
    add     = 1

# Represents a tuple of (guild_id, user_id) for identifying a user in a guild.
GuildUserIdTuple = tuple[int, int]
# Represents a tuple of (action, role_id) for pending role change.
PendingRoleChange = tuple[RoleAction, int]

class PendingUpdate(TypedDict):
    task: asyncio.Task[Any] | None
    operations: list[PendingRoleChange]

logger = logging.getLogger('Pidroid')

class RoleChangeDebouncer:
    def __init__(self, client: Pidroid, delay_seconds: float = 0.5):
        self.__client = client
        self.__delay_seconds = delay_seconds
        self.__pending_updates: dict[GuildUserIdTuple, PendingUpdate] = {}

    async def __process_role_change(self, guild_id: int, user_id: int, operations_to_apply: list[PendingRoleChange]):
        """
        This is the actual function that performs the role changes.
        It first fetches the current roles, applies all pending operations,
        and then performs the single API call to update the roles.
        """
        guild = self.__client.get_guild(guild_id)
        if guild is None:
            logger.warning(f"Guild {guild_id} not found. Skipping role update for user {user_id}.")
            return
        
        member = guild.get_member(user_id)
        if member is None:
            logger.warning(f"Member {user_id} not found in guild {guild_id}. Skipping role update.")
            return
        
        composite_key = (guild_id, user_id)

        # Get member's current roles
        current_roles_from_source = set([r.id for r in member.roles])

        # Apply all collected pending operations to the fetched set
        calculated_final_roles = current_roles_from_source.copy()
        #logger.debug(f"Applying {len(operations_to_apply)} operations for {composite_key}...")
        for action, role in operations_to_apply:
            if action == RoleAction.add:
                calculated_final_roles.add(role)
            elif action == RoleAction.remove:
                # Only remove if present, to avoid errors if role was already removed or never existed
                if role in calculated_final_roles:
                    calculated_final_roles.remove(role)
            else:
                logger.warning(f"Unknown action '{action}' for role '{role}' in {composite_key}. Skipping.")

        # If the calculated final roles are the same as the current roles from the source,
        # we can skip the API call
        if calculated_final_roles == current_roles_from_source:
            #logger.debug(f"No changes detected for {composite_key}. Current roles match calculated final roles.")
            return

        # Perform the actual role update
        await member.edit(roles=[Object(id=role_id) for role_id in calculated_final_roles], reason="Role changes processed by debouncer.")


    async def update_user_role(self, action: RoleAction, guild_id: int, user_id: int, role: int):
        """
        Accepts an individual role action (add or remove) for a user in a guild.
        This method queues the action and debounces the final update.
        """
        composite_key = (guild_id, user_id)

        # Initialize pending operations list if not exists
        if self.__pending_updates.get(composite_key) is None:
            self.__pending_updates[composite_key] = {
                'task': None,
                'operations': []
            }

        # Add the new operation to the list
        self.__pending_updates[composite_key]['operations'].append((action, role))
        #logger.debug(f"Queued operation for {composite_key}: {action} {role}. Total pending: {len(self.__pending_updates[composite_key]['operations'])}")

        # Cancel any existing pending task
        task = self.__pending_updates[composite_key]['task']
        if task is not None:
            task.cancel()

        # Schedule a new debounced task
        # Make a copy of operations to ensure we don't accidentally mutate the list while processing.
        operations_snapshot_for_task = self.__pending_updates[composite_key]['operations'].copy()

        async def _delayed_task():
            try:
                await asyncio.sleep(self.__delay_seconds)
                await self.__process_role_change(guild_id, user_id, operations_snapshot_for_task)
            except asyncio.CancelledError: # ignore cancellation errors
                pass
            except Exception as e: # catch all other exceptions
                logger.exception(f"Error processing role change for {composite_key}: {e}")
            finally:
                # After the task completes (or is cancelled), clean up its entry
                # Only remove if it's the *exact* task that was scheduled.
                # This check prevents removing a newly scheduled task if an old one just finished.
                if composite_key in self.__pending_updates and \
                   self.__pending_updates[composite_key]['task'] == asyncio.current_task():
                    # Clear the operations list and the task reference
                    #logger.debug(f"Cleaning up pending operations for {composite_key}.")
                    del self.__pending_updates[composite_key]

        task = asyncio.create_task(_delayed_task())
        self.__pending_updates[composite_key]['task'] = task
