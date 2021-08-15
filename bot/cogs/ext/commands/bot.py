import discord
import platform
import psutil
import os
import sys

from discord.ext import commands
from discord.ext.commands.context import Context
from discord.message import Message

from client import Pidroid
from constants import ALLOWED_MENTIONS
from cogs.models.categories import BotCategory
from cogs.utils.embeds import build_embed
from cogs.utils.time import humanize, timestamp_to_date, utcnow

COMMANDS_PER_PAGE = 6


class BotCommands(commands.Cog):
    """This class implements cog which contains commands primarily used to diagnose Pidroid."""

    def __init__(self, client: Pidroid):
        self.client = client

    @commands.command(
        brief='Returns ping of the bot and the Discord websocket.',
        category=BotCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.cooldown(rate=1, per=1, type=commands.BucketType.user)
    async def ping(self, ctx: Context):
        async with ctx.typing():
            msg: Message = await ctx.reply("**Pinging...**")
            client_ping = round((msg.created_at.timestamp() - ctx.message.created_at.timestamp()) * 1000)
            api_ping = round(self.client.latency * 1000)
            embed = build_embed(description=f':stopwatch: {client_ping}ms\n\n:heartbeat: {api_ping}ms')
            await msg.edit(content='Pong!', embed=embed, allowed_mentions=ALLOWED_MENTIONS)

    @commands.command(
        brief='Returns invite link for the bot.',
        category=BotCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def invite(self, ctx: Context):
        await ctx.reply('You can invite the bot to your server with the following url: https://ja.theotown.com/pidroid/invite')

    @commands.command(
        brief='Returns general information about the bot.',
        category=BotCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def info(self, ctx: Context, mode: str = None):
        async with ctx.typing():
            # Fetch data from config file
            version = self.client.version

            # Fetch application information from datcord
            app_info = await self.client.application_info()
            if app_info.team is not None:
                owner_name, owner_id = (app_info.team.name, app_info.team.id)
            else:
                owner_name, owner_id = (app_info.owner, app_info.owner.id)

            # Fetch process information
            process_id = os.getpid()
            process = psutil.Process(process_id)

            # Data associated with process
            start_time = process.create_time()
            memory = process.memory_full_info()
            used_memory = round(memory.rss / 1024 / 1024, 2)

            current_timestamp = utcnow().timestamp()

            uptime = humanize(current_timestamp - start_time, False, max_units=3)

            if mode == "extended" and await self.client.is_owner(ctx.author):
                total_memory = round(psutil.virtual_memory().total / 1024 / 1024, 2)
                extended_message = (
                    f'```{self.client.user.name} ({self.client.user.id}) build {version} information\n\n'
                    f'* The bot (PID {process_id}) is running on {process.num_threads()} threads on {platform.system()} ({platform.release()} {platform.version()}) which was started on {timestamp_to_date(psutil.boot_time(), "hybrid")}\n'
                    f'* Python version: {sys.version}\n'
                    f'* Discord.py version: {discord.__version__}\n'
                    f'* Bot uptime: {uptime} started on {timestamp_to_date(int(start_time), "hybrid")}\n'
                    f'* Owner: {owner_name} ({owner_id})\n'
                    f'* CPU usage: {process.cpu_percent(interval=1.0)}%\n'
                    f'* RAM usage: {used_memory}/{total_memory} MB ({round(process.memory_percent(), 2)}%)```'
                )
                await ctx.reply(extended_message)
                return

            embed = build_embed(title=f'{self.client.user.name} status', description=f'{self.client.user.name} is a custom made discord bot by JustAnyone, designed to be used inside the official TheoTown discord.')
            embed.add_field(name='Uptime', value=uptime, inline=True)
            embed.add_field(name='Version', value=version, inline=True)
            if app_info.team is None:
                embed.add_field(name='Owner', value=f'{owner_name}', inline=True)
            else:
                embed.add_field(name='Team', value=f'{owner_name}', inline=True)
            embed.add_field(name='Servers', value=f'{len(self.client.guilds):,} ({len(self.client.users):,} users)', inline=True)
            embed.add_field(name='RAM usage', value=f'{used_memory} MB', inline=True)
            embed.add_field(name='Current time', value=timestamp_to_date(int(current_timestamp), 'custom'), inline=False)
            await ctx.reply(embed=embed)


def setup(client):
    client.add_cog(BotCommands(client))
