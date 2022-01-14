from __future__ import annotations

import bson # type: ignore
import motor.motor_asyncio # type: ignore
import random
import secrets
import string

from bson.objectid import ObjectId # type: ignore
from discord.ext.commands.errors import BadArgument # type: ignore
from motor.core import AgnosticCollection # type: ignore
from pymongo.results import InsertOneResult # type: ignore
from urllib.parse import quote_plus
from typing import Any, List, Optional, Union, TYPE_CHECKING

from cogs.ext.commands.tags import Tag
from cogs.models.case import Case
from cogs.models.configuration import GuildConfiguration
from cogs.models.plugins import NewPlugin, Plugin
from cogs.utils.http import HTTP, Route
from cogs.utils.time import utcnow

if TYPE_CHECKING:
    from client import Pidroid


class API:
    """This class handles actions related to Pidroid Mongo and MySQL database calls over TheoTown API."""

    def __init__(self, client: Pidroid, connection_string: str):
        self.client = client
        self.db_client = motor.motor_asyncio.AsyncIOMotorClient(connection_string, serverSelectionTimeoutMS=5000)
        self.db = self.db_client["Pidroid"]
        self.http = HTTP(client)

    @property
    def internal(self) -> AgnosticCollection:
        """Returns a MongoDB collection for internal related data."""
        return self.db["Internal"]

    @property
    def suggestions(self) -> AgnosticCollection:
        """Returns a MongoDB collection for TheoTown suggestions."""
        return self.db["Suggestions"]

    @property
    def plugin_threads(self) -> AgnosticCollection:
        """Returns a MongoDB collection for plugin showcase threads."""
        return self.db["Plugin_threads"]

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
    def shitposts(self) -> AgnosticCollection:
        """Returns a MongoDB collection for Pidroid shitposts."""
        return self.db["Shitposts"]

    async def get(self, route: Route) -> dict:
        """Sends a GET request to the TheoTown API."""
        return await self.http.request("GET", route)

    async def post(self, route: Route, data: dict = None) -> dict:
        """Sends a POST request to the TheoTown API."""
        return await self.http.request("GET", route, data=data)

    @staticmethod
    def generate_id(characters: str = string.ascii_lowercase + string.ascii_uppercase + string.digits, size: int = 6) -> str:
        """Generates a cryptographically secure string of random digits and letters."""
        return ''.join(secrets.choice(characters) for _ in range(size))

    async def is_id_unique(self, collection_name: str, d_id: str) -> bool:
        """Returns True if specified ID is not used in the specified collection."""
        res = await self.db[collection_name].find_one({"id": d_id})
        return res is None

    async def get_unique_id(self, collection: Union[AgnosticCollection, str]) -> str:
        """Returns a unique ID for the specified collection."""

        collection_name = collection
        if isinstance(collection, AgnosticCollection):
            collection_name = collection.name

        failed_count = 0
        d_id = API.generate_id()
        while not await self.is_id_unique(collection_name, d_id):
            failed_count += 1
            if failed_count > 5:
                # This is when you are really screwed
                raise BadArgument("Mongo was unable to generate a unique ID after trying 5 times")
            d_id = API.generate_id()
        return d_id

    """Phising protection related methods"""

    async def insert_new_phising_url(self, url: str) -> None:
        """Inserts a new phising URL to the database."""
        await self.internal.update_one({}, {"$push": {"phising.urls": url}})

    async def fetch_phising_url_list(self) -> List[str]:
        """Returns a list of phising URLs."""
        data = await self.internal.find_one({"phising.urls": {"$exists": True}}, {"phising": 1, "_id": 0})
        if data is None:
            self.client.logger.critical("Phising URLs returned an empty list!")
            return []
        return data["phising"]["urls"]

    """Suggestion related methods"""

    async def submit_suggestion(self, author_id: int, message_id: int, suggestion: str, attachment_url: str = None) -> str:
        """Submits a suggestion to the database.

        Returns submitted suggestion ID."""
        d_id = await self.get_unique_id(self.suggestions)
        d = {
            "id": d_id,
            "author": bson.Int64(author_id),
            "message_id": bson.Int64(message_id),
            "suggestion": suggestion,
            "timestamp": bson.Int64(utcnow().timestamp())
        }
        if attachment_url:
            d["attachment_url"] = attachment_url
        await self.suggestions.insert_one(d)
        return d_id

    """Plugin API related methods"""

    async def get_new_plugins(self, last_approval_time: int) -> List[NewPlugin]:
        """Queries the TheoTown API for new plugins after the specified approval time."""
        response = await self.get(Route("/private/plugin/get_new", {"last_approval_time": last_approval_time}))
        return [NewPlugin(np) for np in response["data"]]

    async def find_plugin(self, query: str, show_hidden: bool = False, narrow_search: bool = False) -> List[Plugin]:
        """Queries the TheoTown API for plugins matching the query string."""
        response = await self.get(Route(
            "/private/plugin/find",
            {"query": quote_plus(query.replace('#', '')), "show_hidden": show_hidden, "narrow": narrow_search}
        ))
        return [Plugin(p) for p in response["data"]]

    async def create_new_plugin_thread(self, thread_id: int, expire_timestamp: int) -> None:
        """Creates a new plugin thread entry inside the database."""
        await self.plugin_threads.insert_one({
            "thread_id": thread_id,
            "expires": expire_timestamp
        })

    async def get_archived_plugin_threads(self, timestamp: float) -> List[dict]:
        """Returns a list of active plugin threads which require archiving."""
        cursor = self.plugin_threads.find(
            {"expires": {"$lte": timestamp}}
        )
        return [i async for i in cursor]

    async def remove_plugin_thread(self, _id: ObjectId) -> None:
        """Removes a plugin thread entry from the database."""
        await self.plugin_threads.delete_many({"_id": _id})

    """Moderation related methods"""

    async def _fetch_case_users(self, d: dict) -> dict:
        d["user"] = await self.client.get_or_fetch_user(d["user_id"])
        d["moderator"] = await self.client.get_or_fetch_user(d["moderator_id"])
        return d

    async def fetch_case(self, guild_id: int, case_id: str) -> Optional[Case]:
        """Returns a case for the specified guild and user."""
        case = await self.punishments.find_one({"id": str(case_id), "guild_id": guild_id, "visible": True})
        if case is None:
            return None
        return Case(self, await self._fetch_case_users(case))

    async def fetch_cases(self, guild_id: int, user_id: int) -> List[Case]:
        """Returns a list of cases for the specified guild and user."""

        # Visible parameter refers to invalidated warnings
        cursor = self.punishments.find(
            {"guild_id": guild_id, "user_id": user_id, "visible": True},
        ).sort("date_issued", -1)

        return [Case(self, await self._fetch_case_users(c)) async for c in cursor]

    async def fetch_active_cases(self, guild_id: int, user_id: int) -> List[Case]:
        """Returns a list of active cases for the specified guild and user."""
        return [
            c
            for c in await self.fetch_cases(guild_id, user_id)
            if not c.has_expired
        ]

    async def fetch_warnings(self, guild_id: int, user_id: int) -> List[Case]:
        """Returns a list of warnings for the specified guild and user."""
        return [c for c in await self.fetch_cases(guild_id, user_id) if c.type == "warning"]

    async def fetch_active_warnings(self, guild_id: int, user_id: int) -> List[Case]:
        """Returns a list of active warnings for the specified guild and user."""
        return [
            c
            for c in await self.fetch_cases(guild_id, user_id)
            if c.type == "warning" and not c.has_expired
        ]

    async def revoke_punishment(self, punishment_type: str, guild_id: int, user_id: int) -> None:
        """Revokes specified punishment by making it expired."""
        await self.punishments.update_many(
            {'type': punishment_type, 'guild_id': guild_id, 'user_id': user_id},
            {'$set': {'date_expires': 0}}
        )

    async def get_moderation_statistics(self, guild_id: int, moderator_id: int) -> tuple:
        """Returns general moderation statistics of the specified guild and member."""
        cursor = self.punishments.find(
            {"guild_id": guild_id, "moderator_id": moderator_id, "visible": True}
        )
        moderator_data = [i async for i in cursor]

        guild_total = await self.punishments.count_documents(
            {"guild_id": guild_id, "visible": True}
        )
        return moderator_data, guild_total

    async def is_currently_punished(self, punishment: str, guild_id: int, user_id: int) -> bool:
        count = await self.punishments.count_documents({
            "type": punishment,
            "guild_id": guild_id,
            "user_id": user_id,
            "$or": [
                {"date_expires": {"$gte": utcnow().timestamp()}},
                {"date_expires": -1}
            ],
            "visible": True
        })
        return count > 0

    async def is_currently_jailed(self, guild_id: int, user_id: int) -> bool:
        """Returns true if user is currently jailed."""
        return await self.is_currently_punished("jail", guild_id, user_id)

    async def is_currently_muted(self, guild_id: int, user_id: int) -> bool:
        """Returns true if user is currently muted."""
        return await self.is_currently_punished("mute", guild_id, user_id)

    async def get_active_guild_punishments(self, guild_id: int) -> list:
        """Returns a list of active punishments. NOTE that this excludes as they are not considered active."""
        cursor = self.punishments.find(
            {"type": {"$ne": "warning"}, "guild_id": guild_id, "date_expires": {"$gt": 0}, "visible": True}
        )
        return [i async for i in cursor]

    """Guild configuration related methods"""

    async def get_all_guild_configurations(self) -> List[GuildConfiguration]:
        """Returns a list of all guild configurations."""
        cursor = self.guild_configurations.find({})
        return [GuildConfiguration(self, i) async for i in cursor]

    async def get_guild_configuration(self, guild_id: int) -> Optional[GuildConfiguration]:
        """Returns a specified guild configuration."""
        data = await self.guild_configurations.find_one({"guild_id": guild_id})
        if data:
            return GuildConfiguration(self, data)
        return None

    async def get_guild_configuration_by_id(self, object_id: ObjectId) -> Optional[GuildConfiguration]:
        """Returns a specified guild configuration."""
        data = await self.guild_configurations.find_one({"_id": object_id})
        if data:
            return GuildConfiguration(self, data)
        return None

    async def create_new_guild_configuration(
        self, guild_id: int,
        jail_id: int = None, jail_role_id: int = None,
        mute_role_id: int = None
    ) -> Optional[GuildConfiguration]:
        """Creates a new guild configuration entry."""
        d = {
            "guild_id": bson.Int64(guild_id),
        }
        if jail_id:
            d["jail_channel"] = bson.Int64(jail_id)
        if jail_role_id:
            d["jail_role"] = bson.Int64(jail_role_id)
        if mute_role_id:
            d["mute_role"] = bson.Int64(mute_role_id)
        result: InsertOneResult = await self.guild_configurations.insert_one(d)
        return await self.get_guild_configuration_by_id(result.inserted_id)

    async def delete_guild_configuration(self, object_id: ObjectId) -> None:
        """Deletes a guild configuration document."""
        await self.guild_configurations.delete_one({'_id': object_id})

    async def set_guild_config(self, object_id: ObjectId, key: str, value: Any) -> None:
        """Sets a guild configuration key with specified value."""
        await self.guild_configurations.update_one(
            {"_id": object_id},
            {"$set": {key: value}}
        )

    async def unset_guild_config(self, object_id: ObjectId, key: str) -> None:
        """Unsets a guild configuration key."""
        await self.guild_configurations.update_one(
            {'_id': object_id},
            {"$unset": {key: 1}}
        )

    """Tag related methods"""

    async def create_tag(self, data: dict) -> ObjectId:
        """Creates a guild tag from a dictionary."""
        result: InsertOneResult = await self.tags.insert_one(data)
        return result.inserted_id

    async def fetch_guild_tag(self, guild_id: int, tag_name: str) -> Optional[Tag]:
        """Returns a guild tag for the appropriate name."""
        raw_tag = await self.tags.find_one({
            "guild_id": bson.Int64(guild_id),
            "name": {"$regex": f"^{tag_name}$", "$options": "i"}
        })
        if raw_tag is None:
            return None
        return Tag(self, raw_tag)

    async def search_guild_tags(self, guild_id: int, tag_name: str) -> List[Tag]:
        """Returns all guild tags matching the appropriate name."""
        cursor = self.tags.find({
            "guild_id": bson.Int64(guild_id),
            "name": {"$regex": tag_name, "$options": "i"}
        })
        return [Tag(self, i) async for i in cursor]

    async def fetch_guild_tags(self, guild_id: int) -> List[Tag]:
        """Returns a list of all tags defined in the guild."""
        cursor = self.tags.find({"guild_id": bson.Int64(guild_id)}).sort("name", 1)
        return [Tag(self, i) async for i in cursor]

    async def edit_tag(self, object_id: ObjectId, data: dict) -> None:
        """Edits a tag by specified object ID."""
        await self.tags.update_one({'_id': object_id}, {'$set': data})

    async def remove_tag(self, object_id: ObjectId) -> None:
        """Removes a tag by specified object ID."""
        await self.tags.delete_one({'_id': object_id})

    """Shitpost related methods"""

    async def get_random_shitpost(self, last_posts: List[Union[ObjectId, int]]) -> dict:
        """Returns a random shitpost."""
        data = await self.shitposts.find_one(
            {"_id": {"$nin": last_posts}}
        ).sort("times_shown", 1)
        cursor = self.shitposts.find({
            "_id": {"$nin": last_posts}, "times_shown": data["times_shown"]
        })
        return random.choice([i async for i in cursor]) # nosec

    async def log_shitpost(self, object_id: ObjectId) -> None:
        """Marks shitpost by specified ID as read by increasing times_shown."""
        await self.shitposts.update_one(
            {'_id': object_id},
            {'$inc': {'times_shown': 1}}
        )


def setup(client):
    pass

def teardown(client):
    pass
