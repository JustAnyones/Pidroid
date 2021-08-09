from discord.ext import commands
from discord.message import Message

from client import Pidroid
from constants import JUSTANYONE_ID
from cogs.utils.checks import is_client_pidroid
from cogs.utils.embeds import build_embed

class MessageForwadingEvent(commands.Cog):
    """This class implements a cog for bot's DM forwarding to a hidden DM channel."""

    def __init__(self, client: Pidroid):
        self.client = client

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if not is_client_pidroid(self.client):
            return

        if message.author.bot:
            return

        if message.guild is None and message.author.id != JUSTANYONE_ID:
            dm_channel = self.client.get_channel(707561286820692039)
            embed = build_embed()

            if message.content:
                embed.add_field(name="Message", value=message.content, inline=False)
                if message.attachments:
                    string = ""
                    for attachment in message.attachments:
                        hyperlink = f"[{attachment.filename}]({attachment.url})"
                        string = string + "\n" + hyperlink
                    embed.add_field(name="Attachments", value=string, inline=False)

                embed.set_thumbnail(url=message.author.avatar.url)
                embed.set_author(name=f'{message.author.name}#{message.author.discriminator}', icon_url=message.author.avatar.url)
                embed.set_footer(text=f"User ID: {message.author.id}")
                await dm_channel.send(embed=embed)


def setup(client: Pidroid) -> None:
    client.add_cog(MessageForwadingEvent(client))
