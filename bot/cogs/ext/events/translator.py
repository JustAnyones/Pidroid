import asyncio
import json
import os

from typing import List
from discord.ext import commands
from discord.channel import TextChannel
from discord.utils import remove_markdown
from discord.message import Message

from client import Pidroid
from cogs.utils.checks import is_client_pidroid
from cogs.utils.http import post
from cogs.utils.embeds import create_embed
from cogs.utils.time import utcnow

# https://www.deepl.com/docs-api/translating-text/request/
LANGUAGE_MAPPING = {
    "BG": "Bulgarian",
    "CS": "Czech",
    "DA": "Danish",
    "DE": "German",
    "EL": "Greek",
    "EN": "English",
    "ES": "Spanish",
    "ET": "Estonian",
    "FI": "Finnish",
    "FR": "French",
    "HU": "Hungarian",
    "IT": "Italian",
    "JA": "Japanese",
    "LT": "Lithuanian",
    "LV": "Latvian",
    "NL": "Dutch",
    "PL": "Polish",
    "PT": "Portuguese",
    "RO": "Romanian",
    "RU": "Russian",
    "SK": "Slovak",
    "SL": "Slovenian",
    "SV": "Swedish",
    "ZH": "Chinese"
}

CACHE_FILE_PATH = "./data/translation_cache.json"
FEED_CHANNEL = 943920969637040140
SOURCE_CHANNEL = 692830641728782336

class TranslationEventHandler(commands.Cog):
    """This class implements a cog for event handling related to TheoTown translations."""

    def __init__(self, client: Pidroid):
        self.client = client
        self.endpoint = "https://api.deepl.com/v2"
        self.auth_key = self.client.config["authentication"].get("deepl key", None)

        self.translation_cache = {}

        self._translating = asyncio.Event()
        self._translating.set()

        self.daily_char_limit = 50000
        self.used_chars = 0
        self.last_reset = utcnow()

        self.channel: TextChannel = None

        if os.path.exists(CACHE_FILE_PATH):
            self.client.logger.info("Loading translation into cache")
            with open(CACHE_FILE_PATH, "r") as f:
                self.translation_cache = json.load(f)

    def cog_unload(self):
        self.client.logger.info("Saving translation cache")
        with open(CACHE_FILE_PATH, "w") as f:
            json.dump(self.translation_cache, f)

    async def translate(self, text: str) -> List[dict]:
        self._translating.clear()
        try:
            async with await post(self.client, self.endpoint + "/translate", {
                "auth_key": self.auth_key,
                "text": text,
                "target_lang": "EN"
            }) as r:
                data = await r.json()
        except Exception as e:
            self.client.logger.critical("Failure while translating:", e)
            self._translating.set()
            return []
        self._translating.set()
        return data["translations"]

    async def get_usage(self) -> dict:
        async with await post(self.client, self.endpoint + "/usage", {
            "auth_key": self.auth_key
        }) as r:
            data = await r.json()
        return data

    def is_valid(self, message: Message) -> bool:
        return (
            is_client_pidroid(self.client)
            and self.auth_key is not None
            and message.guild
            and not message.author.bot
            and message.channel.id == SOURCE_CHANNEL
        )

    @commands.Cog.listener()
    async def on_message(self, message: Message): # noqa C901
        # Check whether message is valid for further processing
        if not self.is_valid(message):
            return

        # Try to cache the channel object
        if self.channel is None:
            self.channel = await self.client.get_or_fetch_channel(message.guild, FEED_CHANNEL)

        # Reset used chars counter
        if utcnow().timestamp() - self.last_reset.timestamp() > 60 * 60 * 24:
            self.used_chars = 0
            self.last_reset = utcnow()

        # Await translation job to finish
        await self._translating.wait()

        raw_text = remove_markdown(message.clean_content).strip()

        if len(raw_text) + self.used_chars > self.daily_char_limit:
            self.client.logger.critical("Failure translating encountered, the daily character limit was exceeded")
            return
        self.used_chars += len(raw_text)

        c_key = raw_text.lower()
        if self.translation_cache.get(c_key, None) is None:
            self.translation_cache[c_key] = await self.translate(raw_text)
        translations = self.translation_cache[c_key]

        if len(translations) == 0:
            self.client.logger.warning(f"Unable to translate '{message.clean_content}'")
            return

        translation = translations[0]
        translated = translation["text"]
        source_lang = translation["detected_source_language"]

        embed = create_embed(description=translated)
        embed.set_author(name=str(message.author), url=message.jump_url, icon_url=message.author.display_avatar)
        embed.set_footer(text=f"Detected source language: {LANGUAGE_MAPPING.get(source_lang, source_lang)}")

        await self.channel.send(embed=embed)

def setup(client: Pidroid) -> None:
    client.add_cog(TranslationEventHandler(client))
