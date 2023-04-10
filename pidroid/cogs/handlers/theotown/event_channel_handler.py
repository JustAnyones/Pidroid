import discord

from contextlib import suppress
from discord.channel import TextChannel
from discord.ext import commands
from discord.message import Message
from discord.raw_models import RawReactionActionEvent

from pidroid.client import Pidroid
from pidroid.utils.checks import TheoTownChecks as TTChecks, is_guild_moderator, is_guild_theotown

EVENTS_CHANNEL_ID = 371731826601099264
EVENTS_FORUM_CHANNEL_ID = 1085224525924417617

class EventChannelHandler(commands.Cog): # type: ignore
    """This class implements a cog for handling of events related to the event channel."""
    def __init__(self, client: Pidroid):
        self.client = client

    def is_in_events_forum_channel(self, message: Message) -> bool:
        """Returns true if the message belongs inside a events forum channel."""
        if message.guild is None:
            return False

        if message.author.bot:
            return False

        if not is_guild_theotown(message.guild):
            return False

        if not hasattr(message.channel, 'parent'):
            return False

        parent = message.channel.parent
        if parent is None:
            return False

        return parent.id == EVENTS_FORUM_CHANNEL_ID

    @commands.Cog.listener() # type: ignore
    async def on_message(self, message: Message):
        """Add reactions to new messages in the events channel."""
        if message.author.bot:
            return

        if not is_guild_theotown(message.guild):
            return

        assert message.guild is not None
        assert message.channel is not None

        if message.channel.id != EVENTS_CHANNEL_ID:
            return

        if isinstance(message.author, discord.User):
            return

        if not TTChecks.is_event_manager(message.author) and not is_guild_moderator(message.author):
            if message.attachments:
                return await message.add_reaction("👍")

            await message.delete(delay=0)

    #@commands.Cog.listener() # type: ignore
    #async def on_message2(self, message: Message):
    #    """Add reactions to new messages in the events forum channel."""
    #    if not self.is_in_events_forum_channel(message):
    #        return

    #    assert isinstance(message.author, discord.Member)

    #    # Disallow event managers and guild moderators to participate
    #    if not (TTChecks.is_event_manager(message.author) or is_guild_moderator(message.author)):
    #        if message.attachments:
    #            return await message.add_reaction("👍")

    #        await message.delete(delay=0)

    @commands.Cog.listener() # type: ignore
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        """Removes reactions from users which are not allowed to vote on submissions."""
        if not payload.member:
            return

        # Ignore if outside of events channel
        if payload.channel_id != EVENTS_CHANNEL_ID:
            return

        channel = await self.client.get_or_fetch_channel(payload.channel_id)
        if not isinstance(channel, TextChannel):
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        if not message:
            return

        can_vote = (
            TTChecks.is_event_voter(payload.member)
            and payload.member.id != message.author.id
        )

        # Remove votes from unauthorised users in events channel
        # If message has attachments, the reaction is not made by a bot
        # and if the member cannot vote
        if message.attachments and not payload.member.bot and not can_vote:
            with suppress(discord.NotFound):
                await message.remove_reaction("👍", payload.member) # type: ignore


async def setup(client: Pidroid) -> None:
    await client.add_cog(EventChannelHandler(client))
