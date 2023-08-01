import discord
import logging

from contextlib import suppress
from discord import ForumChannel, Member, Thread, User
from discord.ext import commands
from discord.message import Message
from discord.raw_models import RawReactionActionEvent

from pidroid.client import Pidroid
from pidroid.constants import THEOTOWN_GUILD
from pidroid.utils import try_message_user
from pidroid.utils.checks import TheoTownChecks as TTChecks, is_guild_moderator, is_guild_theotown

EVENTS_CHANNEL_ID = 371731826601099264
EVENTS_FORUM_CHANNEL_ID = 1085224525924417617

logger = logging.getLogger('Pidroid')

def is_message_in_events_forum(message: Message) -> bool:
    """Returns true if the message belongs to a events forum channel thread."""
    if message.guild is None:
        return False

    if message.author.bot:
        return False

    if not is_guild_theotown(message.guild):
        return False

    # If channel doesn't have a parent attribute
    if not hasattr(message.channel, 'parent'):
        return False

    # Check if that thread has a parent
    if isinstance(message.channel, Thread):
        return is_thread_part_of_events_forum(message.channel)
    return False

def is_thread_part_of_events_forum(thread: Thread) -> bool:
    """Returns true if thread is part of the events forum."""
    if thread.parent is None:
        return False
    return thread.parent.id == EVENTS_FORUM_CHANNEL_ID

def can_member_participate(member: Member) -> bool:
    """Returns true if member can participate in the event."""
    if TTChecks.is_event_manager(member) or is_guild_moderator(member):
        return False
    return True

def can_member_vote_on_message(member: Member, message: Message) -> bool:
    """Returns true if member can vote on the event submission message."""
    return (
        TTChecks.is_event_voter(member)
        and member.id != message.author.id
    )

class EventChannelHandler(commands.Cog): # type: ignore
    """This class implements a cog for handling of events related to the event channel."""
    def __init__(self, client: Pidroid):
        self.client = client

    @commands.Cog.listener() # type: ignore
    async def on_ready(self) -> None:
        """Called when bot is ready.
        
        This task updates reactions of last 200 messages in the events channel."""
        guild = self.client.get_guild(THEOTOWN_GUILD)
        if guild is None:
            return logger.warning("Could not locate TheoTown guild when updating reactions.")
        
        forum_channel = guild.get_channel(EVENTS_FORUM_CHANNEL_ID)
        if forum_channel is None:
            return logger.warning(
                "Could not locate the events forum channel inside TheoTown guild when updating reactions."
            )
        
        assert isinstance(forum_channel, ForumChannel)
        
        # Go over each post 
        for thread in forum_channel.threads:
            # If thread is locked, don't touch it
            if thread.locked:
                continue
            
            # Go over the last 200 messages in the thread
            async for message in thread.history(limit=200):
                # Check if message has attachments
                if not message.attachments:
                    pass

                # If it does, go over each reaction until it meets a thumbs up
                for reaction in message.reactions:
                    if reaction.emoji == "👍":
                        # Get every single user who reacted with thumbs up
                        async for user in reaction.users():
                            
                            # If user is a bot, ignore them
                            if user.bot:
                                continue

                            if isinstance(user, User):
                                can_vote = False
                            else:
                                can_vote = can_member_vote_on_message(user, message)

                            if not can_vote:
                                with suppress(Exception):
                                    await reaction.remove(user)
                        # Don't search any further
                        break
                

    @commands.Cog.listener() # type: ignore
    async def on_message(self, message: Message):
        """Add reactions to new messages in the events forum channel."""
        if not is_message_in_events_forum(message):
            return

        assert isinstance(message.author, Member)

        if can_member_participate(message.author):
            if message.attachments:
                return await message.add_reaction("👍")
            else:
                assert isinstance(message, (ForumChannel, Thread))
                await try_message_user(
                    message.author,
                    content=(
                        f"Your message in {message.channel.mention} was removed automatically "
                        "because it did not have any attachments"
                    )
                )
                await message.delete(delay=0)

    @commands.Cog.listener() # type: ignore
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        """Removes reactions from users which are not allowed to vote on submissions."""
        
        # If we don't have a member payload, ignore it
        if payload.member is None:
            return
        
        # If we don't have a guild ID, ignore it
        if payload.guild_id is None:
            return
        
        # If we don't get the guild
        guild = self.client.get_guild(payload.guild_id)
        if guild is None:
            return
        
        # If it's not TheoTown guild
        if guild.id != THEOTOWN_GUILD:
            return
        
        # If we don't get an actual thread
        thread = guild.get_thread(payload.channel_id)
        if thread is None:
            return
        
        # If thread is not part of the events forum
        if not is_thread_part_of_events_forum(thread):
            return

        # Obtain the message
        try:
            message = await thread.fetch_message(payload.message_id)
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
