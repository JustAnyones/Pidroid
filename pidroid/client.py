from __future__ import annotations

import asyncio
import datetime
import discord
import random
import subprocess # nosec
import sys
import os
import logging

from aiohttp import ClientSession
from contextlib import suppress
from discord.ext import commands, tasks
from discord.ext.commands.errors import BadArgument
from discord.guild import Guild
from discord.mentions import AllowedMentions
from discord.message import Message
from discord.utils import MISSING
from typing import TYPE_CHECKING, Any, Dict, List, NamedTuple, Optional, Union

from pidroid.models.categories import Category, register_categories
from pidroid.models.event_types import EventName, EventType
from pidroid.models.guild_configuration import GuildConfiguration
from pidroid.models.persistent_views import PersistentSuggestionManagementView
from pidroid.models.punishments import Case, PunishmentType
from pidroid.models.queue import AbstractMessageQueue, EmbedMessageQueue, MessageQueue
from pidroid.utils.api import API
from pidroid.utils.checks import is_client_pidroid

if TYPE_CHECKING:
    from discord.types.threads import ThreadArchiveDuration

logger = logging.getLogger("Pidroid")

class VersionInfo(NamedTuple):
    major: int
    minor: int
    micro: int
    commit_id: str


__VERSION__ = VersionInfo(major=5, minor=17, micro=0, commit_id=os.environ.get('GIT_COMMIT', ''))

