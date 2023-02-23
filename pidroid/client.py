from __future__ import annotations

import asyncio
import datetime
import discord
import random
import subprocess # nosec
import sys
import logging

from aiohttp import ClientSession
from contextlib import suppress
from discord.channel import TextChannel
from discord.ext import commands # type: ignore
from discord.ext.commands.errors import BadArgument # type: ignore
from discord.guild import Guild
from discord.mentions import AllowedMentions
from discord.message import Message
from typing import TYPE_CHECKING, Dict, List, Literal, NamedTuple, Optional

from pidroid.cogs.models.case import Case
from pidroid.cogs.models.categories import get_command_categories, UncategorizedCategory
from pidroid.cogs.utils.api import API
from pidroid.cogs.utils.checks import is_client_pidroid
from pidroid.cogs.utils.data import PersistentDataManager
from pidroid.cogs.utils.logger import BaseLog

class VersionInfo(NamedTuple):
    major: int
    minor: int
    micro: int
    releaselevel: Literal["alpha", "beta", "candidate", "final"]
    commit_id: str


__VERSION__ = VersionInfo(major=5, minor=9, micro=0, releaselevel='alpha', commit_id="unknown")

if TYPE_CHECKING:
    from pidroid.cogs.models.configuration import GuildConfiguration


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
            'cogs.ext.commands.levels',
            'cogs.ext.commands.owner',
            'cogs.ext.commands.reddit',
            'cogs.ext.commands.slash',
            'cogs.ext.commands.sticker',
            'cogs.ext.commands.tags',
            'cogs.ext.commands.theotown',
            'cogs.ext.commands.utilities',
            
            # Moderation related commands
            'cogs.ext.commands.moderation.punishment',
            'cogs.ext.commands.moderation.information',

            # Events
            'cogs.ext.events.copypasta',
            'cogs.ext.events.events_handler',
            'cogs.ext.events.guild_events',
            'cogs.ext.events.initialization',
            'cogs.ext.events.minecraft',
            'cogs.ext.events.reaction_handler',
            'cogs.ext.events.translator',
            
            'cogs.ext.events.audit_log_handler',

            # Tasks
            'cogs.ext.tasks.archive_threads',
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
        self._cached_configurations: Dict[int, GuildConfiguration] = {}

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

    @property
    def token(self) -> str:
        """Returns client token."""
        return self.config['token']

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
        return f"{version_str} {self.client_version.releaselevel} {self.client_version.commit_id}"

    async def wait_until_guild_configurations_loaded(self):
        """Waits until the internal guild configuration cache is ready.

        It also waits for internal bot cache to be ready, therefore calling client.wait_until_ready()
        is no longer needed.
        """
        await self._guild_config_ready.wait()

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

    def get_guild_configuration(self, guild_id: int) -> Optional[GuildConfiguration]:
        """Returns guild configuration for specified guild."""
        config = self.guild_configurations.get(guild_id)
        if config is None:
            self.logger.error(f"Failure acquiring guild configuration for {guild_id}")
            raise BadArgument("Failed to obtain guild configuration, if you're seeing this, something went very wrong!")
        return config
    
    async def fetch_guild_configuration(self, guild_id: int) -> GuildConfiguration:
        config = await self.api.fetch_guild_configuration(guild_id)
        if config is None:
            self.logger.warn(f"Could not fetch guild configuration for {guild_id}")
            config = await self.api.insert_guild_configuration(guild_id)
            self._update_guild_configuration(guild_id, config)
        return config
    
    async def get_or_fetch_guild_configuration(self, guild_id: int) -> GuildConfiguration:
        await self.wait_until_guild_configurations_loaded()
        config = self.guild_configurations.get(guild_id)
        if config is None:
            raise BadArgument(f"Failure acquiring guild configuration for {guild_id}")
        return config

    def _update_guild_configuration(self, guild_id: int, config: GuildConfiguration) -> GuildConfiguration:
        self.guild_configurations[guild_id] = config
        return self.get_guild_configuration(guild_id) # type: ignore

    def _remove_guild_configuration(self, guild_id: int) -> None:
        self.guild_configurations.pop(guild_id)

    async def create_expiring_thread(self, message: Message, name: str, expire_timestamp: datetime.datetime, auto_archive_duration: int = 60):
        """Creates a new expiring thread"""
        thread = await message.create_thread(name=name, auto_archive_duration=auto_archive_duration) # type: ignore
        await self.api.insert_expiring_thread(thread.id, expire_timestamp)
        return thread

    async def dispatch_log(self, guild: Guild, log: BaseLog):
        """Dispatches a Pidroid log to a guild channel, if applicable."""
        config = self.get_guild_configuration(guild.id)
        if config is None:
            return

        if not config.log_channel:
            return

        channel = await self.get_or_fetch_guild_channel(guild, config.log_channel)
        if channel is not None:
            assert isinstance(channel, TextChannel)
            await channel.send(embed=log.as_embed())

    async def fetch_case(self, guild_id: int, case_id: int) -> Case:
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
            for r in await guild.fetch_roles():
                if r.id == role_id:
                    return r
        return role


    def get_prefixes(self, message: Message) -> List[str]:
        """Returns a string list of prefixes for a message using message's context."""
        if not is_client_pidroid(self):
            return self.prefixes

        if message.guild:
            config = self.get_guild_configuration(message.guild.id)
            if config:
                return config.prefixes or self.prefixes
        return self.prefixes

    async def get_prefix(self, message: Message):
        """Returns a prefix for client to respond to."""
        await self.wait_until_guild_configurations_loaded()
        return commands.when_mentioned_or(*self.get_prefixes(message))(self, message) # type: ignore

    async def handle_reload(self):
        """Reloads all cogs of the client, excluding DB and API extensions.
        \nWarning: this is an experimental method and should not be depended on!"""
        self.logger.critical("Reloading bot configuration data and all cogs")
        for ext in self._extensions_to_load:
            await self.unload_extension(ext)
        for ext in self._extensions_to_load:
            await self.load_extension(ext)
        await self.generate_help_documentation()

    async def load_all_extensions(self):
        """Attempts to load all extensions as defined in client object."""
        for ext in self._extensions_to_load:
            self.logger.debug(f"Loading {ext}.")
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
