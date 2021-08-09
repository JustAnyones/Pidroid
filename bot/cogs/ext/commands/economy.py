import dill
import json
import random
import os

from discord.ext import commands
from discord.ext.commands.context import Context

from client import Pidroid
from constants import BEG_FAILURE_RESPONSES, BEG_SUCCESS_RESPONSES
from cogs.models import exceptions
from cogs.models.categories import RandomCategory
from cogs.utils import http
from cogs.utils.decorators import command_checks
from cogs.utils.embeds import error
from cogs.utils.time import humanize

COOLDOWN_FILE_PATH = "./data/beg_cooldowns.p"
BASE_API_URL = 'https://unbelievaboat.com/api/v1/guilds/365478391719264276/users'


class EconomyCommands(commands.Cog):
    """This class implements a cog which contains interactions with unbelievaboat bot API."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        if os.path.exists(COOLDOWN_FILE_PATH):
            self.client.logger.info("Restoring cooldown buckets of beg command")
            with open(COOLDOWN_FILE_PATH, "rb") as f:
                self.beg._buckets._cache = dill.load(f) # noqa (bandit B301)

    def cog_unload(self):
        self.client.logger.info("Saving cooldown buckets of beg command")
        with open(COOLDOWN_FILE_PATH, "wb") as f:
            dill.dump(self.beg._buckets._cache, f)

    @commands.command(
        brief='Beg Pidroid to print some money for you.',
        category=RandomCategory
    )
    @commands.cooldown(rate=1, per=60 * 60 * 24 * 3, type=commands.BucketType.user)
    @command_checks.is_theotown_guild()
    @command_checks.client_is_pidroid()
    @commands.bot_has_guild_permissions(send_messages=True)
    async def beg(self, ctx: Context):
        try:
            token = self.client.config['authentication']['unbelievaboat']['token']
            headers = {'Authorization': token}
        except KeyError:
            await ctx.reply(embed=error('I could not find a token for unbelievaboat!'))
            return

        if random.randint(1, 100) >= 75: # 25 %
            cash = random.randint(9410, 78450)
            async with await http.patch(self.client, f"{BASE_API_URL}/{ctx.author.id}", json.dumps({'cash': cash}), headers=headers):
                pass
            await ctx.reply(random.choice(BEG_SUCCESS_RESPONSES).replace('%cash%', f'{cash:,} <:theon:658301468637528095>'))
            return
        if random.randint(1, 1000) <= 12:
            async with await http.get(self.client, f"{BASE_API_URL}/{ctx.author.id}", headers=headers) as response:
                data = await response.json()
            steal_amount = data['total'] * 0.025 # 2.5% of their total money :)
            if steal_amount > 0:
                async with await http.patch(self.client, f"{BASE_API_URL}/{ctx.author.id}", json.dumps({'cash': -steal_amount}), headers=headers):
                    pass
                await ctx.reply(f'You know what, I think I need some funding myself. Let me take a fine amount of {steal_amount:,} <:theon:658301468637528095>')
        await ctx.reply(random.choice(BEG_FAILURE_RESPONSES))

    @beg.error
    async def clear_error(self, ctx: Context, e):
        if isinstance(e, commands.CommandOnCooldown):
            await ctx.reply(f'Quit begging, you may ask me for money again in {humanize(e.retry_after, False, max_units=2)}.')
        elif isinstance(e, exceptions.ClientIsNotPidroid):
            self.beg.reset_cooldown(ctx)
            return
        else:
            await ctx.reply(embed=error(e))


def setup(client: Pidroid) -> None:
    client.add_cog(EconomyCommands(client))
