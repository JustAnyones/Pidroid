import discord

from discord.channel import TextChannel
from discord.ext import commands
from discord.message import Message
from discord.raw_models import RawReactionActionEvent

from client import Pidroid
from constants import JUSTANYONE_ID, SPOILERS_CHANNEL, SUGGESTIONS_CHANNEL
from cogs.utils.checks import is_client_pidroid, is_guild_theotown

class ReactionEventHandler(commands.Cog): # type: ignore
    """This class implements a cog for handling of events related to reactions."""
    def __init__(self, client: Pidroid):
        self.client = client

    @commands.Cog.listener() # type: ignore
    async def on_message(self, message: Message):
        if not is_client_pidroid(self.client):
            return

        if message.author.bot:
            return

        if not message.guild or not is_guild_theotown(message.guild):
            return

        if message.channel.id == SPOILERS_CHANNEL:
            await message.add_reaction("<:bear_think:431390001721376770>")

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

        # Remove suggestions via reaction
        if channel.id == SUGGESTIONS_CHANNEL and payload.member.id == JUSTANYONE_ID and str(payload.emoji) == "⛔":
            await message.delete(delay=0)


async def setup(client: Pidroid) -> None:
    await client.add_cog(ReactionEventHandler(client))
