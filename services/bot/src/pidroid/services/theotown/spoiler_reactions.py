from discord.ext import commands
from discord.message import Message

from pidroid.client import Pidroid
from pidroid.utils.checks import is_guild_theotown

SPOILERS_CHANNEL_ID = 416906073207996416

class SpoilerReactionService(commands.Cog):
    """This class implements a cog for handling of events related to reactions."""
    def __init__(self, client: Pidroid):
        super().__init__()
        self.client = client

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot:
            return

        if not message.guild or not is_guild_theotown(message.guild):
            return

        if message.channel.id == SPOILERS_CHANNEL_ID:
            await message.add_reaction("<:bear_think:431390001721376770>")

async def setup(client: Pidroid) -> None:
    await client.add_cog(SpoilerReactionService(client))
