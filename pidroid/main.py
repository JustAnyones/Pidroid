# pyright: reportMissingImports=false

import aiohttp
import asyncio
import os
import sys

from argparse import ArgumentParser
from discord.ext import commands
from discord.ext.commands.context import Context # type: ignore

# Allows us to not set the Python path
sys.path.append(os.getcwd())

from pidroid.client import Pidroid
from pidroid.constants import DATA_FILE_PATH, TEMPORARY_FILE_PATH

# Use uvloop if possible
try:
    import uvloop # type: ignore # If my calculations are correct, when this baby hits eighty-eight miles per hour you're gonna see some serious shit
    uvloop.install()
except ImportError:
    pass
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# Use selector event loop since proactor has some issues
if sys.platform == 'win32':
    from asyncio import WindowsSelectorEventLoopPolicy
    asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

def load_env_from_file(path: str) -> None:
    print("Loading environment from a file")
    with open(path) as f:
        for l in f.readlines():
            key, value = l.split("=", 1)
            os.environ[key] = value.strip().replace("$$", "$")

def config_from_env() -> dict:

    if os.environ.get("TOKEN", None) is None:
        exit("No bot token was specified. Please specify it using the TOKEN environment variable.")
    

    if os.environ.get("POSTGRES_DSN", None) is None:
        exit("No Postgres DSN was specified. Please specify it using the POSTGRES_DSN environment variable.")

    prefix_string = os.environ.get("PREFIXES", "P, p, TT")
    prefixes = [p.strip() for p in prefix_string.split(",")]

    return {
        "token": os.environ["TOKEN"],
        "prefixes": prefixes,

        "mongo_dsn": os.environ["MONGO_DSN"],
        "postgres_dsn": os.environ.get("POSTGRES_DSN"),

        "tt_api_key": os.environ.get("TT_API_KEY"),
        "deepl_api_key": os.environ.get("DEEPL_API_KEY"),
        "tenor_api_key": os.environ.get("TENOR_API_KEY"),
        "unbelievaboat_api_key": os.environ.get("UNBELIEVABOAT_API_KEY"),
        "github_token": os.environ.get("GITHUB_TOKEN"),

        "bitly_login": os.environ.get("BITLY_LOGIN"),
        "bitly_api_key": os.environ.get("BITLY_API_KEY"),

        "reddit_client_id": os.environ.get("REDDIT_CLIENT_ID"),
        "reddit_client_secret": os.environ.get("REDDIT_CLIENT_SECRET"),
        "reddit_username": os.environ.get("REDDIT_USERNAME"),
        "reddit_password": os.environ.get("REDDIT_PASSWORD"),
    }

async def main():  # noqa: C901

    # Create directories in case they don't exist
    if not os.path.exists(DATA_FILE_PATH):
        os.mkdir(DATA_FILE_PATH)
    if not os.path.exists(TEMPORARY_FILE_PATH):
        os.mkdir(TEMPORARY_FILE_PATH)

    arg_parser = ArgumentParser()
    arg_parser.add_argument("-e", "--envfile", help="specifies .env file to load environment from")

    args = arg_parser.parse_args()
    if args.envfile:
        load_env_from_file(args.envfile)

    # Load configuration from environment
    bot = Pidroid(config_from_env())

    @bot.command(hidden=True)
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def reload(ctx: Context):
        try:
            await bot.handle_reload()
            await ctx.reply('The entirety of the bot has been reloaded!')
        except Exception as e:
            await ctx.reply(f'The following exception occurred while trying to reload the bot:\n```{e}```')

    async with aiohttp.ClientSession() as session:
        async with bot:
            bot.session = session
            await bot.start(bot.token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
