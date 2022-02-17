from __future__ import annotations

import asyncio
import discord
import json
import signal
import logging

from aiohttp import ClientSession
from contextlib import suppress
from discord.channel import TextChannel
from discord.client import _cleanup_loop
from discord.ext import commands
from discord.ext.commands.errors import BadArgument # type: ignore
from discord.guild import Guild
from discord.mentions import AllowedMentions
from discord.message import Message
from discord.types.channel import GuildChannel
from typing import TYPE_CHECKING, List, Optional

from cogs.models.case import Case
from cogs.models.categories import get_command_categories
from cogs.utils.api import API
from cogs.utils.checks import is_client_development
from cogs.utils.data import PersistentDataManager
from cogs.utils.logger import BaseLog

__VERSION__ = discord.VersionInfo(major=4, minor=4, micro=2, releaselevel='alpha', serial=0)

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

        # This defines hot-reloadable cogs and various files
        self.extensions_to_load = [
            # Commands
            'cogs.ext.commands.admin',
            'cogs.ext.commands.anime',
            'cogs.ext.commands.bot',
            'cogs.ext.commands.economy',
            'cogs.ext.commands.emoji',
            'cogs.ext.commands.forum',
            'cogs.ext.commands.fun',
            'cogs.ext.commands.github',
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
            'cogs.ext.events.translator',

            # Tasks
            'cogs.ext.tasks.automod',
            'cogs.ext.tasks.cronjobs',
            'cogs.ext.tasks.forum_messages',
            'cogs.ext.tasks.guild_statistics',
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

        self.client_version = __VERSION__

        self.command_categories = get_command_categories()

        self.version_cache = {}

        self.config = config
        self.prefixes = self.config['prefixes']

        self.session = ClientSession(loop=self.loop)

        self.api = API(self, self.config['authentication']['database']["connection string"])

        self.persistent_data = PersistentDataManager()

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
        return self._cached_configurations.keys() # type: ignore

    def get_guild_configuration(self, guild_id: int) -> Optional[GuildConfiguration]:
        """Returns guild configuration for specified guild."""
        return self.guild_configurations.get(guild_id)

    def _update_guild_configuration(self, guild_id: int, config: GuildConfiguration) -> GuildConfiguration:
        self.guild_configurations[guild_id] = config
        return self.get_guild_configuration(guild_id) # type: ignore

    def _remove_guild_configuration(self, guild_id: int) -> None:
        self.guild_configurations.pop(guild_id)

    async def dispatch_log(self, guild: Guild, log: BaseLog):
        """Dispatches a Pidroid log to a guild channel, if applicable."""
        config = self.get_guild_configuration(guild.id)
        if config is None:
            return

        if not config.log_channel:
            return

        channel = await self.get_or_fetch_channel(guild, config.log_channel)
        if channel is not None:
            channel: TextChannel
            await channel.send(embed=log.as_embed())

    async def fetch_case(self, guild_id: int, case_id: str) -> Case:
        """Returns a case for specified guild and user."""
        case = await self.api.fetch_case(guild_id, case_id)
        if case is None:
            raise BadArgument("Specified case could not be found!")
        return case

    async def fetch_cases(self, guild_id: int, user_id: int) -> List[Case]:
        """Returns a list of cases for specified guild and user."""
        return await self.api.fetch_cases(guild_id, user_id)

    async def fetch_warnings(self, guild_id: int, user_id: int) -> List[Case]:
        """Returns a list of warning cases for specified guild and user."""
        return await self.api.fetch_warnings(guild_id, user_id)

    async def fetch_active_warnings(self, guild_id: int, user_id: int) -> List[Case]:
        """Returns a list of active warning cases for specified guild and user."""
        return await self.api.fetch_active_warnings(guild_id, user_id)

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

    async def get_or_fetch_channel(self, guild: Guild, channel_id: int) -> Optional[GuildChannel]:
        """Attempts to resolve guild channel from channel_id by any means. Returns None if everything failed."""
        channel = guild.get_channel(channel_id)
        if channel is None:
            with suppress(discord.HTTPException):
                return await guild.fetch_channel(channel_id)
        return channel

    def setup_logging(self, logging_level: int = logging.WARNING):
        """Sets up client logging module."""
        self.logger = logging.getLogger('Pidroid')
        self.logger.setLevel(logging_level)
        if __VERSION__[3] == "development" or __VERSION__[3] == "alpha":
            self.logger.setLevel(logging.DEBUG)

    def get_prefixes(self, message: Message) -> List[str]:
        """Returns a string list of prefixes for a message using message's context."""
        if is_client_development(self):
            return self.prefixes

        if message.guild and message.guild.id in self.guild_configuration_guilds:
            guild_prefixes = self.get_guild_configuration(message.guild.id).prefixes
            return guild_prefixes or self.prefixes
        return self.prefixes

    async def get_prefix(self, message: Message):
        """Returns a prefix for client to respond to."""
        await self.wait_guild_config_cache_ready()
        return commands.when_mentioned_or(*self.get_prefixes(message))(self, message)

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
    # https://github.com/Rapptz/discord.py/blob/f485f1b61269c4e846e4e8b9232d8ec10b173c21/discord/client.py#L608-L666
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
