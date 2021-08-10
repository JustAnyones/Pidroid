__VERSION__ = (4, 0, 0, 'alpha')

import asyncio
import discord
import json
import logging

from aiohttp import ClientSession
from discord.ext import commands
from discord.mentions import AllowedMentions

from cogs.utils.api import API
from cogs.utils.data import PersistentDataManager

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
            'cogs.ext.commands.theotown',
            'cogs.ext.commands.utilities',
            'cogs.ext.commands.mod.punish',
            'cogs.ext.commands.mod.logs',

            # Events
            'cogs.ext.events.copypasta',
            'cogs.ext.events.initialization',
            'cogs.ext.events.message_forwarder',
            'cogs.ext.events.minecraft',
            'cogs.ext.events.reaction_handler',

            # Tasks
            'cogs.ext.tasks.automod',
            'cogs.ext.tasks.cronjobs',
            'cogs.ext.tasks.guild_statistics',
            'cogs.ext.tasks.plugin_store',
            'cogs.ext.tasks.punishment_handler',

            # Error handler
            'cogs.ext.error_handler',

            # Debugging tool jishaku
            'jishaku'
        ]
        self._connected = asyncio.Event()

        self.command_categories = []

        self.version_cache = {}

        self.config = config
        self.prefixes = self.config['prefixes']

        self.session = ClientSession(loop=self.loop)

        self.api = API(self, self.config['authentication']['database']["connection string"])

        self.use_experimental_embedding = False

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
        """Returns client version."""
        major, minor, patch, _ = __VERSION__
        if patch == 0:
            return f"{major}.{minor}"
        return f"{major}.{minor}.{patch}"

    @property
    def full_version(self) -> str:
        """Returns full client version."""
        major, minor, patch, channel = __VERSION__
        return f"{major}.{minor}.{patch}-{channel[:3]}"

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

    async def get_prefix(self, message):
        """Returns client prefix."""
        if not message.guild:
            # Only allow first defined prefix to be used in DMs
            return self.prefixes[0]
        return commands.when_mentioned_or(*self.prefixes)(self, message)

    def handle_reload(self):
        """Reloads all cogs of the client, excluding DB and API extensions.
        \nWarning: this is an experimental method and should not be depended on!"""
        logging.critical("Reloading bot configuration data and all cogs")
        for ext in self.extensions_to_load:
            self.unload_extension(ext)
        with open('./config.json') as data:
            self.config = json.load(data)
        for ext in self.extensions_to_load:
            self.load_extension(ext)

    def load_all_extensions(self):
        """Attempts to load all extensions as defined in client object."""
        for ext in self.extensions_to_load:
            logging.debug(f"Loading {ext}.")
            try:
                self.load_extension(ext)
                logging.debug(f"Successfully loaded {ext}.")
            except Exception:
                logging.exception(f"Failed to load {ext}.")

    def load_cogs(self):
        """Attempts to load all extensions as defined in client object."""
        logging.info("Starting the bot")
        self.load_all_extensions()

    def run(self, *args, **kwargs):
        """Runs the client."""
        try:
            self.loop.run_until_complete(self.start(self.token))
        except KeyboardInterrupt:
            pass
        except Exception:
            logging.critical("Fatal exception", exc_info=True)
        finally:
            self.loop.run_until_complete(self.session.close())
            self.loop.run_until_complete(self.close())
            for task in asyncio.all_tasks(self.loop):
                task.cancel()
            try:
                self.loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(self.loop)))
            except asyncio.CancelledError:
                logging.debug("All pending tasks has been cancelled.")
            finally:
                logging.info("Shutting down the bot")
