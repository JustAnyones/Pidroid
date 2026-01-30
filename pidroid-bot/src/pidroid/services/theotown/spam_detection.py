import asyncio
import datetime
import logging

from collections import defaultdict
from discord import Member
from discord.ext import commands
from discord.message import Message
from typing import TypedDict, override

from pidroid.client import Pidroid
from pidroid.utils.aliases import MessageableGuildChannelTuple
from pidroid.utils.checks import is_guild_theotown
from pidroid.utils.time import utcnow

# Threshold for the number of same messages in different channels from the same user
# before they are considered spam.
CHANNEL_THRESHOLD = 3

# The amount of time to keep a message from a member tracked before it is removed from the tracking list.
KEEP_MESSAGE_TRACKED_FOR = 30 # seconds

class Infraction(TypedDict):
    channel_id: int
    message_id: int
    timestamp: datetime.datetime

# (user_id, message_content)
KEY = tuple[int, str]
# list of infractions
VALUE = list[Infraction] 

logger = logging.getLogger('pidroid.services.theotown.spam_detection')

class SpamDetectionService(commands.Cog):
    """
    This class implements a cog for handling of events related to spam detection.
    
    This is relatively simple spam detection that tracks messages sent by users
    across different channels in the Theotown server. If a user sends the same message
    in more than `CHANNEL_THRESHOLD` different channels, they are considered to be spamming and bot will issue a timeout.
    """
    def __init__(self, client: Pidroid):
        super().__init__()
        self.client = client
        # Dictionary to store message tracking
        self.message_tracker: dict[KEY, VALUE] = defaultdict(list)
        # Task to periodically clean up old messages from the tracker
        self.cleanup_task = self.client.loop.create_task(self._cleanup_messages())

    @override
    async def cog_unload(self):
        self.cleanup_task.cancel()

    async def _cleanup_messages(self):
        """
        Periodically cleans up old messages from the tracker.
        """
        while True:
            await asyncio.sleep(10) # Clean up every 10 seconds
            now = utcnow()

            keys_to_remove: list[KEY] = []
            for (user_id, message_content), entries in self.message_tracker.items():
                new_entries = [
                    entry.copy() for entry in entries
                    if (now - entry['timestamp']).total_seconds() < KEEP_MESSAGE_TRACKED_FOR
                ]
                if not new_entries:
                    keys_to_remove.append((user_id, message_content))
                else:
                    self.message_tracker[(user_id, message_content)] = new_entries

            for key in keys_to_remove:
                del self.message_tracker[key]

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot:
            return

        if not message.guild or not is_guild_theotown(message.guild):
            return

        # If the message content is empty after normalization (e.g., just an attachment), skip
        normalized_content = message.content.strip().lower()
        if not normalized_content:
            return
        
        assert isinstance(message.author, Member)

        user_id = message.author.id
        channel_id = message.channel.id
        message_id = message.id
        current_time = utcnow()

        # Add the current message to the tracker
        self.message_tracker[(user_id, normalized_content)].append({
            'channel_id': channel_id,
            'message_id': message_id,
            'timestamp': current_time
        })

        # Filter out old messages and count unique channels for the current message content
        unique_channels_for_message: set[int] = set()
        for infraction in self.message_tracker[(user_id, normalized_content)]:
            if (current_time - infraction['timestamp']).total_seconds() < KEEP_MESSAGE_TRACKED_FOR:
                unique_channels_for_message.add(infraction['channel_id'])

        # If the number of unique channels exceeds the threshold, it's spam
        if len(unique_channels_for_message) >= CHANNEL_THRESHOLD:
            member = message.author
            reason = f"Spamming the same message in {len(unique_channels_for_message)} channels."
            try:
                await member.timeout(utcnow() + datetime.timedelta(hours=24), reason=reason)

                # Delete the messages from the channels where the user spammed
                for infraction in self.message_tracker[(user_id, normalized_content)]:
                    channel = self.client.get_channel(infraction['channel_id'])
                    if not channel:
                        logger.warning(f"Channel {infraction['channel_id']} not found for user {user_id} in spam detection.")
                        continue
                    try:
                        assert isinstance(channel, MessageableGuildChannelTuple)
                        msg = channel.get_partial_message(infraction['message_id'])
                        await msg.delete(delay=0)
                    except Exception:
                        logger.exception(f"Failed to delete message {infraction['message_id']} in channel {channel.id}")

                # Clear the messages from the tracker for this user and content to prevent repeated timeouts
                del self.message_tracker[(user_id, normalized_content)]
            except Exception:
                logger.exception(f"An error occurred while timing out {member.display_name}")

async def setup(client: Pidroid) -> None:
    await client.add_cog(SpamDetectionService(client))
