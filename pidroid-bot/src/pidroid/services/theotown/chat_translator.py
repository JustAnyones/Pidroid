import asyncio
import emoji # I am not updating the emoji regex myself every time there's a new one
import re
import logging

from contextlib import suppress
from discord import Embed
from discord.ext import commands
from discord.channel import TextChannel
from discord.utils import remove_markdown
from discord.message import Message
from typing import TypedDict

from pidroid.client import Pidroid
from pidroid.models.translation import TranslationEntryDict
from pidroid.utils.embeds import PidroidEmbed
from pidroid.utils.http import post
from pidroid.utils.time import utcnow

class TranslateApiResponseDict(TypedDict):
    translations: list[TranslationEntryDict]

# https://developers.deepl.com/docs/getting-started/supported-languages#translation-target-languages
LANGUAGE_MAPPING = {
    "ACE": "Acehnese",
    "AF": "Afrikaans",
    "AN": "Aragonese",
    "AR": "Arabic",
    "AS": "Assamese",
    "AY": "Aymara",
    "AZ": "Azerbaijani",
    "BA": "Bashkir",
    "BE": "Belarusian",
    "BG": "Bulgarian",
    "BHO": "Bhojpuri",
    "BN": "Bengali",
    "BR": "Breton",
    "BS": "Bosnian",
    "CA": "Catalan",
    "CEB": "Cebuano",
    "CKB": "Kurdish (Sorani)",
    "CS": "Czech",
    "CY": "Welsh",
    "DA": "Danish",
    "DE": "German",
    "EL": "Greek",
    "EN": "English",
    "EO": "Esperanto",
    "ES": "Spanish",
    "ET": "Estonian",
    "EU": "Basque",
    "FA": "Persian",
    "FI": "Finnish",
    "FR": "French",
    "GA": "Irish",
    "GL": "Galician",
    "GN": "Guarani",
    "GOM": "Konkani",
    "GU": "Gujarati",
    "HA": "Hausa",
    "HE": "Hebrew",
    "HI": "Hindi",
    "HR": "Croatian",
    "HT": "Haitian Creole",
    "HU": "Hungarian",
    "HY": "Armenian",
    "ID": "Indonesian",
    "IG": "Igbo",
    "IS": "Icelandic",
    "IT": "Italian",
    "JA": "Japanese",
    "JV": "Javanese",
    "KA": "Georgian",
    "KK": "Kazakh",
    "KMR": "Kurdish (Kurmanji)",
    "KO": "Korean",
    "KY": "Kyrgyz",
    "LA": "Latin",
    "LB": "Luxembourgish",
    "LMO": "Lombard",
    "LN": "Lingala",
    "LT": "Lithuanian",
    "LV": "Latvian",
    "MAI": "Maithili",
    "MG": "Malagasy",
    "MI": "Maori",
    "MK": "Macedonian",
    "ML": "Malayalam",
    "MN": "Mongolian",
    "MR": "Marathi",
    "MS": "Malay",
    "MT": "Maltese",
    "MY": "Burmese",
    "NB": "Norwegian (Bokmål)",
    "NE": "Nepali",
    "NL": "Dutch",
    "OC": "Occitan",
    "OM": "Oromo",
    "PA": "Punjabi",
    "PAG": "Pangasinan",
    "PAM": "Kapampangan",
    "PL": "Polish",
    "PRS": "Dari",
    "PS": "Pashto",
    "PT": "Portuguese",
    "QU": "Quechua",
    "RO": "Romanian",
    "RU": "Russian",
    "SA": "Sanskrit",
    "SCN": "Sicilian",
    "SK": "Slovak",
    "SL": "Slovenian",
    "SQ": "Albanian",
    "SR": "Serbian",
    "ST": "Sesotho",
    "SU": "Sundanese",
    "SV": "Swedish",
    "SW": "Swahili",
    "TA": "Tamil",
    "TE": "Telugu",
    "TG": "Tajik",
    "TH": "Thai",
    "TK": "Turkmen",
    "TL": "Tagalog",
    "TN": "Tswana",
    "TR": "Turkish",
    "TS": "Tsonga",
    "TT": "Tatar",
    "UK": "Ukrainian",
    "UR": "Urdu",
    "UZ": "Uzbek",
    "VI": "Vietnamese",
    "WO": "Wolof",
    "XH": "Xhosa",
    "YI": "Yiddish",
    "YUE": "Cantonese",
    "ZH": "Chinese",
    "ZU": "Zulu"
}

FEED_CHANNEL_ID = 943920969637040140
SOURCE_CHANNEL_ID = 692830641728782336

CUSTOM_EMOJI_PATTERN = re.compile(r'<(a:.+?:\d+|:.+?:\d+)>')
URL_PATTERN = re.compile(r'(https?:\/\/)(\s)*(www\.)?(\s)*((\w|\s)+\.)*([\w\-\s]+\/)*([\w\-]+)((\?)?[\w\s]*=\s*[\w\%&]*)*')
BASE64_PATTERN = re.compile(r'^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)?$')

logger = logging.getLogger("pidroid.services.theotown.chat_translator")

def remove_emojis(string: str) -> str:
    """Removes all emojis from a string."""
    stripped = re.sub(CUSTOM_EMOJI_PATTERN, "", string)
    return emoji.replace_emoji(stripped, '')

