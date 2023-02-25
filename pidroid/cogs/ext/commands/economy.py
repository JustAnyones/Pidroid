import json
import random

from discord.ext import commands
from discord.ext.commands.context import Context # type: ignore
from discord.ext.commands.errors import BadArgument

from pidroid.client import Pidroid
from pidroid.cogs.models.categories import RandomCategory
from pidroid.cogs.utils import http
from pidroid.cogs.utils.cooldowns import load_command_cooldowns, save_command_cooldowns
from pidroid.cogs.utils.decorators import command_checks
from pidroid.cogs.utils.time import humanize

BASE_API_URL = 'https://unbelievaboat.com/api/v1/guilds/365478391719264276/users'

CURRENCY_SYMBOL = "<:theon:658301468637528095>"

BEG_SUCCESS_RESPONSES = [
    'Ugh, fine, I guess you are my little pogchamp, come here, I\'ll give you %cash%.',
    'I am feeling nice today, so here, have a handsome sum of %cash%!',
    'Pssst, have some %cash%, because you\'re so nice to talk to!',
    'Your prayers have been answered. You may now have %cash%!'
]

BEG_FAILURE_RESPONSES = [
    'I wish I could give you some shinies, but I won\'t.',
    'Congratulations, you did beg me for the shiny theons, however I do not feel generous this time.',
    'I apologize, I gave my funds to someone else. Maybe next time?',
    'Uh, oh, I have an important meeting to attend. Sorry, I\'ll catch you later.'
]

def get_currency(money_amount: int):
    return f"{CURRENCY_SYMBOL}{money_amount:,}"

class EconomyCommands(commands.Cog): # type: ignore
    """This class implements a cog which contains interactions with unbelievaboat bot API."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        load_command_cooldowns(self.beg, "beg.dill")

    def cog_unload(self):
        save_command_cooldowns(self.beg, "beg.dill")

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
            token = self.client.config['unbelievaboat_api_key']
            headers = {'Authorization': token}
        except KeyError:
            raise BadArgument("I could not find an API token for unbelievaboat!")

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
    async def on_beg_command_error(self, ctx: Context, error):
        if isinstance(error, commands.CommandOnCooldown): # type: ignore
            return await ctx.reply(
                f'Quit begging, you may ask me for money again in {humanize(error.retry_after, False, max_units=2)}.'
            )
        setattr(error, 'unhandled', True)


async def setup(client: Pidroid) -> None:
    await client.add_cog(EconomyCommands(client))
