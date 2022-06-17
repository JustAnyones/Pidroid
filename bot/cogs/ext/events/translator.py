import asyncio
import base64
import emoji # type: ignore # I am not updating the emoji regex myself every time there's a new one
import re

from contextlib import suppress
from discord.ext import commands # type: ignore
from discord.channel import TextChannel
from discord.utils import remove_markdown
from discord.message import Message
from typing import List, Optional, Tuple

from client import Pidroid
from cogs.utils.checks import is_client_pidroid
from cogs.utils.embeds import PidroidEmbed
from cogs.utils.http import post
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
    "ZH": "Chinese",
    "ID": "Indonesian",
    "TR": "Turkish"
}

FEED_CHANNEL = 943920969637040140
SOURCE_CHANNEL = 692830641728782336

CUSTOM_EMOJI_PATTERN = re.compile(r'<(a:.+?:\d+|:.+?:\d+)>')
URL_PATTERN = re.compile(r'(https?:\/\/)(\s)*(www\.)?(\s)*((\w|\s)+\.)*([\w\-\s]+\/)*([\w\-]+)((\?)?[\w\s]*=\s*[\w\%&]*)*')
BASE64_PATTERN = re.compile(r'^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)?$')

def remove_emojis(string: str) -> str:
    """Removes all emojis from a string."""
    stripped = re.sub(CUSTOM_EMOJI_PATTERN, "", string)
    return emoji.get_emoji_regexp().sub("", stripped)

def remove_urls(string: str) -> str:
    """Removes URLs from a string."""
    return re.sub(URL_PATTERN, "", string)

class ParserFlags:
    NORMAL     = 1 << 0 # noqa
    LOWERCASED = 1 << 1
    BASE64     = 1 << 2 # noqa
    BYPASSED   = 1 << 3 # noqa
    FAIL       = 1 << 4 # noqa


FLAG_FOOTERS = {
    ParserFlags.LOWERCASED: "Text has been lowercased",
    ParserFlags.BASE64: "Text has been converted from base64",
    ParserFlags.FAIL: "Failed parsing a base64 string"
}

class TextParser:
    def __init__(self, text: str, remove_markdown: bool = True) -> None:
        self.original = text
        self.remove_markdown = remove_markdown

    @property
    def text(self) -> str:
        if self.remove_markdown:
            return remove_markdown(self.original).strip()
        return self.original

    @property
    def stripped_text(self) -> str:
        string = remove_emojis(self.text).strip()
        return remove_urls(string).strip()

    @property
    def should_translate(self) -> bool:
        return len(self.stripped_text) > 0

    def get_parsed_text(self) -> Tuple[int, Optional[str]]:
        # If string is base64
        if re.match(BASE64_PATTERN, self.text):
            try:
                decoded_string = base64.b64decode(self.text).decode("utf-8")
            except UnicodeDecodeError:
                return ParserFlags.BASE64, None
            return ParserFlags.BASE64, decoded_string

        # If 30% of all characters are uppercase, lowercase the entire string
        #print("Value of capitalized letters in string", sum(1 for c in self.text if c.isupper()) / len(self.text))
        if not self.text.isupper() and sum(1 for c in self.text if c.isupper()) / len(self.text) >= 0.30:
            return ParserFlags.LOWERCASED, self.text.lower()

        # Otherwise, just return normal string
        return ParserFlags.NORMAL, self.text

class TranslationEventHandler(commands.Cog): # type: ignore
    """This class implements a cog for event handling related to TheoTown translations."""

    def __init__(self, client: Pidroid):
        self.client = client
        self.endpoint = "https://api.deepl.com/v2"
        self.auth_key = self.client.config["authentication"].get("deepl key", None)

        self._translating = asyncio.Event()
        self._translating.set()

        self.daily_char_limit = 50000
        self.used_chars = 0
        self.last_reset = utcnow()

        self.channel: Optional[TextChannel] = None

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

    async def translate_message(self, message: Message, clean_text: str) -> List[dict]:
        # Await previous translation jobs to finish
        await self._translating.wait()

        # Check if daily limit is not reached, if it is, stop translating
        if len(clean_text) + self.used_chars > self.daily_char_limit:
            self.client.logger.critical("Failure translating encountered, the daily character limit was exceeded")
            return []
        self.used_chars += len(clean_text)

        # Check if text was already translated
        c_key = clean_text.lower()
        translations = await self.client.api.fetch_translation(c_key)
        if len(translations) == 0:
            translations = await self.translate(clean_text)
            await self.client.api.insert_new_translation(c_key, translations)

        # If message could not be translated, log it as a warning
        if len(translations) == 0:
            self.client.logger.warning(f"Unable to translate '{message.clean_content}'")

        return translations

    @commands.Cog.listener() # type: ignore
    async def on_message(self, message: Message):
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
        await self.handle(message)

    async def handle(self, message: Message):
        parser = TextParser(message.clean_content)
        translations = []
        flag = ParserFlags.BYPASSED
        if parser.should_translate:
            flag, text = parser.get_parsed_text()
            if text is None and flag == ParserFlags.FAIL:
                self.client.logger.warn(f"Failed parsing of base64 text for '{parser.text}'")
                text = parser.text
                flag = ParserFlags.FAIL
            translations = await self.translate_message(message, text)
        await self.dispatch_translation(message, translations, flag)

    async def dispatch_translation(self, message: Message, translations: List[dict], flag: int) -> None: # noqa C901
        # If message contains a reply, track down the reference author
        action = None
        if message.reference:
            with suppress(Exception):
                reference = await message.channel.fetch_message(message.reference.message_id)
                action = f"Replying to {str(reference.author)}"

        # Create a rich message description from stickers
        rich_description = ""
        for sticker in message.stickers:
            rich_description += f"[Sticker {sticker.name}]\n"

        attachments = [a.url for a in message.attachments]

        if flag == ParserFlags.BYPASSED:
            embeds = [PidroidEmbed(description=message.clean_content)]
        else:
            embeds = []
            for translation in translations:
                text: str = translation["text"]
                detected_lang: str = translation["detected_source_language"]
                embed = PidroidEmbed(description=text)
                embed.set_footer(text=f"Detected source language: {LANGUAGE_MAPPING.get(detected_lang, detected_lang)}")
                embeds.append(embed)

        # Go over each embed and set author values or other stuff
        for embed in embeds:
            embed.set_author(name=str(message.author), url=message.jump_url, icon_url=message.author.display_avatar)

            # Set action as title, like replying
            if action is not None:
                embed.title = action

            # Insert rich description
            if len(rich_description) > 0:
                embed.description += "\n--\n" + rich_description

            # Add attachments if they exist
            if len(attachments) > 0:
                embed.add_field(name="Attachments", value='\n'.join(attachments), inline=False)

            # Notify of any modifications done to the original string
            if flag == ParserFlags.BYPASSED:
                embed.set_footer(text="Translation layer bypassed as nothing translatable was found")
            else:
                footer = FLAG_FOOTERS.get(flag)
                if footer is not None:
                    embed.set_footer(text=f"{footer} | {embed.footer.text}")

        await self.channel.send(embeds=embeds)

async def setup(client: Pidroid) -> None:
    await client.add_cog(TranslationEventHandler(client))
