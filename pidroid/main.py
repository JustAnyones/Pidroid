import aiohttp
import asyncio
import os
import signal
import sys
import logging

from alembic.config import CommandLine
from discord.ext import commands
from discord.ext.commands import Context

from pidroid.client import Pidroid
from pidroid.constants import DATA_FILE_PATH, TEMPORARY_FILE_PATH
from pidroid.utils.types import ConfigDict # noqa: E402

# Use uvloop if possible
try:
    import uvloop # pyright: ignore[reportMissingImports]
    uvloop.install() # pyright: ignore[reportUnknownMemberType]
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy()) # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType]
except ImportError:
    pass
    

# Use selector event loop since proactor has some issues
if sys.platform == 'win32':
    from asyncio import WindowsSelectorEventLoopPolicy
    asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

logger = logging.getLogger("Pidroid")

def get_postgres_dsn() -> str:
    postgres_dsn = os.environ.get("POSTGRES_DSN", None)
    if postgres_dsn == '':
        postgres_dsn = None
    if postgres_dsn is None:
        logger.debug("POSTGRES_DSN variable was not found, attempting to resolve from postgres variables")
        
        user = os.environ.get("DB_USER", None)
        password = os.environ.get("DB_PASSWORD", None)
        host = os.environ.get("DB_HOST", "127.0.0.1")
        
        if user is None or password is None:
            logger.critical((
                "Unable to create a postgres DSN string. "
                "DB_USER or DB_PASSWORD environment variable is missing."
            ))
            exit()
        postgres_dsn = "postgresql+asyncpg://{}:{}@{}".format(user, password, host)
    return postgres_dsn

def config_from_env() -> ConfigDict:
    postgres_dsn = get_postgres_dsn()

    prefix_string = os.environ.get("PREFIXES", "P, p, TT")
    prefixes = [p.strip() for p in prefix_string.split(",")]
    
    debugging = False
    if os.environ.get("DEBUGGING", "0").lower() in ['1', 'true']:
        debugging = True
        logger.info("Debugging mode is enabled")
        logger.setLevel(logging.DEBUG)

    return {
        "debugging": debugging,
        
        "token": os.environ["TOKEN"],
        "prefixes": prefixes,

        "postgres_dsn": postgres_dsn,

        "tt_api_key": os.environ.get("TT_API_KEY"),
        "deepl_api_key": os.environ.get("DEEPL_API_KEY"),
        "tenor_api_key": os.environ.get("TENOR_API_KEY"),
        "unbelievaboat_api_key": os.environ.get("UNBELIEVABOAT_API_KEY")
    }

def migrate():
    CommandLine("alembic").main(["upgrade", "head"])

def _register_reload_command(bot: Pidroid):
    """Registers the cog reload command for the bot."""

    @bot.command(hidden=True)
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def reload(ctx: Context[Pidroid]): # pyright: ignore[reportUnusedFunction]
        try:
            await bot.handle_reload()
            _ = await ctx.reply('The entirety of the bot has been reloaded!')
        except Exception as e:
            _ = await ctx.reply(f'The following exception occurred while trying to reload the bot:\n```{e}```')

async def _start_bot(bot: Pidroid):
    """Starts the bot."""

    # Handle docker's sigterm signal gracefully
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(
        signal.SIGTERM,
        lambda: loop.create_task(bot.close())
    )

    # Do the actual startup
    async with aiohttp.ClientSession() as session:
        async with bot:
            bot.session = session
            await bot.start(bot.token)

def main():

    # Create directories in case they don't exist
    if not os.path.exists(DATA_FILE_PATH):
        os.mkdir(DATA_FILE_PATH)
    if not os.path.exists(TEMPORARY_FILE_PATH):
        os.mkdir(TEMPORARY_FILE_PATH)

    if os.environ.get("TOKEN", None) is None:
        exit("No bot token was specified. Please specify it using the TOKEN environment variable.")

    # Create Pidroid instance with configuration from environment
    bot = Pidroid(config_from_env())

    # Register core commands
    _register_reload_command(bot)

    try:
        asyncio.run(_start_bot(bot))
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
