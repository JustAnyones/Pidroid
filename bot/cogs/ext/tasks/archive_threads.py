from discord import NotFound
from discord.ext import tasks, commands # type: ignore
from discord.threads import Thread

from client import Pidroid
from cogs.utils.checks import is_client_pidroid
from cogs.utils.time import utcnow


class ThreadTasks(commands.Cog): # type: ignore
    """This class implements a cog for handling of Threads that get archived after some time."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.api = self.client.api

        self.archive_threads.start()

    def cog_unload(self) -> None:
        """Ensure that tasks are cancelled on cog unload."""
        self.archive_threads.cancel()

    @tasks.loop(seconds=60)
    async def archive_threads(self) -> None:
        """Archives expired threads."""
        threads_to_archive = await self.api.get_archived_threads(utcnow().timestamp())
        for thread_item in threads_to_archive:
            thread_id: int = thread_item["thread_id"]

            try:
                thread: Thread = await self.client.fetch_channel(thread_id)
            except Exception as e:
                self.client.logger.exception(f"Failure to look up a thread, ID is {thread_id}\nException: {e}")

                if isinstance(e, NotFound):
                    # If thread channel was deleted completely
                    if e.code == 10003:
                        self.client.logger.info("Thread channel does not exist, deleting from the database")
                        await self.api.remove_thread(thread_item["_id"])
                continue

            await thread.edit(archived=False) # Workaround for stupid bug where archived threads can't be instantly locked
            await thread.edit(archived=True, locked=True)
            await self.api.remove_thread(thread_item["_id"])

    @archive_threads.before_loop
    async def before_archive_threads(self) -> None:
        """Runs before archive_threads task to ensure that the task is allowed to run."""
        await self.client.wait_until_ready()
        if not is_client_pidroid(self.client):
            self.archive_threads.cancel()

async def setup(client: Pidroid) -> None:
    await client.add_cog(ThreadTasks(client))
