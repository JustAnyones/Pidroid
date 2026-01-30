import logging

from discord import Message, Permissions
from discord.ext import tasks, commands
from typing import override

from sqlalchemy import delete, select

from pidroid.client import Pidroid
from pidroid.utils.aliases import MessageableGuildChannel, MessageableGuildChannelTuple
from pidroid.utils.checks import member_has_channel_permission
from pidroid.utils.db.reminder import Reminder
from pidroid.utils.embeds import PidroidEmbed
from pidroid.utils.time import utcnow

logger = logging.getLogger("pidroid.services.reminders")

class ReminderService(commands.Cog):
    """This class implements a cog for handling deliveries of reminders."""

    def __init__(self, client: Pidroid) -> None:
        super().__init__()
        self.client = client
        _ = self.deliver_due_reminders.start()

    @override
    async def cog_unload(self):
        """Ensure that tasks are cancelled on cog unload."""
        self.deliver_due_reminders.stop()

    async def send_reminder(self, reminder: Reminder) -> Message | None:
        """Sends a reminder."""
        user = self.client.get_user(reminder.user_id)
        # If we cannot find the user, don't even bother
        if user is None:
            return

        # Find channel, if it was set
        channel: MessageableGuildChannel | None = None
        if reminder.channel_id:
            chan = self.client.get_channel(reminder.channel_id)
            if chan:
                assert isinstance(chan, MessageableGuildChannelTuple)
                channel = chan

        # Create the messages
        embed = PidroidEmbed(
            title="Reminder",
            description=reminder.content
        ).add_field(name="Reminder created in", value=reminder.message_url)

        # Send out the messages
        # To the found channel, if allowed
        can_send_to_channel = channel and member_has_channel_permission(channel, channel.guild.me, Permissions.send_messages)
        if channel and can_send_to_channel:
            use_embed = member_has_channel_permission(channel, channel.guild.me, Permissions.embed_links)

            if use_embed:
                return await channel.send(content=f"{user.mention} reminder", embed=embed)

            return await channel.send(
                content=(
                    f"{user.mention} you asked to remind you {reminder.content!r} "
                    f"at {reminder.message_url}"
                )
            )

        # Or the user directly, if channel was not set
        return await user.send(embed=embed)


    @tasks.loop(seconds=15)
    async def deliver_due_reminders(self) -> None:
        """Periodically fetches and delivers due reminders."""
        try:
            async_session = self.client.api.session
            async with async_session() as session: 
                async with session.begin():
                    # Acquire every due reminder
                    result = await session.execute(
                        select(Reminder).
                        filter(Reminder.date_remind <= utcnow())
                    )

                    # Go over each reminder, send it
                    # and delete it from database
                    for reminder in result.scalars():
                        try:
                            _ = await self.send_reminder(reminder)
                        except Exception:
                            logger.exception("An exception was encountered while trying to send a due reminder")
                        await session.execute(
                            delete(Reminder).
                            filter(Reminder.id == reminder.id)
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
