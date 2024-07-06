import logging

from discord import NotFound
from discord.ext import tasks, commands
from discord.threads import Thread
from typing import override

from pidroid.client import Pidroid
from pidroid.utils.time import utcnow

logger = logging.getLogger("Pidroid")

class ThreadArchiverService(commands.Cog):
    """This class implements a cog for automatic handling of threads that get archived after some time."""

    def __init__(self, client: Pidroid) -> None:
        super().__init__()
        self.client = client
        self.archive_threads.start()

    @override
    async def cog_unload(self):
        """Ensure that tasks are cancelled on cog unload."""
        self.archive_threads.cancel()

    @tasks.loop(seconds=60)
    async def archive_threads(self) -> None:
        """Archives expired threads."""
        threads_to_archive = await self.client.api.fetch_expired_threads(utcnow())
        for thread_entry in threads_to_archive:

            try:
                thread = await self.client.fetch_channel(thread_entry.thread_id)
                assert isinstance(thread, Thread)
            except Exception as e:
                logger.exception(f"Failure to look up a thread, ID is {thread_entry.thread_id}\nException: {e}")

                if isinstance(e, NotFound):
                    # If thread channel was deleted completely
                    if e.code == 10003:
                        logger.warning("Thread channel does not exist, deleting entry from the database")
                        await self.client.api.delete_expiring_thread(thread_entry.id)
                continue

            _ = await thread.edit(archived=False) # Workaround for stupid bug where archived threads can't be instantly locked
            _ = await thread.edit(archived=True, locked=True)
            await self.client.api.delete_expiring_thread(thread_entry.id)

    @archive_threads.before_loop
    async def before_archive_threads(self) -> None:
        """Runs before archive_threads task to ensure that the task is ready to run."""
        await self.client.wait_until_ready()

async def setup(client: Pidroid) -> None:
    await client.add_cog(ThreadArchiverService(client))
