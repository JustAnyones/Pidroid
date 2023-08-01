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
from discord.ext import commands # type: ignore
from discord.ext.commands.errors import BadArgument # type: ignore
from discord.guild import Guild
from discord.mentions import AllowedMentions
from discord.message import Message
from typing import TYPE_CHECKING, Dict, List, Literal, NamedTuple, Optional

from pidroid.models.punishments import Case, PunishmentType
from pidroid.models.categories import get_command_categories, UncategorizedCategory
from pidroid.models.guild_configuration import GuildConfiguration, GuildPrefixes
from pidroid.models.persistent_views import PersistentSuggestionDeletionView
from pidroid.utils.api import API
from pidroid.utils.checks import is_client_pidroid
from pidroid.utils.data import PersistentDataManager

class VersionInfo(NamedTuple):
    major: int
    minor: int
    micro: int
    releaselevel: Literal["alpha", "beta", "candidate", "final"]
    commit_id: str


__VERSION__ = VersionInfo(major=5, minor=10, micro=0, releaselevel='alpha', commit_id=os.environ.get('GIT_COMMIT', ''))

class Pidroid(commands.Bot): # type: ignore
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
            'cogs.handlers.thread_archiver',

            # TheoTown specific handler extensions
            # NOTE: these handlers are not loaded if current client ID is not Pidroid.
            'cogs.handlers.theotown.chat_translator',
            'cogs.handlers.theotown.copypasta',
            'cogs.handlers.theotown.event_channel_handler',
            'cogs.handlers.theotown.guild_statistics',
            'cogs.handlers.theotown.plugin_store',
            'cogs.handlers.theotown.reaction_handler',

            # Load the error handler last
            'cogs.handlers.error_handler',

            # Debugging tool jishaku
            'jishaku'
        ]

        # This holds cached guild configurations
        self._guild_prefix_cache_ready = asyncio.Event()
        self.__cached_guild_prefixes: Dict[int, GuildPrefixes] = {}

        self.client_version = __VERSION__

        self.command_categories = get_command_categories()

        self.version_cache: Dict[str, Optional[str]] = {}

        self.session = None

        self.api = API(self, self.config["postgres_dsn"])

        self.persistent_data = PersistentDataManager()

        self.logger = logging.getLogger('Pidroid') # backwards compatibility

    async def setup_hook(self):
        await self.api.connect()
        await self.load_cogs()
        self.add_persistent_views()

    def add_persistent_views(self):
        self.add_view(PersistentSuggestionDeletionView())

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
        return f"{version_str} {self.client_version.releaselevel} {self.client_version.commit_id}"

    async def wait_until_guild_configurations_loaded(self):
        """Waits until the internal guild configuration cache is ready.

        It also waits for internal bot cache to be ready, therefore calling client.wait_until_ready()
        is no longer needed.
        """
        await self._guild_prefix_cache_ready.wait()

    async def fetch_guild_configuration(self, guild_id: int) -> GuildConfiguration:
        """Returns the latest available guild configuration from the database.

        If there was no guild configuration found, new configuration will be created and returned.

        The internal guild configuration is also updated.
        """
        config = await self.api.fetch_guild_configuration(guild_id)
        if config is None:
            self.logger.warning(
                "Could not fetch guild configuration for %s, create new configuration",
                guild_id
            )
            config = await self.api.insert_guild_configuration(guild_id)
        self._update_guild_prefixes(guild_id, config)
        return config
    
    def _get_guild_prefixes(self, guild_id: int) -> Optional[GuildPrefixes]:
        """Returns guild prefixes from internal cache."""
        return self.__cached_guild_prefixes.get(guild_id)

    def _update_guild_prefixes(self, guild_id: int, config: GuildConfiguration) -> GuildConfiguration:
        """Updates guild prefixes in the internal cache and returns its object."""
        self.__cached_guild_prefixes[guild_id] = config.guild_prefixes
        return self._get_guild_prefixes(guild_id) # type: ignore

    def _remove_guild_prefixes(self, guild_id: int) -> None:
        """Removes guild prefixes from internal cache."""
        self.__cached_guild_prefixes.pop(guild_id)

    async def create_expiring_thread(self, message: Message, name: str, expire_timestamp: datetime.datetime, auto_archive_duration: int = 60):
        """Creates a new expiring thread"""
        thread = await message.create_thread(name=name, auto_archive_duration=auto_archive_duration) # type: ignore
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

    async def get_or_fetch_role(self, guild: Guild, role_id: int):
        """Attempts to resolve a role from role_id by any means. Returns None if everything failed."""
        role = guild.get_role(role_id)
        if role is None:
            for role in await guild.fetch_roles():
                if role.id == role_id:
                    return role
        return role


    async def get_prefixes(self, message: Message) -> List[str]:
        """Returns a string list of prefixes for a message using message's context."""
        if not is_client_pidroid(self):
            return self.prefixes

        if message.guild:
            guild_prefixes = self._get_guild_prefixes(message.guild.id)
            if guild_prefixes:
                return guild_prefixes.prefixes or self.prefixes
        return self.prefixes

    async def get_prefix(self, message: Message):
        """Returns a prefix for client to respond to."""
        await self.wait_until_guild_configurations_loaded()
        return commands.when_mentioned_or(*await self.get_prefixes(message))(self, message) # type: ignore

    async def handle_reload(self):
        """Reloads all cogs of the client, excluding DB and API extensions.
        \nWarning: this is an experimental method and should not be depended on!"""
        self.logger.critical("Reloading bot configuration data and all cogs")
        is_pidroid = is_client_pidroid(self)
        for ext in self._extensions_to_load:
            if not is_pidroid and ext.startswith("cogs.handlers.theotown"):
                continue
            await self.unload_extension(ext)
        for ext in self._extensions_to_load:
            if not is_pidroid and ext.startswith("cogs.handlers.theotown"):
                self.logger.info(f"Skipping loading {ext} as the current client is not Pidroid.")
                continue
            await self.load_extension(ext)
        await self.generate_help_documentation()

    async def load_all_extensions(self):
        """Attempts to load all extensions as defined in client object."""
        # By now, we should be logged in
        is_pidroid = is_client_pidroid(self)

        for ext in self._extensions_to_load:
            self.logger.debug(f"Loading {ext}.")
            if not is_pidroid and ext.startswith("cogs.handlers.theotown"):
                self.logger.info(f"Skipping loading {ext} as the current client is not Pidroid.")
                continue
            try:
                await self.load_extension(ext)
                self.logger.debug(f"Successfully loaded {ext}.")
            except Exception:
                self.logger.exception(f"Failed to load {ext}.")
        await self.generate_help_documentation()

    async def load_cogs(self):
        """Attempts to load all extensions as defined in client object."""
        self.logger.info("Loading extensions")
        await self.load_all_extensions()

    async def generate_help_documentation(self):
        # TODO: implement
        self.logger.warning("DOCUMENTATION GENERATION IS YET TO BE IMPLEMENTED")

        commands = [c for c in self.walk_commands()]
        categories = self.command_categories

        mapping = {}

        def get_full_command_name(command) -> str:
            """Returns full command name including any command groups."""
            name = ''
            if len(command.parents) > 0:
                for parent in reversed(command.parents):
                    name += f'{parent.name} '
            return name + command.name

        for command in commands:
            # Ignore commands that are hidden
            if command.hidden:
                continue

            command_name = get_full_command_name(command)
            # Ignore jishaku commands
            if command_name.startswith("jishaku"):
                continue

            category = command.__original_kwargs__.get("category", UncategorizedCategory)

            mapping[command_name] = {
                "description": command.brief,
                "aliases": command.aliases,
                "category": category
            }
            #print(command)

        #for command in mapping:
        #    print(command, mapping[command])

        #def get_commands_in_category(mapping: dict, category: Category):
        #    return [command for command in mapping if isinstance(mapping['category'], category)]



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
