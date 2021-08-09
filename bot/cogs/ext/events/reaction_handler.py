import discord

from contextlib import suppress
from discord.channel import TextChannel
from discord.ext import commands
from discord.message import Message
from discord.raw_models import RawReactionActionEvent

from client import Pidroid
from constants import JUSTANYONE_ID
from cogs.utils.checks import is_event_voter, is_event_manager, is_client_pidroid, is_guild_moderator, is_theotown_guild

class ReactionEventHandler(commands.Cog):
    """This class implements a cog for handling of events related to reactions."""
    def __init__(self, client: Pidroid):
        self.client = client

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if not is_client_pidroid(self.client):
            return

        if message.author.bot:
            return

        if message.guild and is_theotown_guild(message.guild):

            # Events auto reaction
            if message.channel.id == 371731826601099264:
                if not is_event_manager(message.author) and not is_guild_moderator(message.guild, message.channel, message.author):
                    if message.attachments:
                        await message.add_reaction(emoji="👍")
                    else:
                        await message.delete(delay=0)
                return

            # Spoilers auto reaction
            if message.channel.id == 416906073207996416:
                await message.add_reaction(emoji="<:bear_think:431390001721376770>")
                return

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        if not is_client_pidroid(self.client):
            return

        member: discord.Member = payload.member
        channel: TextChannel = self.client.get_channel(payload.channel_id)
        try:
            message: Message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        if not message:
            return

        emoji = str(payload.emoji)

        # Remove suggestions via reaction
        if channel.id == 409800607466258445 and member.id == JUSTANYONE_ID and emoji == "⛔":
            await message.delete(delay=0)
            return

        # Remove votes from unauthorised users in events channel
        if channel.id == 371731826601099264 and message.attachments and not member.bot and not is_event_voter(member) and member.id != message.author.id:
            with suppress(discord.NotFound):
                await message.remove_reaction("👍", member)


def setup(client: Pidroid) -> None:
    client.add_cog(ReactionEventHandler(client))
