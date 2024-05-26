import discord
import os
import platform
import psutil
import sys

from discord.ext import commands
from discord.ext.commands import Context
from discord.message import Message

from pidroid.client import Pidroid
from pidroid.constants import ALLOWED_MENTIONS
from pidroid.models.categories import BotCategory
from pidroid.utils.embeds import PidroidEmbed
from pidroid.utils.time import humanize, timestamp_to_date, utcnow

class BotCommandCog(commands.Cog):
    """This class implements cog which contains commands primarily used to diagnose Pidroid."""

    def __init__(self, client: Pidroid):
        super().__init__()
        self.client = client

    @commands.command(
        name="ping",
        brief='Returns the ping of the bot.',
        category=BotCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.cooldown(rate=1, per=1, type=commands.BucketType.user)
    async def ping_command(self, ctx: Context[Pidroid]):
        msg: Message = await ctx.reply("**Pinging...**")
        client_ping = round((msg.created_at.timestamp() - ctx.message.created_at.timestamp()) * 1000)
        api_ping = round(self.client.latency * 1000)
        embed = PidroidEmbed(description=f':stopwatch: {client_ping}ms\n\n:heartbeat: {api_ping}ms')
        return await msg.edit(content='Pong!', embed=embed, allowed_mentions=ALLOWED_MENTIONS)

    @commands.command(
        name="invite",
        brief='Returns an invite link for the bot.',
        category=BotCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def invite_command(self, ctx: Context[Pidroid]):
        return await ctx.reply('You can invite the bot to your server with the following url: https://pidroid.svetikas.lt/invite')

    @commands.command(
        name="info",
        brief='Returns general information about the bot.',
        category=BotCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def info_command(self, ctx: Context[Pidroid], mode: str | None):
        async with ctx.typing():
            # Fetch data from config file
            version = self.client.version

            if self.client.client_version.commit_id != '':
                version += f" ([{self.client.client_version.commit_id}](https://github.com/JustAnyones/Pidroid/commit/{self.client.client_version.commit_id}))"

            # Fetch application information from datcord
            app_info = await self.client.application_info()
            if app_info.team is not None:
                owner_name, owner_id = (app_info.team.name, app_info.team.id)
            else:
                owner_name, owner_id = (str(app_info.owner), app_info.owner.id)

            # Fetch process information
            process_id = os.getpid()
            process = psutil.Process(process_id)

            # Data associated with process
            start_time = process.create_time()
            memory = process.memory_full_info()
            used_memory = round(memory.rss / 1024 / 1024, 2)

            current_timestamp = utcnow().timestamp()

            uptime = humanize(current_timestamp - start_time, False, max_units=3)
            
            assert self.client.user is not None

            if mode == "extended" and await self.client.is_owner(ctx.author):
                total_memory = round(psutil.virtual_memory().total / 1024 / 1024, 2)
                extended_message = (
                    f'```{self.client.user.name} ({self.client.user.id}) build {version} information\n\n'
                    f'* The bot (PID {process_id}) is running on {process.num_threads()}'
                    f' threads on {platform.system()} ({platform.release()} {platform.version()})'
                    f' which was started on {timestamp_to_date(int(psutil.boot_time()), "hybrid")}\n'
                    f'* Python version: {sys.version}\n'
                    f'* Discord.py version: {discord.__version__}\n'
                    f'* Bot uptime: {uptime} started on {timestamp_to_date(int(start_time), "hybrid")}\n'
                    f'* Owner: {owner_name} ({owner_id})\n'
                    f'* CPU usage: {process.cpu_percent(interval=1.0)}%\n'
                    f'* RAM usage: {used_memory}/{total_memory} MB ({round(process.memory_percent(), 2)}%)```'
                )
                return await ctx.reply(extended_message)

            embed = PidroidEmbed(title=f'{self.client.user.name} status', description=f'{self.client.user.name} is a custom made discord bot by JustAnyone, designed for the TheoTown community.')
            embed.add_field(name='Uptime', value=uptime, inline=True)
            embed.add_field(name='Version', value=version, inline=True)
            if app_info.team is None:
                embed.add_field(name='Owner', value=f'{owner_name}', inline=True)
            else:
                embed.add_field(name='Team', value=f'{owner_name}', inline=True)
            embed.add_field(name='Servers', value=f'{len(self.client.guilds):,} ({len(self.client.users):,} users cached)', inline=True)
            embed.add_field(name='RAM usage', value=f'{used_memory} MB', inline=True)
            embed.add_field(name='Current bot time', value=timestamp_to_date(int(current_timestamp), 'custom'), inline=False)
            return await ctx.reply(embed=embed)


async def setup(client: Pidroid):
    await client.add_cog(BotCommandCog(client))
