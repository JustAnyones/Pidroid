import aiocron
import logging

from aiohttp.client_exceptions import ServerDisconnectedError
from asyncio import Task
from datetime import timedelta
from discord.channel import TextChannel
from discord.ext import tasks, commands
from typing import override

from pidroid.client import Pidroid
from pidroid.modules.plugin_store.types import PluginStoreStatisticsDict
from pidroid.modules.plugin_store.ui import MonthlyPluginReportLayout
from pidroid.utils import http, truncate_string
from pidroid.utils.cronjobs import start_cronjob
from pidroid.utils.data import PersistentDataStore
from pidroid.utils.time import timedelta_to_datetime

PLUGIN_SHOWCASE_CHANNEL_ID = 640522649033769000
PLUGIN_REVISION_CHANNEL_ID = 1444621889686470821
PLUGIN_INFORMATION_CHANNEL_ID = 640521916943171594

logger = logging.getLogger("pidroid.plugin_store.service")

class PluginStoreService(commands.Cog):
    """This class implements a cog for handling of automatic tasks related to TheoTown's plugin store."""

    def __init__(self, client: Pidroid) -> None:
        super().__init__()
        self.client: Pidroid = client

        self.use_threads: bool = True
        self.add_reactions: bool = True

        self.new_plugins_cache: list[int] = []
        self.new_revisions_cache: list[int] = []

        _ = self.retrieve_new_plugins.start()
        _ = self.retrieve_new_plugin_revisions.start()
        self.monthly_plugin_cronjob: Task[None] = self.client.loop.create_task(
            start_cronjob(self.client, monthly_plugin_cronjob, "Monthly plugin statistics")
        )

    @override
    async def cog_unload(self):
        """Ensure that tasks are cancelled on cog unload."""
        self.retrieve_new_plugins.cancel()
        self.retrieve_new_plugin_revisions.cancel()
        _ = self.monthly_plugin_cronjob.cancel()

    @tasks.loop(seconds=60)
    async def retrieve_new_plugins(self) -> None:
        """Retrieves new plugin store plugins and publishes them to TheoTown guild channel."""

        channel = await self.client.get_or_fetch_channel(PLUGIN_SHOWCASE_CHANNEL_ID)
        if channel is None:
            return logger.warning("Showcase channel could not be resolved!")
        assert isinstance(channel, TextChannel)

        try:
            async with PersistentDataStore() as store:
                time = await store.get("last_plugin_approval_time")

            if time is None:
                last_approval_time = -1
            else:
                last_approval_time = int(time)

            plugins = await self.client.api.fetch_new_plugins(last_approval_time)

            if len(plugins) == 0:
                self.new_plugins_cache = []
                return

            latest_approval_time = plugins[0].approval_time
            if latest_approval_time > last_approval_time:

                async with PersistentDataStore() as store:
                    await store.set("last_plugin_approval_time", str(latest_approval_time))

                for plugin in plugins:

                    if plugin.plugin_id in self.new_plugins_cache:
                        continue
                    self.new_plugins_cache.append(plugin.plugin_id)

                    message = await channel.send(embed=plugin.to_embed())

                    if self.add_reactions:
                        await message.add_reaction("👍")
                        await message.add_reaction("👎")

                    if self.use_threads:
                        _ = await self.client.create_expiring_thread(
                            message, f"{truncate_string(plugin.clean_name, 89)} discussion",
                            timedelta_to_datetime(timedelta(days=14))
                        )
        except ServerDisconnectedError:
            logger.exception("An server disconnection was encountered while trying to retrieve and publish new plugin information")
        except Exception:
            logger.exception("An exception was encountered while trying to retrieve and publish new plugin information")

    @retrieve_new_plugins.before_loop
    async def before_new_plugin_retriever(self) -> None:
        """Runs before retrieve_new_plugins task to ensure that the task is ready to run."""
        await self.client.wait_until_ready()

    @tasks.loop(seconds=60)
    async def retrieve_new_plugin_revisions(self) -> None:
        """Retrieves new plugin store plugin revisions and publishes them to a hidden channel."""

        channel = await self.client.get_or_fetch_channel(PLUGIN_REVISION_CHANNEL_ID)
        if channel is None:
            return logger.warning("Revision channel could not be resolved!")
        assert isinstance(channel, TextChannel)

        try:
            async with PersistentDataStore() as store:
                time = await store.get("last_plugin_revision_query_time")

            if time is None:
                last_query_time = -1
            else:
                last_query_time = int(time)

            plugins = await self.client.api.fetch_new_revisions(last_query_time)

            if len(plugins) == 0:
                self.new_revisions_cache = []
                return

            last_plugin_time = plugins[-1].submission_time
            if last_plugin_time > last_query_time:

                async with PersistentDataStore() as store:
                    await store.set("last_plugin_revision_query_time", str(last_plugin_time))

                for plugin in plugins:
                    if plugin.revision_id in self.new_revisions_cache:
                        continue
                    self.new_revisions_cache.append(plugin.revision_id)

                    # Only announce unapproved revisions
                    if plugin.approval_time > 0:
                        continue

                    _ = await channel.send(
                        embed=plugin.to_embed(),
                        content=f"New revision for plugin ID {plugin.plugin_id} submitted."
                    )


        except ServerDisconnectedError:
            logger.exception("A server disconnection was encountered while trying to retrieve and publish new plugin revisions")
        except Exception:
            logger.exception("An exception was encountered while trying to retrieve and publish new plugin revisions")

    @retrieve_new_plugin_revisions.before_loop
    async def before_new_plugin_revisions_retriever(self) -> None:
        """Runs before retrieve_new_plugin_revisions task to ensure that the task is ready to run."""
        await self.client.wait_until_ready()

@aiocron.crontab('0 9 1 * *', start=False) # At 8 in the morning of the first day every month
async def monthly_plugin_cronjob(client: Pidroid) -> None:
    """Retrieves monthly plugin information and posts it to TheoTown guild channel."""
    try:
        channel = await client.get_or_fetch_channel(PLUGIN_INFORMATION_CHANNEL_ID)
        assert isinstance(channel, TextChannel)
        async with await http.get(client, "https://api.theotown.com/store/get_stats") as response:
            data: PluginStoreStatisticsDict = await response.json()

        month_of_data = int(data["month"])

        async with PersistentDataStore() as store:
            previous_month = await store.get("last_plugin_statistic_month")

        if previous_month is None:
            return
        previous_month = int(previous_month)

        if month_of_data != previous_month:
            async with PersistentDataStore() as store:
                await store.set("last_plugin_statistic_month", str(month_of_data))

            layout = MonthlyPluginReportLayout(data)
            _ = await channel.send(view=layout)
    except Exception:
        logger.exception("An exception was encountered while trying announce monthly plugin information")


async def setup(client: Pidroid) -> None:
    await client.add_cog(PluginStoreService(client))
