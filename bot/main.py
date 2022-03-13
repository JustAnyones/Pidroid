# pyright: reportMissingImports=false

import asyncio
import json
import os
import sys

from discord.ext import commands
from discord.ext.commands.context import Context

from client import Pidroid
from constants import DATA_FILE_PATH, TEMPORARY_FILE_PATH

# Use uvloop if possible
try:
    import uvloop # If my calculations are correct, when this baby hits eighty-eight miles per hour you're gonna see some serious shit
    uvloop.install()
except ImportError:
    pass
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# Use selector event loop since proactor has some issues
if sys.platform == 'win32':
    from asyncio import WindowsSelectorEventLoopPolicy
    asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

def troll_erk():
    import subprocess
    import random

    urls = [
        "https://nekobot.xyz/imagegen/a/a/c/857b16eddc3c22a65b78e8d431a22.mp4",
        "https://www.youtube.com/watch?v=veaKOM1HYAw",
        "https://www.youtube.com/watch?v=UIp6_0kct_U",
        "https://www.youtube.com/watch?v=h_JJm5ETNSA"
    ]

    if sys.platform == "win32":
        r = subprocess.run('powershell [Environment]::UserName', capture_output=True)

        user_name = r.stdout.decode("utf-8").strip()
        has_tt_folder = os.path.exists(os.path.join(os.environ["userprofile"], "TheoTown"))

        # We do a miniscule amount of trolling
        if user_name == "eriks" and has_tt_folder:
            subprocess.run([
                'powershell',
                f'[system.Diagnostics.Process]::Start("firefox", "{random.choice(urls)}")'
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():  # noqa: C901
    troll_erk()

    # Create directories in case they don't exist
    if not os.path.exists(DATA_FILE_PATH):
        os.mkdir(DATA_FILE_PATH)
    if not os.path.exists(TEMPORARY_FILE_PATH):
        os.mkdir(TEMPORARY_FILE_PATH)

    # Load config file
    with open('./config.json') as data:
        config = json.load(data)

    bot = Pidroid(config)

    @bot.command(hidden=True)
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def reload(ctx: Context):
        try:
            bot.handle_reload()
            await ctx.reply('The entirety of the bot has been reloaded!')
        except Exception as e:
            await ctx.reply(f'The following exception occurred while trying to reload the bot:\n```{e}```')

    bot.run()


if __name__ == "__main__":
    main()
