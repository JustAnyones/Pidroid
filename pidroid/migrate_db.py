import asyncio
import os
import motor.motor_asyncio # type: ignore

from bson.objectid import ObjectId # type: ignore
from motor.core import AgnosticCollection # type: ignore
from typing import List

from cogs.utils.api import API
from cogs.utils.time import timestamp_to_datetime

class OldAPI:

    def __init__(self, dsn: str):
        self.db_client = motor.motor_asyncio.AsyncIOMotorClient(dsn, serverSelectionTimeoutMS=5000)
        self.db = self.db_client["Pidroid"]

    @property
    def internal(self) -> AgnosticCollection:
        """Returns a MongoDB collection for internal related data."""
        return self.db["Internal"]

    @property
    def suggestions(self) -> AgnosticCollection:
        """Returns a MongoDB collection for TheoTown suggestions."""
        return self.db["Suggestions"]

    @property
    def punishments(self) -> AgnosticCollection:
        """Returns a MongoDB collection for guild member punishments."""
        return self.db["Punishments"]

    @property
    def guild_configurations(self) -> AgnosticCollection:
        """Returns a MongoDB collection for guild configurations."""
        return self.db["Guild_configurations"]

    @property
    def tags(self) -> AgnosticCollection:
        """Returns a MongoDB collection for tags."""
        return self.db["Tags"]

    @property
    def translations(self) -> AgnosticCollection:
        """Returns a MongoDB collection for translations."""
        return self.db["Translations"]

    async def fetch_phishing_urls(self) -> List[str]:
        """Returns a list of phising URLs."""
        data = await self.internal.find_one({"phising.urls": {"$exists": True}}, {"phising": 1, "_id": 0})
        if data is None:
            return []
        return data["phising"]["urls"]

    async def fetch_translations(self) -> List[dict]:
        """Returns a list of translations for specified string."""
        cursor = self.translations.find({})
        return [i async for i in cursor]

    async def fetch_suggestions(self) -> List[dict]:
        """Returns a list of all guild configurations."""
        cursor = self.suggestions.find({})
        return [i async for i in cursor]

    async def fetch_cases(self) -> List[dict]:
        cursor = self.punishments.find()
        return [i async for i in cursor]

    async def fetch_guild_configurations(self) -> List[dict]:
        """Returns a list of all guild configurations."""
        cursor = self.guild_configurations.find({})
        return [i async for i in cursor]

    async def fetch_tags(self) -> List[dict]:
        """Returns a list of all tags defined in the guild."""
        cursor = self.tags.find()
        return [i async for i in cursor]

async def migrate():
    
    mongo_dsn = os.getenv("MONGO_DSN")
    postgres_dsn = os.getenv("POSTGRES_DSN")

    new_api = API(None, postgres_dsn, True)
    await new_api.connect()
    old_api = OldAPI(mongo_dsn)
    print("Migrating")

    # Migrating phishing
    urls = await old_api.fetch_phishing_urls()
    for url in urls:
        await new_api.insert_phishing_url(url)
    print("Migrated phishing")

    # Migrate suggestions
    suggestions = await old_api.fetch_suggestions()
    for suggestion in suggestions:
        attachment_url = suggestion.get("attachment_url", None)
        attachments = []
        if attachment_url is not None:
            attachments.append(attachment_url)
        await new_api.insert_suggestion2(
            suggestion["author"],
            suggestion.get("message_id", None),
            suggestion["suggestion"],
            attachments,
            timestamp_to_datetime(suggestion["timestamp"])
        )
    print("Migrated suggestions")

    # Migrate translations
    translations = await old_api.fetch_translations()
    for translation in translations:
        translated = translation["translation"]
        if len(translated) == 0 or len(translated) > 1:
            continue
        translated = translated[0]
        await new_api.insert_translation_entry(
            translation["original_string"],
            translated["detected_source_language"],
            translated["text"]
        )
    print("Translations migrated")
            
    cases = await old_api.fetch_cases()
    for case in cases:
        expiration_date = None        
        date_expires = case["date_expires"]
        if date_expires == -1:
            expiration_date = None
        else:
            expiration_date = timestamp_to_datetime(date_expires)
                
        handled = False
        if date_expires == 0:
            handled = True

        await new_api.insert_punishment_entry2(
            case["type"],
            case["guild_id"],
            case["user_id"],
            case.get("user_name", None),
            case["moderator_id"],
            case.get("moderator_name", None),
            case.get("reason", None),
            expiration_date,
            timestamp_to_datetime(case["date_issued"]),
            case["visible"],
            handled
        )
    print("Punishments migrated")

    # Migrate guild configs
    configs = await old_api.fetch_guild_configurations()
    for config in configs:
        c = await new_api.fetch_guild_configuration(config["guild_id"])
                
        if c is None:
            c = await new_api.insert_guild_configuration(
                config["guild_id"],
                config.get("jail_channel"), config.get("jail_role"),
                config.get("log_channel", None)
            )

        c.jail_channel = config.get("jail_channel")
        c.jail_role = config.get("jail_role")
        c.mute_role = config.get("mute_role")
        c.log_channel = config.get("log_channel")
        c.public_tags = config.get("public_tags", False)
        c.strict_anti_phishing = config.get("strict_anti_phising", False)
        c.suspicious_usernames = config.get("suspicious_users", [])
        c.prefixes = config.get("prefixes", [])
        await c._update()
    print("Migrated guild configurations")

    # Migrate tags
    tags = await old_api.fetch_tags()
    for tag in tags:
        _id: ObjectId = tag["_id"]

        authors = []
        if tag.get("author_id") is None:
            authors = tag["author_ids"]
        else:
            authors.append(tag["author_id"])

        await new_api.insert_tag2(
            tag["guild_id"],
            tag["name"],
            tag["content"],
            authors,
            _id.generation_time
        )
    print("Tags migrated")
    print("Database migration has been completed")

asyncio.run(migrate())