def remove_urls(string: str) -> str:
    """Removes URLs from a string."""
    return re.sub(URL_PATTERN, "", string)

class ParserFlags:
    NORMAL     = 1 << 0 # noqa
    LOWERCASED = 1 << 1
    BYPASSED   = 1 << 3 # noqa
    FAIL       = 1 << 4 # noqa


FLAG_FOOTERS = {
    ParserFlags.LOWERCASED: "Text has been lowercased",
    ParserFlags.FAIL: "Failed parsing a supposed base64 string"
}

class TextParser:
    def __init__(self, text: str, remove_markdown: bool = True) -> None:
        super().__init__()
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

    def get_parsed_text(self) -> tuple[int, str]:
        # If 50% of all characters are uppercase, lowercase the entire string
        #print("Value of capitalized letters in string", sum(1 for c in self.text if c.isupper()) / len(self.text))
        if not self.text.isupper() and sum(1 for c in self.text if c.isupper()) / len(self.text) >= 0.50:
            return ParserFlags.LOWERCASED, self.text.lower()

        # Otherwise, just return normal string
        return ParserFlags.NORMAL, self.text

class ChatTranslationService(commands.Cog):
    """This class implements a cog for handling TheoTown guild chat translations."""

    def __init__(self, client: Pidroid):
        super().__init__()
        self.client: Pidroid = client
        self.endpoint: str = "https://api.deepl.com/v2"
        self.auth_key = self.client.config.get("deepl_api_key", None)

        self._translating = asyncio.Event()
        self._translating.set()

        self.daily_char_limit: int = 100_000
        self.used_chars: int = 0
        self.last_reset = utcnow()

    async def translate(self, text: str) -> list[TranslationEntryDict]:
        self._translating.clear()
        try:
            async with await post(self.client, self.endpoint + "/translate", {
                "text": [text],
                "target_lang": "EN"
            },headers={
                "Authorization": f"DeepL-Auth-Key {self.auth_key}"
            }) as r:
                data: TranslateApiResponseDict = await r.json()
        except Exception as e:
            logger.critical(f"Failure while translating: {text}")
            logger.exception(e)
            self._translating.set()
            return []
        self._translating.set()
        return data["translations"]

    def is_valid(self, message: Message) -> bool:
        return (
            self.auth_key is not None
            and message.guild is not None
            and not message.author.bot
            and message.channel.id == SOURCE_CHANNEL_ID
        )

    async def translate_message(self, message: Message, clean_text: str) -> list[TranslationEntryDict]:
        # Await previous translation jobs to finish
        _ = await self._translating.wait()

        # Check if daily limit is not reached, if it is, stop translating
        if len(clean_text) + self.used_chars > self.daily_char_limit:
            logger.warning("Failure translating encountered, the daily character limit was exceeded")
            return []
        self.used_chars += len(clean_text)

        # Check if text was already translated
        c_key = clean_text.lower()
        translations = await self.client.api.fetch_translations(c_key)
        if len(translations) == 0:
            translations = await self.translate(clean_text)
            for t in translations:
                await self.client.api.insert_translation_entry(c_key, t["detected_source_language"], t["text"])

        # If message could not be translated, log it as a warning
        if len(translations) == 0:
            logger.warning(f"Unable to translate '{message.clean_content}'")

        return translations

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        # Check whether message is valid for further processing
        if not self.is_valid(message):
            return

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
            translations = await self.translate_message(message, text or parser.text)

        assert message.guild is not None
        channel = await self.client.get_or_fetch_guild_channel(message.guild, FEED_CHANNEL_ID)
        if channel is None:
            return logger.warning("Translation output channel is None!")
        assert isinstance(channel, TextChannel)
        await self.dispatch_translation(channel, message, translations, flag)

    async def dispatch_translation(self, channel: TextChannel, message: Message, translations: list[TranslationEntryDict], flag: int) -> None: # noqa C901
        # If message contains a reply, track down the reference author
        action = None
        if message.reference and message.reference.message_id:
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
            embeds: list[Embed] = []
            for translation in translations:
                text = translation["text"]
                detected_lang = translation["detected_source_language"]
                embeds.append((
                    PidroidEmbed(description=text)
                    .set_footer(text=f"Detected source language: {LANGUAGE_MAPPING.get(detected_lang, detected_lang)} | {self.used_chars}/{self.daily_char_limit} chars used")
                ))

        # Go over each embed and set author values or other stuff
        for embed in embeds:
            _ = embed.set_author(name=str(message.author), url=message.jump_url, icon_url=message.author.display_avatar)

            # Set action as title, like replying
            if action is not None:
                embed.title = action

            # Insert rich description
            if len(rich_description) > 0:
                assert embed.description is not None
                embed.description += "\n--\n" + rich_description

            # Add attachments if they exist
            if len(attachments) > 0:
                _ = embed.add_field(name="Attachments", value='\n'.join(attachments), inline=False)

            # Notify of any modifications done to the original string
            if flag == ParserFlags.BYPASSED:
                _ = embed.set_footer(text="Translation layer bypassed as nothing translatable was found")
            else:
                footer = FLAG_FOOTERS.get(flag)
                if footer is not None:
                    _ = embed.set_footer(text=f"{footer} | {embed.footer.text}")
            
            await self.client.queue(channel, embed)

async def setup(client: Pidroid) -> None:
    await client.add_cog(ChatTranslationService(client))
