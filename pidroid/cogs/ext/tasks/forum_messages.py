import sys
import traceback

from discord.channel import TextChannel
from discord.ext import tasks, commands # type: ignore
from discord.utils import format_dt

from pidroid.client import Pidroid
from pidroid.constants import THEOTOWN_FORUM_URL
from pidroid.cogs.utils.checks import is_client_pidroid
from pidroid.cogs.utils.embeds import PidroidEmbed
from pidroid.cogs.utils.http import Route
from pidroid.cogs.utils.parsers import truncate_string
from pidroid.cogs.utils.time import timestamp_to_datetime

class ForumMessageTask(commands.Cog): # type: ignore
    """This class implements a cog for handling forum PMs to Pidroid user."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.fetch_messages.start()

    def cog_unload(self) -> None:
        """Ensure that tasks are cancelled on cog unload."""
        self.fetch_messages.cancel()

    @property
    def message_channel(self) -> TextChannel:
        """Returns forum PM channel object."""
        return self.client.get_channel(707561286820692039)

    @tasks.loop(seconds=60)
    async def fetch_messages(self) -> None:
        try:
            response = await self.client.api.get(Route("/private/forum/get_unread_messages"))

            for message in response["data"]:

                message_id = message["msg_id"]
                subject = truncate_string(message["message_subject"], 256)
                text = truncate_string(message["message_text"], 4096)
                time_sent = message["message_time"]
                message_url = f"{THEOTOWN_FORUM_URL}/ucp.php?i=pm&f=-2&p={message_id}"

                author_id = message["author_id"]
                author_name = message["author_username"]
                author_url = f"{THEOTOWN_FORUM_URL}/memberlist.php?mode=viewprofile&u={author_id}"
                author_avatar_url = f"{THEOTOWN_FORUM_URL}/download/file.php?avatar={message['author_avatar']}"

                embed = PidroidEmbed(title=subject, description=text, url=message_url)
                embed.add_field(name="Time sent", value=format_dt(timestamp_to_datetime(time_sent)))
                embed.set_author(name=author_name, icon_url=author_avatar_url, url=author_url)
                embed.set_footer(text=f"Message ID: {message_id}")
                await self.message_channel.send(embed=embed)
        except Exception as e:
            self.client.logger.exception("An exception was encountered while trying to fetch Pidroid messages")
            traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)

    @fetch_messages.before_loop
    async def before_fetch_messages(self) -> None:
        """Runs before archive_threads task to ensure that the task is allowed to run."""
        await self.client.wait_until_ready()
        if not is_client_pidroid(self.client):
            self.fetch_messages.cancel()

async def setup(client: Pidroid) -> None:
    await client.add_cog(ForumMessageTask(client))