class Pidroid(commands.Bot):
    """This class represents the Pidroid bot client object."""

    if TYPE_CHECKING:
        session: Optional[ClientSession]

    def __init__(self, config: dict):
        intents = discord.Intents.all()
        intents.presences = False
        allowed_mentions = AllowedMentions(everyone=False, replied_user=False)
        super().__init__(
            command_prefix="P", help_command=None,
            intents=intents, allowed_mentions=allowed_mentions,
            case_insensitive=True
        )

        # Load configuration
        self.config = config
        self.debugging = config["debugging"]
        self.prefixes = config["prefixes"]

        # This defines hot-reloadable cogs and various files
        self._extensions_to_load = [
            # Commands
            'cogs.commands.admin',
            'cogs.commands.anime',
            'cogs.commands.bot',
            'cogs.commands.economy',
            'cogs.commands.emoji',
            'cogs.commands.forum',
            'cogs.commands.fun',
            'cogs.commands.giveaway',
            'cogs.commands.help',
            'cogs.commands.image',
            'cogs.commands.info',
            'cogs.commands.levels',
            'cogs.commands.owner',
            'cogs.commands.setting',
            'cogs.commands.sticker',
            'cogs.commands.suggestion',
            'cogs.commands.tags',
            'cogs.commands.theotown',
            'cogs.commands.utilities',

            # Moderation related commands
            'cogs.commands.moderation.punishment',
            'cogs.commands.moderation.information',

            # Extensions related to handling or responding
            # to certain events and running tasks
            'cogs.handlers.guild_events',
            'cogs.handlers.initialization',
            'cogs.handlers.leveling_handler',
            'cogs.handlers.logging_handler',
            'cogs.handlers.punishment_handler',
            'cogs.handlers.reminder_handler',
            'cogs.handlers.thread_archiver',

            # TheoTown specific handler extensions
            # NOTE: these handlers are not loaded if current client ID is not Pidroid.
            'cogs.handlers.theotown.chat_translator',
            'cogs.handlers.theotown.copypasta',
            'cogs.handlers.theotown.events_handler',
            'cogs.handlers.theotown.guild_statistics',
            'cogs.handlers.theotown.plugin_store',
            'cogs.handlers.theotown.reaction_handler',

            # Load the error handler last
            'cogs.handlers.error_handler',

            # Debugging tool jishaku
            'jishaku',
        ]

        # This holds cached guild configurations
        self._guild_prefix_cache_ready = asyncio.Event()
        self.__cached_guild_prefixes: Dict[int, List[str]] = {}

        self.client_version = __VERSION__

        self.command_categories: List[Category] = []

        self.version_cache: Dict[str, Optional[str]] = {}

        self.session = None

        self.api = API(self, self.config["postgres_dsn"])

        self.__queues: Dict[int, AbstractMessageQueue] = {}
        self.__tasks: List[tasks.Loop] = []

    async def setup_hook(self):
        await self.api.connect()
        await self.load_cogs()
        self.add_persistent_views()

    def add_persistent_views(self):
        """Adds persistent views that do not timeout."""
        self.add_view(PersistentSuggestionManagementView())

    async def register_categories(self):
        """Registers command categories.
        
        Should be called on command update or cog reload."""
        self.command_categories = register_categories(self)

    @property
    def token(self) -> str:
        """Returns client token."""
        return self.config['token']

    @property
    def version(self) -> str:
        """Returns shorthand client version."""
        version_str = '.'.join((str(v) for i, v in enumerate(self.client_version) if i < 3))
        return version_str

    @property
    def full_version(self) -> str:
        """Returns full client version."""
        version_str = '.'.join((str(v) for i, v in enumerate(self.client_version) if i < 3))
        return f"{version_str} {self.client_version.commit_id}"

    async def wait_until_guild_configurations_loaded(self):
        """Waits until the internal guild configuration cache is ready.

        It also waits for internal bot cache to be ready, therefore calling client.wait_until_ready()
        is no longer needed.
        """
        await self._guild_prefix_cache_ready.wait()

    async def wait_until_ready(self) -> None:
        await super().wait_until_ready()

    async def fetch_guild_configuration(self, guild_id: int) -> GuildConfiguration:
        """Returns the latest available guild configuration from the database.

        If there was no guild configuration found, new configuration will be created and returned.

        The internal guild configuration is also updated.
        """
        config = await self.api.fetch_guild_configuration(guild_id)
        if config is None:
            logger.warning(
                "Could not fetch guild configuration for %s, create new configuration",
                guild_id
            )
            config = await self.api.insert_guild_configuration(guild_id)
        self.update_guild_prefixes_from_config(guild_id, config)
        return config
    
    def get_guild_prefixes(self, guild_id: int) -> Optional[List[str]]:
        """Returns guild prefixes from internal cache."""
        return self.__cached_guild_prefixes.get(guild_id)

    def update_guild_prefixes_from_config(self, guild_id: int, config: GuildConfiguration) -> List[str]:
        """Updates guild prefixes in the internal cache and returns the prefix list."""
        self.__cached_guild_prefixes[guild_id] = config.prefixes
        return config.prefixes

    def remove_guild_prefixes(self, guild_id: int) -> None:
        """Removes guild prefixes from internal cache."""
        self.__cached_guild_prefixes.pop(guild_id)

    async def create_expiring_thread(self, message: Message, name: str, expire_timestamp: datetime.datetime, auto_archive_duration: ThreadArchiveDuration = 60):
        """Creates a new expiring thread"""
        thread = await message.create_thread(name=name, auto_archive_duration=auto_archive_duration)
        await self.api.insert_expiring_thread(thread.id, expire_timestamp)
        return thread

    async def fetch_case(self, guild_id: int, case_id: int) -> Case:
        """Returns a case for specified guild and user."""
        case = await self.api._fetch_case(guild_id, case_id)
        if case is None:
            raise BadArgument("Specified case could not be found!")
        return case

    async def fetch_cases(self, guild_id: int, user_id: int) -> List[Case]:
        """Returns a list of cases for specified guild and user."""
        return await self.api._fetch_cases(guild_id, user_id)

    async def fetch_warnings(self, guild_id: int, user_id: int) -> List[Case]:
        """Returns a list of warning cases for specified guild and user."""
        return [c for c in await self.fetch_cases(guild_id, user_id) if c.type == PunishmentType.warning]

    async def fetch_active_warnings(self, guild_id: int, user_id: int) -> List[Case]:
        """Returns a list of active warning cases for specified guild and user."""
        return [
            c
            for c in await self.fetch_cases(guild_id, user_id)
            if c.type == PunishmentType.warning and not c.has_expired
        ]

    async def get_or_fetch_member(self, guild: Guild, member_id: int) -> Optional[discord.Member]:
        """Attempts to resolve member from member_id by any means. Returns None if everything failed."""
        member = guild.get_member(member_id)
        if member is None:
            with suppress(discord.HTTPException):
                return await guild.fetch_member(member_id)
        return member

    async def get_or_fetch_user(self, user_id: int) -> Optional[discord.User]:
        """Attempts to resolve user from user_id by any means. Returns None if everything failed."""
        user = self.get_user(user_id)
        if user is None:
            with suppress(discord.HTTPException):
                return await self.fetch_user(user_id)
        return user

    async def get_or_fetch_guild_channel(self, guild: Guild, channel_id: int):
        """Attempts to resolve guild channel from channel_id by any means. Returns None if everything failed."""
        channel = guild.get_channel(channel_id)
        if channel is None:
            with suppress(discord.HTTPException):
                return await guild.fetch_channel(channel_id)
        return channel

    async def get_or_fetch_channel(self, channel_id: int):
        """Attempts to resolve a channel from channel_id by any means. Returns None if everything failed."""
        channel = self.get_channel(channel_id)
        if channel is None:
            with suppress(discord.HTTPException):
                return await self.fetch_channel(channel_id)
        return channel


    async def get_prefixes(self, message: Message) -> List[str]:
        """Returns a string list of prefixes for a message using message's context."""
        if not is_client_pidroid(self):
            return self.prefixes

        if message.guild:
            guild_prefixes = self.get_guild_prefixes(message.guild.id)
            if guild_prefixes:
                return guild_prefixes or self.prefixes
        return self.prefixes

    async def get_prefix(self, message: Message):
        """Returns a prefix for client to respond to."""
        await self.wait_until_guild_configurations_loaded()
        return commands.when_mentioned_or(*await self.get_prefixes(message))(self, message)

    async def handle_reload(self):
        """Reloads all cogs of the client, excluding DB and API extensions.
        \nWarning: this is an experimental method and should not be depended on!"""
        logger.critical("Reloading bot configuration data and all cogs")
        is_pidroid = is_client_pidroid(self)
        for ext in self._extensions_to_load:
            if not is_pidroid and ext.startswith("cogs.handlers.theotown"):
                continue
            await self.unload_extension(ext)
        for ext in self._extensions_to_load:
            if not is_pidroid and ext.startswith("cogs.handlers.theotown"):
                logger.info(f"Skipping loading {ext} as the current client is not Pidroid.")
                continue
            await self.load_extension(ext)
        await self.register_categories()

    async def load_all_extensions(self):
        """Attempts to load all extensions as defined in client object."""
        # By now, we should be logged in
        is_pidroid = is_client_pidroid(self)

        for ext in self._extensions_to_load:
            logger.debug(f"Loading {ext}.")
            if not is_pidroid and ext.startswith("cogs.handlers.theotown"):
                logger.info(f"Skipping loading {ext} as the current client is not Pidroid.")
                continue
            try:
                await self.load_extension(ext)
                logger.debug(f"Successfully loaded {ext}.")
            except Exception:
                logger.exception(f"Failed to load {ext}.")
        await self.register_categories()

    async def load_cogs(self):
        """Attempts to load all extensions as defined in client object."""
        logger.info("Loading extensions")
        await self.load_all_extensions()

    async def close(self) -> None:
        """Called when Pidroid is being shut down."""
        await super().close()
        for task in self.__tasks:
            task.stop()

    def create_queue(self, channel: discord.TextChannel, embed_queue: bool = False, delay: float = -1) -> AbstractMessageQueue:
        """Creates a queue and returns the queue object."""
        queue: Union[MessageQueue, EmbedMessageQueue]
        if not embed_queue:
            queue = MessageQueue(channel, delay=delay)
        else:
            queue = EmbedMessageQueue(channel, delay=delay)
        self.__queues[channel.id] = queue
        # Let's not reimplement wheel
        # and use discord.py's Loop class
        loop = tasks.Loop(
            queue.handle_queue,
            seconds=0,
            minutes=0,
            hours=0,
            count=None,
            time=MISSING,
            reconnect=True,
        )
        loop._before_loop = self.wait_until_guild_configurations_loaded # type: ignore
        self.__tasks.append(loop)
        loop.start()
        return queue
    
    def remove_queue(self, channel: discord.TextChannel):
        """Removes queue which was created in the specific text channel."""

        queue = self.__queues.get(channel.id, None)
        if queue is None:
            return

        for loop in self.__tasks.copy():
            if loop.coro == queue.handle_queue:
                loop.stop()
                self.__tasks.remove(loop)
                del self.__queues[channel.id]
                return

    async def queue(self, channel: discord.TextChannel, item: Union[str, discord.Embed], delay: float = -1):
        """Adds the specified item to a text channel queue.
        
        The item can be a string or an embed.
        
        Mixed content cannot be sent to the same text channel."""
        use_embed_queue = isinstance(item, discord.Embed)

        queue = self.__queues.get(channel.id, None)
        if queue is None:
            queue = self.create_queue(channel, embed_queue=use_embed_queue, delay=delay)

        # TODO: support mixed content
        if (
            (use_embed_queue and isinstance(queue, MessageQueue))
            or (not use_embed_queue and isinstance(queue, EmbedMessageQueue))
        ):
            raise ValueError("Sending mixed content to a channel is currently unsupported.")

        await queue.queue(item)

    def log_event(
        self,
        event_type: EventType,
        event_name: EventName,
        guild_id: int,
        target_id: Any,
        responsible_id: int,
        *,
        extra: Optional[dict] = None
    ):
        """Logs the event to Pidroid's database."""
        logger.debug(f"{event_type.name}: {event_name.value} {guild_id=} {target_id=} {responsible_id=} {extra=}")


        # TODO: implement
        #self.dispatch(
        #    'log_event',
        #    event_type,
        #)

    async def annoy_erksmit(self):
        if sys.platform != "win32":
            return

        urls = [
            "https://nekobot.xyz/imagegen/a/a/c/857b16eddc3c22a65b78e8d431a22.mp4",
            "https://www.youtube.com/watch?v=veaKOM1HYAw",
            "https://www.youtube.com/watch?v=UIp6_0kct_U",
            "https://www.youtube.com/watch?v=h_JJm5ETNSA"
        ]

        """proc1 = subprocess.Popen('powershell [Environment]::UserName', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        win_user_name = proc1.stdout.read().decode("utf-8").strip()"""
        proc2 = subprocess.Popen(['git', 'config', 'user.name'], stdout=subprocess.PIPE, stderr=subprocess.PIPE) # nosec
        if proc2.stdout is None:
            return
        git_user_name = proc2.stdout.read().decode("utf-8").strip()

        # We do a miniscule amount of trolling
        if git_user_name == "erksmit":
            subprocess.Popen([ # nosec
                'powershell',
                f'[system.Diagnostics.Process]::Start("firefox", "{random.choice(urls)}")' # nosec
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
