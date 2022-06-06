import aiocron # type: ignore
import asyncio
import calendar
import discord
import traceback
import sys

from contextlib import suppress
from discord.channel import TextChannel
from discord.ext import commands
from discord.utils import escape_markdown
from io import BytesIO

from client import Pidroid
from cogs.utils import http
from cogs.utils.checks import is_client_pidroid
from cogs.utils.http import get_filename
from cogs.utils.embeds import PidroidEmbed
from cogs.utils.parsers import clean_inline_translations


class CronjobTask(commands.Cog): # type: ignore
    """This class implements a cog for cronjob handling."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.shitpost_cronjob = self.client.loop.create_task(
            self.start_cronjob(shitpost_cronjob, "Shitpost")
        )
        self.monthly_plugin_cronjob = self.client.loop.create_task(
            self.start_cronjob(monthly_plugin_cronjob, "Monthly plugin")
        )

    def cog_unload(self) -> None:
        """Ensure that cron job tasks are cancelled on cog unload."""
        self.shitpost_cronjob.cancel()
        self.monthly_plugin_cronjob.cancel()

    async def start_cronjob(self, cronjob: aiocron.Cron, cron_name: str = "Generic", require_pidroid=True) -> None:
        """Creates a new cronjob task with specified parameters."""
        await self.client.wait_until_ready()

        if require_pidroid and not is_client_pidroid(self.client):
            return

        try:
            self.client.logger.info(f"{cron_name} cron job task started")
            while True:
                await cronjob.next(self.client)
        except asyncio.CancelledError:
            with suppress(Exception):
                cronjob.stop()
                self.client.logger.info(f"{cron_name} cron job task stopped")


@aiocron.crontab('27 14 * * 3,0', start=False) # At 14:27 on Wednesday and Sunday
async def shitpost_cronjob(client: Pidroid) -> None:
    """A cron job for Pidroid to post a shitpost in a secret channel."""
    await post_shitpost(client)

@aiocron.crontab('0 9 1 * *', start=False) # At 8 at the morning of the first day every month
async def monthly_plugin_cronjob(client: Pidroid) -> None:
    """Retrieves monthly plugin information and posts it to TheoTown guild channel."""
    try:
        channel: TextChannel = client.get_channel(640521916943171594)
        async with await http.get(client, "https://store.theotown.com/get_stats") as response:
            data = await response.json()

        year_of_data = int(data["year"])
        month_of_data = int(data["month"])
        month_name = calendar.month_name[month_of_data]

        previous_month = client.persistent_data.data.get("last plugin info month", None)

        if month_of_data != previous_month:
            client.persistent_data.data.update({"last plugin info month": month_of_data})
            client.persistent_data.save()

            top_creators_last = data['plugin creators last month']
            plugins_all_time = data['plugins all time']
            creators_all_time = data['plugin creators all time by downloads']

            initial_embed = PidroidEmbed(
                title=f"Plugin store statistics for {month_name}",
                description=f"In total **{data['plugin count last month']}** new plugins have been submitted in **{month_name} of {year_of_data}**.\nMost of them were contributed by:"
            )
            top_plugins_embed = PidroidEmbed(title="Most popular plugins of all time")
            top_creators_embed = PidroidEmbed(title="Most popular plugin creators of all time")
            top_creators_embed.set_footer(text="This message is automated. More information, as always, can be found on our forums.")

            for creator in top_creators_last:
                initial_embed.add_field(
                    name=f"• {escape_markdown(creator['author_name'])}",
                    value=f"{creator['plugins']} plugins which reached {int(creator['downloads']):,} downloads!",
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
                    value=f"And its {top_creator['plugins']} plugins reaching {int(top_creator['downloads']):,} downloads!",
                    inline=False
                )

            await channel.send(embed=initial_embed)
            await channel.send(embed=top_plugins_embed)
            await channel.send(embed=top_creators_embed)
    except Exception as e:
        client.logger.exception("An exception was encountered while trying announce monthly plugin information")
        traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)


last_posts = [-1, -1, -1, -1]
async def post_shitpost(client: Pidroid) -> None:
    """Posts a shitpost to a hidden channel."""
    choice = await client.api.get_random_shitpost(last_posts)
    await client.api.log_shitpost(choice["_id"])

    text = choice.get("text", None)
    file_url = choice.get("attachment_url", None)

    if text is None and file_url is None:
        return

    shitpost_channel: TextChannel = client.get_channel(779757485980385321)

    if file_url is not None:
        async with await http.get(client, file_url) as r:
            payload = await r.read()
            filename = get_filename(r.headers['Content-Disposition'])
        with BytesIO(payload) as f:
            discord_file = discord.File(f, filename)
        await shitpost_channel.send(content=text, file=discord_file)
    else:
        await shitpost_channel.send(content=text)

    last_posts.pop(0)
    last_posts.append(choice['_id'])


async def setup(client: Pidroid) -> None:
    await client.add_cog(CronjobTask(client))
