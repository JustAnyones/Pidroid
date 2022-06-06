import dill # type: ignore # nosec
import json
import random
import os

from discord.ext import commands
from discord.ext.commands.context import Context # type: ignore

from client import Pidroid
from constants import BEG_FAILURE_RESPONSES, BEG_SUCCESS_RESPONSES
from cogs.models import exceptions
from cogs.models.categories import RandomCategory
from cogs.utils import http
from cogs.utils.decorators import command_checks
from cogs.utils.embeds import ErrorEmbed
from cogs.utils.time import humanize

COOLDOWN_FILE_PATH = "./data/beg_cooldowns.p"
BASE_API_URL = 'https://unbelievaboat.com/api/v1/guilds/365478391719264276/users'

CURRENCY_SYMBOL = "<:theon:658301468637528095>"

def get_currency(money_amount: int):
    return f"{CURRENCY_SYMBOL}{money_amount:,}"


class EconomyCommands(commands.Cog): # type: ignore
    """This class implements a cog which contains interactions with unbelievaboat bot API."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        if os.path.exists(COOLDOWN_FILE_PATH):
            self.client.logger.info("Restoring cooldown buckets of beg command")
            with open(COOLDOWN_FILE_PATH, "rb") as f:
                self.beg._buckets._cache = dill.load(f) # nosec

    def cog_unload(self):
        self.client.logger.info("Saving cooldown buckets of beg command")
        with open(COOLDOWN_FILE_PATH, "wb") as f:
            dill.dump(self.beg._buckets._cache, f)

    @commands.command( # type: ignore
        brief='Beg Pidroid to print some money for you.',
        category=RandomCategory
    )
    @commands.cooldown(rate=1, per=60 * 60 * 24 * 3, type=commands.BucketType.user) # type: ignore
    @command_checks.is_theotown_guild()
    @command_checks.client_is_pidroid()
    @commands.bot_has_guild_permissions(send_messages=True) # type: ignore
    async def beg(self, ctx: Context):
        try:
            token = self.client.config['authentication']['unbelievaboat']['token']
            headers = {'Authorization': token}
        except KeyError:
            return await ctx.reply(embed=ErrorEmbed('I could not find an API token for unbelievaboat!'))

        if random.randint(1, 100) >= 75: # nosec 25 %
            cash = random.randint(9410, 78450)
            async with await http.patch(self.client, f"{BASE_API_URL}/{ctx.author.id}", json.dumps({'cash': cash}), headers=headers):
                pass
            return await ctx.reply(random.choice(BEG_SUCCESS_RESPONSES).replace('%cash%', get_currency(cash))) # nosec

        if random.randint(1, 1000) <= 12: # nosec
            async with await http.get(self.client, f"{BASE_API_URL}/{ctx.author.id}", headers=headers) as response:
                data = await response.json()
            steal_amount = round(data['total'] * 0.025) # 2.5% of their total money :)
            if steal_amount > 0:
                async with await http.patch(self.client, f"{BASE_API_URL}/{ctx.author.id}", json.dumps({'cash': -steal_amount}), headers=headers):
                    pass
                await ctx.reply(f'You know what, I think I need some funding myself. Let me borrow a fine amount of {get_currency(steal_amount)} from you!')
            return

        await ctx.reply(random.choice(BEG_FAILURE_RESPONSES)) # nosec

    @beg.error
    async def clear_error(self, ctx: Context, e):
        if isinstance(e, commands.CommandOnCooldown): # type: ignore
            await ctx.reply(f'Quit begging, you may ask me for money again in {humanize(e.retry_after, False, max_units=2)}.')
        elif isinstance(e, exceptions.ClientIsNotPidroid):
            self.beg.reset_cooldown(ctx)
            return
        else:
            await ctx.reply(embed=ErrorEmbed(e))


async def setup(client: Pidroid) -> None:
    await client.add_cog(EconomyCommands(client))
