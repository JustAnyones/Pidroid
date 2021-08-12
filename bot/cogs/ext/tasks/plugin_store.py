import traceback
import sys

from datetime import timedelta
from discord.channel import TextChannel
from discord.ext import tasks, commands

from client import Pidroid
from cogs.utils.checks import is_client_pidroid
from cogs.utils.parsers import truncate_string
from cogs.utils.time import timedelta_to_datetime, utcnow

class PluginStoreTasks(commands.Cog):
    """This class implements a cog for handling of automatic tasks related to TheoTown's plugin store."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.api = self.client.api

        self.use_threads = True

        self.new_plugins_cache = []
        self.showcase_channel: TextChannel = None

        self.retrieve_new_plugins.start()
        self.archive_threads.start()

    def cog_unload(self) -> None:
        """Ensure that tasks are cancelled on cog unload."""
        self.retrieve_new_plugins.cancel()
        self.archive_threads.cancel()

    def resolve_channel(self) -> None:
        """Resolves plugin showcase channel."""
        if self.showcase_channel is None:
            self.showcase_channel = self.client.get_channel(640522649033769000)

            # If lookup failed, call cog unload method to cancel any tasks belonging to this class
            if self.showcase_channel is None:
                self.cog_unload()

    @tasks.loop(seconds=60)
    async def archive_threads(self) -> None:
        """Archives plugin showcase threads."""
        self.resolve_channel()
        threads_to_archive = await self.api.get_archived_plugin_threads(utcnow().timestamp())
        for thread_item in threads_to_archive:
            thread = self.showcase_channel.get_thread(thread_item["thread_id"])
            try:
                if not thread.archived:
                    await thread.edit(archived=True, locked=True)
                else:
                    await thread.edit(locked=True)
            except Exception:
                self.client.logger.exception("An exception was encountered while trying to lock a plugin thread")
            await self.api.remove_plugin_thread_record(thread_item["_id"])

    @archive_threads.before_loop
    async def before_archive_threads(self) -> None:
        """Runs before archive_threads task to ensure that the task is allowed to run."""
        await self.client.wait_until_ready()
        if not is_client_pidroid(self.client):
            self.archive_threads.cancel()

    @tasks.loop(seconds=30)
    async def retrieve_new_plugins(self) -> None:
        """Retrieves new plugin store plugins and publishes them to TheoTown guild channel."""
        try:
            last_approval_time = self.client.persistent_data.data.get("last plugin approval", -1)

            plugins = await self.api.get_new_plugins(last_approval_time)

            if len(plugins) == 0:
                self.new_plugins_cache = []
                return

            latest_approval_time = plugins[0].time

            if latest_approval_time > last_approval_time:
                self.resolve_channel()

                self.client.persistent_data.data.update({"last plugin approval": latest_approval_time})
                self.client.persistent_data.save()

                for plugin in plugins:

                    if plugin.id in self.new_plugins_cache:
                        continue
                    self.new_plugins_cache.append(plugin.id)

                    message = await self.showcase_channel.send(embed=plugin.to_embed())

                    await message.add_reaction(emoji="👍")
                    await message.add_reaction(emoji="👎")

                    if self.use_threads:
                        thread = await message.start_thread(name=f"{truncate_string(plugin.clean_title, 89)} discussion", auto_archive_duration=60)
                        await self.api.create_new_plugin_thread(thread.id, timedelta_to_datetime(timedelta(days=2)).timestamp())

        except Exception as e:
            self.client.logger.exception("An exception was encountered while trying to retrieve and publish new plugin information")
            traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)

    @retrieve_new_plugins.before_loop
    async def before_new_plugin_retriever(self) -> None:
        """Runs before retrieve_new_plugins task to ensure that the task is allowed to run."""
        await self.client.wait_until_ready()
        if not is_client_pidroid(self.client):
            self.retrieve_new_plugins.cancel()

def setup(client: Pidroid) -> None:
    client.add_cog(PluginStoreTasks(client))
