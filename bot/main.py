# pyright: reportMissingImports=false

import asyncio
import json
import os
import sys
import aiohttp

from discord.ext import commands
from discord.ext.commands.context import Context # type: ignore

from client import Pidroid
from constants import DATA_FILE_PATH, TEMPORARY_FILE_PATH

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

async def main():  # noqa: C901

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
