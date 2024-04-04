import discord

from discord.channel import TextChannel
from discord.ext import commands # type: ignore
from discord.message import Message
from discord.raw_models import RawReactionActionEvent

from pidroid.client import Pidroid
from pidroid.constants import JUSTANYONE_ID

SUGGESTIONS_CHANNEL_ID = 409800607466258445

class SuggestionDeletionService(commands.Cog):
    """This class implements a cog for handling of events related to reactions."""
    def __init__(self, client: Pidroid):
        self.client = client

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        """Lgeacy way of removing suggestions based on the reaction, to be removed eventually.
        
        This is left as backwards compatibility."""
        if not payload.member:
            return

        channel = await self.client.get_or_fetch_channel(payload.channel_id)
        if not isinstance(channel, TextChannel):
            return
        
        try:
            message: Message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        if not message:
            return

        # Remove suggestions via reaction
        if channel.id == SUGGESTIONS_CHANNEL_ID and payload.member.id == JUSTANYONE_ID and str(payload.emoji) == "⛔":
            await message.delete(delay=0)


async def setup(client: Pidroid) -> None:
    await client.add_cog(SuggestionDeletionService(client))
