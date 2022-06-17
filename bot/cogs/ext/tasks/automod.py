import random
import re

from discord import Member
from discord.embeds import Embed
from discord.ext import commands
from discord.message import Message
from typing import Dict, List, Union
from urllib.parse import urlparse

from client import Pidroid
from constants import AUTOMODERATOR_RESPONSES
from cogs.models.case import Kick
from cogs.models.configuration import GuildConfiguration
from cogs.utils.logger import BannedWordLog, PhisingLog, SuspiciousUserLog
from cogs.utils.time import utcnow
from cogs.utils.checks import is_guild_moderator


def find_swearing(string: str, banned_words: List[str]) -> Union[str, None]:
    """Returns a word which was found to be a swear in a string."""
    for word in string.split():
        if word in banned_words:
            return word
    return None

def clean_markdown(message_content: str) -> str:
    """Returns a string stripped of any markdown."""
    return re.sub(r"[^a-zA-Z0-9\s]", "", message_content) # Did I ever tell you how much I hate regex?


class AutomodTask(commands.Cog): # type: ignore
    """This class implements a cog for handling automatic moderation of the TheoTown guild."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.automod_violations: Dict[int, Dict[int, dict]] = {}
        self.phising_urls: List[str] = []

    async def _update_phising_urls(self):
        """Updates internal phishing url list."""
        urls = await self.client.api.fetch_phising_url_list()
        self.client.logger.info("Updated phishing url list")
        self.phising_urls = urls

    async def count_violation(self, message: Message):
        guild_id = message.guild.id
        member_id = message.author.id
        # Set default values if data doesn't exist
        self.automod_violations.setdefault(guild_id, {})
        self.automod_violations[guild_id].setdefault(
            member_id,
            {"last_violation": utcnow().timestamp(), "count": 0}
        )

        member_data = self.automod_violations[guild_id][member_id]
        if member_data["count"] > 3:
            if (utcnow().timestamp() - member_data["last_violation"]) < 60 * 5:
                k = Kick()
                k._fill(self.client.api, message.guild, None, self.client.user, message.author) # type: ignore
                k.reason = "Phishing automod violation limit exceeded"
                await k.issue()
            del self.automod_violations[guild_id][member_id]
            return

        member_data["last_violation"] = utcnow().timestamp()
        member_data["count"] += 1

    async def punish_phising(self, message: Message, trigger_url: str = None):
        assert message.guild is not None
        await self.client.dispatch_log(message.guild, PhisingLog(message, trigger_url))
        await message.delete(delay=0)
        config = self.client.get_guild_configuration(message.guild.id)
        if config is not None:
            if config.strict_anti_phising:
                await self.count_violation(message)

    async def handle_banned_words(self, config: GuildConfiguration, message: Message) -> None:
        """Handles the detection and removal of banned words."""
        content = clean_markdown(message.clean_content.lower())
        word = find_swearing(content, config.banned_exact_words)
        if word is not None:
            assert message.guild is not None
            await self.client.dispatch_log(message.guild, BannedWordLog(message, word))
            await message.delete(delay=0)
            await message.channel.send(random.choice(AUTOMODERATOR_RESPONSES).replace('%user%', message.author.mention), delete_after=3.5) # nosec

    async def handle_phising(self, message: Message) -> bool:
        """Handles the detection and filtering of phising messages."""
        # URL based phising in plain message
        for url in self.phising_urls:
            if url in message.content:
                await self.punish_phising(message, url)
                return True

        # Phising related to embedded content
        if len(message.embeds) > 0:
            # Only scan link embeds which attempt to fake discord gift embed
            link_type_embeds: List[Embed] = [e for e in message.embeds if e.type == "link"]
            for link_embed in link_type_embeds:
                try:
                    if "nitro" in link_embed.title.lower() and "a wild gift appears" in link_embed.provider.name.lower():
                        url = urlparse(link_embed.url.lower())
                        if url.netloc != "discord.gift":
                            await self.punish_phising(message)
                            return True
                except AttributeError:
                    pass
        return False

    async def handle_suspicious_member(self, config: GuildConfiguration, member: Member) -> bool:
        """Handles the detection of members which are deemed suspicious."""
        for trigger_word in config.suspicious_users:
            if trigger_word in member.name.lower():
                await self.client.dispatch_log(member.guild, SuspiciousUserLog(member, trigger_word))
                return True
        return False

    @commands.Cog.listener() # type: ignore
    async def on_member_join(self, member: Member) -> None:
        """Checks whether new member is suspicious."""
        if member.bot:
            return

        await self.client.wait_guild_config_cache_ready()
        config = self.client.get_guild_configuration(member.guild.id)
        if config is None:
            return

        await self.handle_suspicious_member(config, member)

    @commands.Cog.listener() # type: ignore
    async def on_message(self, message: Message) -> None:
        """Checks every new message if it contains phising or swearing."""
        if message.author.bot:
            return

        if message.guild is None:
            return

        await self.client.wait_guild_config_cache_ready()
        config = self.client.get_guild_configuration(message.guild.id)
        if config is None:
            return

        if is_guild_moderator(message.guild, message.channel, message.author):
            return

        punished = await self.handle_phising(message)
        if not punished:
            await self.handle_banned_words(config, message)


async def setup(client: Pidroid) -> None:
    await client.add_cog(AutomodTask(client))
