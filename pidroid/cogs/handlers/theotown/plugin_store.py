import aiocron # type: ignore
import calendar
import logging

from aiohttp.client_exceptions import ServerDisconnectedError
from datetime import timedelta
from discord.channel import TextChannel
from discord.ext import tasks, commands # type: ignore
from discord.utils import escape_markdown
from typing import List

from pidroid.client import Pidroid
from pidroid.utils import http, truncate_string, clean_inline_translations
from pidroid.utils.cronjobs import start_cronjob
from pidroid.utils.data import PersistentDataStore
from pidroid.utils.embeds import PidroidEmbed
from pidroid.utils.time import timedelta_to_datetime

PLUGIN_SHOWCASE_CHANNEL_ID = 640522649033769000
PLUGIN_INFORMATION_CHANNEL_ID = 640521916943171594

logger = logging.getLogger("Pidroid")

class PluginStoreTasks(commands.Cog):
    """This class implements a cog for handling of automatic tasks related to TheoTown's plugin store."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client

        self.use_threads = True
        self.add_reactions = True

        self.new_plugins_cache: List[int] = []

        self.retrieve_new_plugins.start()
        self.monthly_plugin_cronjob = self.client.loop.create_task(
            start_cronjob(self.client, monthly_plugin_cronjob, "Monthly plugin statistics")
        )

    def cog_unload(self):
        """Ensure that tasks are cancelled on cog unload."""
        self.retrieve_new_plugins.cancel()
        self.monthly_plugin_cronjob.cancel()

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

            latest_approval_time = plugins[0].time

            if latest_approval_time > last_approval_time:

                async with PersistentDataStore() as store:
                    await store.set("last_plugin_approval_time", str(latest_approval_time))

                for plugin in plugins:

                    if plugin.id in self.new_plugins_cache:
                        continue
                    self.new_plugins_cache.append(plugin.id)

                    message = await channel.send(embed=plugin.to_embed())

                    if self.add_reactions:
                        await message.add_reaction("👍")
                        await message.add_reaction("👎")

                    if self.use_threads:
                        await self.client.create_expiring_thread(
                            message, f"{truncate_string(plugin.clean_title, 89)} discussion",
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


@aiocron.crontab('0 9 1 * *', start=False) # At 8 in the morning of the first day every month
async def monthly_plugin_cronjob(client: Pidroid) -> None:
    """Retrieves monthly plugin information and posts it to TheoTown guild channel."""
    try:
        channel = await client.get_or_fetch_channel(PLUGIN_INFORMATION_CHANNEL_ID)
        assert isinstance(channel, TextChannel)
        async with await http.get(client, "https://store.theotown.com/get_stats") as response:
            data = await response.json()

        year_of_data = int(data["year"])
        month_of_data = int(data["month"])
        month_name = calendar.month_name[month_of_data]

        async with PersistentDataStore() as store:
            previous_month = await store.get("last_plugin_statistic_month")

        if previous_month is None:
            return
        previous_month = int(previous_month)

        if month_of_data != previous_month:
            async with PersistentDataStore() as store:
                await store.set("last_plugin_statistic_month", str(month_of_data))

            top_creators_last = data['plugin creators last month']
            plugins_all_time = data['plugins all time']
            creators_all_time = data['plugin creators all time by downloads']

            initial_embed = PidroidEmbed(
                title=f"Plugin store statistics for {month_name}",
                description=f"In total **{data['plugin count last month']}** new plugins have been released in **{month_name} of {year_of_data}**.\nMost of them were contributed by:"
            )
            top_plugins_embed = PidroidEmbed(title="Most popular plugins of all time")
            top_creators_embed = PidroidEmbed(title="Most popular plugin creators of all time")
            top_creators_embed.set_footer(text="This message is automated. More information, as always, can be found on our forums.")

            for creator in top_creators_last:
                initial_embed.add_field(
                    name=f"• {escape_markdown(creator['author_name'])}",
                    value=f"{creator['plugins']} plugin(s) which reached {int(creator['downloads']):,} downloads!",
                    inline=False
                )

            for i in range(9): # Only 9 results
                top_plugin = plugins_all_time[i]
                top_creator = creators_all_time[i]
                top_plugins_embed.add_field(
                    name=f"{i+1}. {clean_inline_translations(top_plugin['name'])}",
                    value=f"Made by **{escape_markdown(top_plugin['author_name'])}** reaching {int(top_plugin['downloads']):,} downloads!",
                    inline=False
                )
                top_creators_embed.add_field(
                    name=f"{i+1}. {escape_markdown(top_creator['author_name'])}",
                    value=f"And their {top_creator['plugins']} plugin(s) reaching {int(top_creator['downloads']):,} downloads!",
                    inline=False
                )

            await channel.send(embeds=[initial_embed, top_plugins_embed, top_creators_embed])
    except Exception:
        logger.exception("An exception was encountered while trying announce monthly plugin information")


async def setup(client: Pidroid) -> None:
    await client.add_cog(PluginStoreTasks(client))
