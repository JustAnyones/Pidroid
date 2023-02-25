from discord import NotFound
from discord.ext import tasks, commands # type: ignore
from discord.threads import Thread

from pidroid.client import Pidroid
from pidroid.cogs.utils.checks import is_client_pidroid
from pidroid.cogs.utils.time import utcnow


class ThreadTasks(commands.Cog): # type: ignore
    """This class implements a cog for automatic handling of threads that get archived after some time."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.archive_threads.start()

    def cog_unload(self):
        """Ensure that tasks are cancelled on cog unload."""
        self.archive_threads.cancel()

    @tasks.loop(seconds=60)
    async def archive_threads(self) -> None:
        """Archives expired threads."""
        threads_to_archive = await self.client.api.fetch_expired_threads(utcnow())
        for thread_entry in threads_to_archive:

            try:
                thread = await self.client.fetch_channel(thread_entry.thread_id) # type: ignore
                assert isinstance(thread, Thread)
            except Exception as e:
                self.client.logger.exception(f"Failure to look up a thread, ID is {thread_entry.thread_id}\nException: {e}")

                if isinstance(e, NotFound):
                    # If thread channel was deleted completely
                    if e.code == 10003:
                        self.client.logger.info("Thread channel does not exist, deleting from the database")
                        await self.client.api.delete_expiring_thread(thread_entry.id) # type: ignore
                continue

            await thread.edit(archived=False) # Workaround for stupid bug where archived threads can't be instantly locked
            await thread.edit(archived=True, locked=True)
            await self.client.api.delete_expiring_thread(thread_entry.id) # type: ignore

    @archive_threads.before_loop
    async def before_archive_threads(self) -> None:
        """Runs before archive_threads task to ensure that the task is allowed to run."""
        await self.client.wait_until_ready()
        if not is_client_pidroid(self.client):
            self.archive_threads.cancel()

async def setup(client: Pidroid) -> None:
    await client.add_cog(ThreadTasks(client))
