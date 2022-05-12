from datetime import timedelta
from discord import Message, NotFound
from discord.threads import Thread
from discord.ext import tasks, commands
from discord.ext.commands.context import Context

from cogs.models.categories import RandomCategory
from cogs.utils.time import utcnow
from client import Pidroid
from cogs.utils.checks import is_client_pidroid
from cogs.utils.time import timedelta_to_datetime

class ThreadTasks(commands.Cog):
    """This class implements a cog for handling of Threads that get archived after some time."""

    @commands.command()
    async def thread(self, ctx: Context, timeout: int = timedelta_to_datetime(timedelta(seconds=30)).timestamp()):
        message = await ctx.reply(content="here it is")
        await self.create_expiring_thread(ctx.message  , "testNshit", timeout)

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.api = self.client.api

        self.archive_threads.start()

    def cog_unload(self) -> None:
        """Ensure that tasks are cancelled on cog unload."""
        self.archive_threads.cancel()

    async def create_expiring_thread(self, message: Message, name: str, expire_timestamp: int):
        thread = await message.create_thread(name=name, auto_archive_duration=60)
        await self.api.create_new_expiring_thread(thread.id, expire_timestamp)

    @tasks.loop(seconds=60)
    async def archive_threads(self) -> None:
        """Archives expired threads."""
        threads_to_archive = await self.api.get_archived_threads(utcnow().timestamp())
        print(len(threads_to_archive))
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
