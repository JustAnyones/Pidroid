import discord

from contextlib import suppress
from discord.channel import TextChannel
from discord.ext import commands
from discord.message import Message
from discord.raw_models import RawReactionActionEvent

from client import Pidroid
from constants import EVENTS_CHANNEL
from cogs.utils.checks import TheoTownChecks as TTChecks, is_client_pidroid, is_guild_moderator, is_guild_theotown

class EventChannelHandler(commands.Cog): # type: ignore
    """This class implements a cog for handling of events related to the event channel."""
    def __init__(self, client: Pidroid):
        self.client = client

    @commands.Cog.listener() # type: ignore
    async def on_message(self, message: Message):
        if not is_client_pidroid(self.client):
            return

        if message.author.bot:
            return

        if not is_guild_theotown(message.guild):
            return
        assert message.guild is not None
        assert message.channel is not None

        if isinstance(message.author, discord.User):
            return

        if message.channel.id == EVENTS_CHANNEL:

            if not TTChecks.is_event_manager(message.author) and not is_guild_moderator(message.guild, message.channel, message.author):
                if message.attachments:
                    await message.add_reaction("👍")
                    return

                await message.delete(delay=0)

    @commands.Cog.listener() # type: ignore
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        if not is_client_pidroid(self.client):
            return

        if not payload.member:
            return

        channel: TextChannel = self.client.get_channel(payload.channel_id)
        try:
            message: Message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        if not message:
            return

        # Ignore if outside of events channel
        if channel.id != EVENTS_CHANNEL:
            return

        # Remove votes from unauthorised users in events channel
        if message.attachments and not payload.member.bot and (not TTChecks.is_event_voter(payload.member) or payload.member.id == message.author.id):
            with suppress(discord.NotFound):
                await message.remove_reaction("👍", payload.member)


async def setup(client: Pidroid) -> None:
    await client.add_cog(EventChannelHandler(client))
