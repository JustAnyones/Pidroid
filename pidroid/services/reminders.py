import logging

from discord import Permissions
from discord.ext import tasks, commands
from typing import Optional

from sqlalchemy import delete, select

from pidroid.client import Pidroid
from pidroid.utils.aliases import MessageableGuildChannel, MessageableGuildChannelTuple
from pidroid.utils.api import ReminderTable
from pidroid.utils.checks import member_has_channel_permission
from pidroid.utils.embeds import PidroidEmbed
from pidroid.utils.time import utcnow

logger = logging.getLogger("Pidroid")

class ReminderService(commands.Cog): # type: ignore
    """This class implements a cog for handling deliveries of reminders."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.deliver_due_reminders.start()

    def cog_unload(self):
        """Ensure that tasks are cancelled on cog unload."""
        self.deliver_due_reminders.stop()

    async def send_reminder(self, reminder: ReminderTable):
        """Sends a reminder."""
        user = self.client.get_user(reminder.user_id)
        # If we cannot find the user, don't even bother
        if user is None:
            return

        # Find channel, if it was set
        channel: Optional[MessageableGuildChannel] = None
        if reminder.channel_id:
            chan = self.client.get_channel(reminder.channel_id)
            if chan:
                assert isinstance(chan, MessageableGuildChannelTuple)
                channel = chan

        # Create the messages
        embed = PidroidEmbed(
            title="Reminder",
            description=reminder.content
        )
        embed.add_field(name="Reminder created in", value=reminder.message_url)

        # Send out the messages
        # To the found channel, if allowed
        can_send_to_channel = channel and member_has_channel_permission(channel, channel.guild.me, Permissions.send_messages)
        if channel and can_send_to_channel:
            use_embed = member_has_channel_permission(channel, channel.guild.me, Permissions.embed_links)

            if use_embed:
                await channel.send(content=f"{user.mention} reminder", embed=embed)
            else:
                await channel.send(
                    content=(
                        f"{user.mention} you asked to remind you {reminder.content!r} "
                        f"at {reminder.message_url}"
                    )
                )

        # Or the user directly, if channel was not set
        else:
            await user.send(embed=embed)


    @tasks.loop(seconds=15)
    async def deliver_due_reminders(self) -> None:
        """Periodically fetches and delivers due reminders."""
        try:
            async_session = self.client.api.session
            async with async_session() as session: 
                async with session.begin():
                    # Acquire every due reminder
                    result = await session.execute(
                        select(ReminderTable).
                        filter(ReminderTable.date_remind <= utcnow())
                    )

                    # Go over each reminder, send it
                    # and delete it from database
                    for row in result.fetchall():
                        reminder = row[0]
                        try:
                            await self.send_reminder(reminder)
                        except Exception:
                            logger.exception("An exception was encountered while trying to send a due reminder")
                        await session.execute(
                            delete(ReminderTable).
                            filter(ReminderTable.id == reminder.id)
                        )
                # Commit it
                await session.commit()
        except Exception:
            logger.exception("An exception was encountered while trying to deliver due reminders")

    @deliver_due_reminders.before_loop
    async def before_deliver_due_reminders(self) -> None:
        """Runs before deliver_due_reminders task to ensure that the task is allowed to run."""
        await self.client.wait_until_ready()

async def setup(client: Pidroid) -> None:
    await client.add_cog(ReminderService(client))
