from __future__ import annotations

import asyncio
import discord
import json
import signal
import logging

from aiohttp import ClientSession
from discord.client import _cleanup_loop
from discord.ext import commands
from discord.mentions import AllowedMentions
from discord.message import Message
from typing import TYPE_CHECKING, List, Optional

from cogs.utils.api import API
from cogs.utils.data import PersistentDataManager

__VERSION__ = discord.VersionInfo(major=4, minor=1, micro=0, releaselevel='alpha', serial=0)

if TYPE_CHECKING:
    from cogs.models.configuration import GuildConfiguration


class Pidroid(commands.Bot):
    """This class represents the Pidroid bot client object."""

    def __init__(self, config):
        intents = discord.Intents.all()
        intents.presences = False
        allowed_mentions = AllowedMentions(everyone=False, replied_user=False)
        super().__init__(
            command_prefix=None, help_command=None,
            intents=intents, allowed_mentions=allowed_mentions,
            case_insensitive=True
        )

        # This is necessary to allow reloading of code while the bot is running
        self.extensions_to_load = [
            # Constants file
            'constants',

            # Models
            'cogs.models.exceptions', # Load first so that I can use it in error_handler
            'cogs.models.categories',
            'cogs.models.configuration',
            'cogs.models.case',
            'cogs.models.plugins',
            'cogs.models.punishments',

            # Various utility functions
            'cogs.utils.api',
            'cogs.utils.checks',
            'cogs.utils.converters',
            'cogs.utils.decorators',
            'cogs.utils.embeds',
            'cogs.utils.getters',
            'cogs.utils.http',
            'cogs.utils.paginators',
            'cogs.utils.parsers',
            'cogs.utils.time',

            # Commands
            'cogs.ext.commands.admin',
            'cogs.ext.commands.anime',
            'cogs.ext.commands.bot',
            'cogs.ext.commands.economy',
            'cogs.ext.commands.emoji',
            'cogs.ext.commands.forum',
            'cogs.ext.commands.fun',
            'cogs.ext.commands.giveaway',
            'cogs.ext.commands.help',
            'cogs.ext.commands.image',
            'cogs.ext.commands.info',
            'cogs.ext.commands.minecraft',
            'cogs.ext.commands.owner',
            'cogs.ext.commands.reddit',
            'cogs.ext.commands.sticker',
            'cogs.ext.commands.tags',
            'cogs.ext.commands.theotown',
            'cogs.ext.commands.utilities',
            'cogs.ext.commands.mod.punish',
            'cogs.ext.commands.mod.logs',

            # Events
            'cogs.ext.events.copypasta',
            'cogs.ext.events.events_handler',
            'cogs.ext.events.initialization',
            'cogs.ext.events.minecraft',
            'cogs.ext.events.reaction_handler',

            # Tasks
            'cogs.ext.tasks.automod',
            'cogs.ext.tasks.cronjobs',
            'cogs.ext.tasks.forum_messages',
            'cogs.ext.tasks.guild_statistics',
            'cogs.ext.tasks.http_server',
            'cogs.ext.tasks.plugin_store',
            'cogs.ext.tasks.punishment_handler',

            # Error handler
            'cogs.ext.error_handler',

            # Debugging tool jishaku
            'jishaku'
        ]

        # This holds cached guild configurations
        self._guild_config_ready = asyncio.Event()
        self._cached_configurations = {}

        self._connected = asyncio.Event()

        self.client_version = __VERSION__

        self.command_categories = []

        self.version_cache = {}

        self.http_server_testing = True
        self.scavenger_hunt_complete = False

        self.config = config
        self.prefixes = self.config['prefixes']

        self.session = ClientSession(loop=self.loop)

        self.api = API(self, self.config['authentication']['database']["connection string"])

        self.prefix = self.prefixes[0]

        self.persistent_data = PersistentDataManager()

        self.logger = None
        self.setup_logging()

        self.load_cogs()

    @property
    def token(self) -> str:
        """Returns client token."""
        return self.config['authentication']['bot token']

    @property
    def version(self) -> str:
        """Returns shorthand client version."""
        version_str = '.'.join((str(v) for i, v in enumerate(self.client_version) if i < 3))
        if self.client_version.releaselevel != "final":
            return f"{version_str} {self.client_version.releaselevel}"
        return version_str

    @property
    def full_version(self) -> str:
        """Returns full client version."""
        version_str = '.'.join((str(v) for i, v in enumerate(self.client_version) if i < 3))
        return f"{version_str} {self.client_version.releaselevel} {self.client_version.serial}"

    async def wait_guild_config_cache_ready(self):
        """Waits until the internal guild configuration cache is ready.

        It also waits for internal bot cache to be ready, therefore calling client.wait_until_ready()
        is no longer needed.
        """
        await self._guild_config_ready.wait()

    @property
    def guild_config_cache_ready(self) -> bool:
        """Returns true if the internal guild configuration cache is ready."""
        return self._guild_config_ready.is_set()

    @property
    def guild_configurations(self) -> dict:
        """Returns raw guild configuration dictionary, should not be called."""
        return self._cached_configurations

    @property
    def guild_configuration_guilds(self) -> List[int]:
        """Returns guild configuration guild IDs."""
        return self._cached_configurations.keys()

    def get_guild_configuration(self, guild_id: int) -> Optional[GuildConfiguration]:
        """Returns guild configuration for specified guild."""
        return self.guild_configurations.get(guild_id)

    def _update_guild_configuration(self, guild_id: int, config: GuildConfiguration) -> GuildConfiguration:
        self.guild_configurations[guild_id] = config
        return self.get_guild_configuration(guild_id)

    def _remove_guild_configuration(self, guild_id: int) -> None:
        self.guild_configurations.pop(guild_id)

    # ETC
    async def resolve_user(self, user_id: int) -> discord.User:
        """Attempts to resolve user from user_id by any means. Returns None if everything failed."""
        result = self.get_user(user_id)
        if result is None:
            try:
                result = await self.fetch_user(user_id)
            except discord.HTTPException:
                return None
        return result

    def setup_logging(self):
        """Sets up client logging module."""
        self.logger = logging.getLogger('Pidroid')
        self.logger.setLevel(logging.WARNING)
        if __VERSION__[3] == "development" or __VERSION__[3] == "alpha":
            self.logger.setLevel(logging.DEBUG)

    async def get_prefix(self, message: Message):
        """Returns a prefix for client to respond to."""
        await self.wait_guild_config_cache_ready()

        if message.guild:
            guild_prefixes = self.get_guild_configuration(message.guild.id).prefixes
            prefixes = guild_prefixes or self.prefixes
        else:
            prefixes = self.prefixes

        return commands.when_mentioned_or(*prefixes)(self, message)

    def handle_reload(self):
        """Reloads all cogs of the client, excluding DB and API extensions.
        \nWarning: this is an experimental method and should not be depended on!"""
        self.logger.critical("Reloading bot configuration data and all cogs")
        for ext in self.extensions_to_load:
            self.unload_extension(ext)
        with open('./config.json') as data:
            self.config = json.load(data)
        for ext in self.extensions_to_load:
            self.load_extension(ext)

    def load_all_extensions(self):
        """Attempts to load all extensions as defined in client object."""
        for ext in self.extensions_to_load:
            self.logger.debug(f"Loading {ext}.")
            try:
                self.load_extension(ext)
                self.logger.debug(f"Successfully loaded {ext}.")
            except Exception:
                self.logger.exception(f"Failed to load {ext}.")

    def load_cogs(self):
        """Attempts to load all extensions as defined in client object."""
        self.logger.info("Starting the bot")
        self.load_all_extensions()

    # Borrowed method from the client
    def run(self): # noqa: C901
        """Runs the client."""
        loop = self.loop

        try:
            loop.add_signal_handler(signal.SIGINT, lambda: loop.stop())
            loop.add_signal_handler(signal.SIGTERM, lambda: loop.stop())
        except NotImplementedError:
            pass

        async def runner():
            try:
                await self.start(self.token)
            finally:
                if not self.is_closed():
                    await self.close()
                    await self.session.close() # All this chonkers method borrowing, just for this single call

        def stop_loop_on_completion(f):
            loop.stop()

        future = asyncio.ensure_future(runner(), loop=loop)
        future.add_done_callback(stop_loop_on_completion)
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            self.logger.info('Received signal to terminate bot and event loop.')
        finally:
            future.remove_done_callback(stop_loop_on_completion)
            self.logger.info('Cleaning up tasks.')
            _cleanup_loop(loop)

        if not future.cancelled():
            try:
                return future.result()
            except KeyboardInterrupt:
                # I am unsure why this gets raised here but suppress it anyway
                return None
