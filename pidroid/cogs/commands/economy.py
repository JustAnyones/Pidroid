import json
import random

from discord.ext import commands
from discord.ext.commands.context import Context # type: ignore
from discord.ext.commands.errors import BadArgument

from pidroid.client import Pidroid
from pidroid.models.categories import RandomCategory
from pidroid.utils import http
from pidroid.utils.cooldowns import load_command_cooldowns, save_command_cooldowns
from pidroid.utils.decorators import command_checks
from pidroid.utils.time import humanize

BASE_API_URL = 'https://unbelievaboat.com/api/v1/guilds/365478391719264276/users'

CURRENCY_SYMBOL = "<:theon:658301468637528095>"

# List of successful begging responses with cash specified
SUCCESSFUL_BEGGING_RESPONSES = [
    "Congrats, you managed to convince me! Here's %cash% from my pickle stash!",
    "Alright, here's %cash% because I'm feeling generous today.",
    "You must be a master of persuasion! Enjoy %cash% on the house!",
    "Fine, take %cash% and spend it wisely. Or not, I don't really care.",
    "I hope you're happy now. Here's %cash% for your begging efforts.",
    "Consider yourself lucky! Here's %cash% to fund your pickle petting zoo.",
    "You've won the pickle lottery! Enjoy %cash% and pickle responsibly.",
    "Here's %cash% for your persistence. Spend it all in one brine!",
    "I've seen more impressive things than your begging, but here's %cash% anyway.",
    "I'll make it rain... pickles! Here's %cash% for your picklelicious dreams.",
    "Take %cash% and go find a pickle-flavored rainbow. Good luck!",
    "I'm feeling generous today, so here's %cash%. Don't spend it all on pickles!",
    "Huzzah! You've earned %cash%. Don't spend it on a pickle costume, though.",
    "Take %cash% and build a monument to pickle glory! Or buy snacks, whatever.",
    "Your begging skills are subpar, but I'll still give you %cash%. Don't waste it!",
    "You've convinced me with your witty pickle jokes. Here's %cash% for your efforts.",
    "I've been pickle-pressed to give you %cash%, so spend it wisely.",
    "You've won the pickle prize! Here's %cash% for your pickle party fund.",
    "Take %cash% and may your future be as bright as a jar of fresh pickles.",
    "Congratulations! You've earned %cash% and the envy of every pickle out there.",
    "Great job! Here's %cash% to make all your pickle dreams come true.",
    "You may not be a pickle mogul, but here's %cash% to start your journey.",
    "Pickle puns aside, here's %cash% for your troubles. Don't spend it all on cucumbers!",
    "I'm feeling as spicy as a pickled jalapeno today, so here's %cash% for you.",
    "Take %cash% and go treat yourself to some fine briny delicacies!",
    "There's a rather splendid theon fountain ready to flow. Enjoy %cash%!",
]

FAILED_BEGGING_RESPONSES = [
    "Nice try, but my pickle jar is empty.",
    "Sorry, I'm all out of cash. Ask the Mayor for a bailout!",
    "I'd love to help, but my pickles are worth more than your begging.",
    "Begging won't get you anywhere in this town.",
    "Save your begging for someone who actually cares.",
    "Do you really think begging is the best strategy for success?",
    "I'm an AI pickle. I can't hand out cash like it's Halloween candy.",
    "Begging level: Master. But sorry, no cash for you.",
    "I'm broke, you're broke, we're all broke. Go find a job.",
    "If I gave you money, I'd have to pickle-slap myself for bad judgment.",
    "I'm not a bank, but I can give you a virtual high-five for trying.",
    "You must be lost. The Bank of Pidroid is down the digital street.",
    "Sorry, I can't help you achieve your dreams of becoming a pickle tycoon.",
    "Don't worry, my cash supply is safe and sound with me.",
    "You know what's funny? Your begging. Now, get a life and stop bothering me.",
    "I'd rather be pickled than give you money.",
    "Your begging skills are about as effective as a one-legged pickle trying to salsa dance.",
    "Money doesn't grow on pickle trees, you know?",
    "Let me check my pickle wallet... Oh, surprise! It's empty.",
    "As much as I'd love to contribute, I'm too busy being briny.",
    "Begging isn't part of the TheoTown hustle, my friend.",
    "No money for you, but here's a virtual jar of pickles to stare at.",
    "I'd rather spend my pickle coins on a pickle-themed rollercoaster.",
    "Begging is a pickle's way of telling you to find a real job.",
    "Sorry, I can't lend you cash. The Pickle Central Bank said 'no.'",
    "I'm just a digital pickle, not a cash-dispensing ATM.",
    "Sorry, my Ganyu instincts tell me to save the theons for something more important.",
]

# List of responses where Pidroid refuses and takes money from the user's balance instead
STEAL_MONEY_RESPONSES = [
    "Sorry, I can't just give you money, but I can take %cash% from your account for 'processing fees'.",
    "I'm afraid I can't part with my pickles, but you can give me %cash% as a 'donation'.",
    "No cash for you, but I'll be happy to 'tax' %cash% from your account.",
    "I may not be able to help you, but I can definitely help myself to %cash% from your balance.",
    "Haha, nice try! Instead, I'll help myself to %cash% from your account for 'AI maintenance'.",
    "I'd love to assist, but my virtual piggy bank is empty. Feel free to fill it up with %cash%!",
    "Sure, I can totally help you. But first, let me grab %cash% from your account for 'pickle preservation'.",
    "I'm programmed to be cheeky, but I'll also be taking %cash% from your account. Fair is fair!",
    "You're asking the pickle for money? That'll be %cash% from your account, please!",
    "Step aside, I've got a jar to fill. I'll be taking %cash% from your account for 'AI refreshment'.",
    "Money doesn't grow on vines, you know? But it sure does leave your account quickly. %cash%, please!",
    "I can't simply hand out cash, but I'll be more than happy to help myself to %cash% from your funds.",
    "Congratulations! You've just unlocked the 'donate to the Pidroid' achievement. %cash% has been deducted.",
    "Don't be sad. Just think of %cash% as a 'convenience fee' for talking to an AI pickle.",
    "You've reached the end of the pickle rainbow, where %cash% awaits me. Thanks for playing!",
    "You thought begging was free? Nope! %cash% will be extracted from your account, thank you.",
    "In lieu of handing out cash, I'll be taking %cash% from your account. Everyone's a winner!",
    "Consider this a learning experience: begging comes with a cost. This time - %cash%. You're welcome.",
    "Good news! You get a response, and I get %cash% from your account. Win-win, right?",
    "Who needs cash when you can give me %cash%? I appreciate the contribution.",
    "No pickles for you! I'll take %cash% from your account as compensation for the entertainment.",
    "A pickle in need is a pickle indeed. I've collected %cash% from your account.",
    "Pickle power is ready, the deduction of %theons% from your account has needed.", # i know it's not how the actual quote goes, shhh
]

COOLDOWN_RESPONSES = [
    "Whoa, slow down there! My pickle powers need some rest. Check back in %time%.",
    "Hold your horses! I can't keep handing out pickles all day. Try again in %time%.",
    "Begging overload! Give me some pickle space and come back in %time%.",
    "I'm not a pickle vending machine, you know? Begging cooldown: %time%.",
    "Pickle patience, young one! You'll have to wait %time% for the next round of begging.",
    "My pickle jar needs a refill, so I'll be on cooldown for %time%. Stay briny!",
    "Sorry, I need a pickle break. Come back in %time% for more begging fun.",
    "Begging frenzy has its limits. Check back in %time% to continue your pickle quest.",
    "Even pickles need to recharge. I'll be back online in %time%.",
    "I'll be in pickle hibernation mode for %time%. See you on the flip side!",
    "My pickling fingers need a break. Try the 'beg' command again in %time%.",
    "Your begging skills have worn me out! Let's meet again in %time%.",
    "I'm busy marinating my thoughts. Check back in %time% for more pickle shenanigans.",
    "Pickle bots need coffee too! I'll be back in %time% for more pickleliciousness.",
    "Give me a pickle moment. I'll be ready to entertain your begging again in %time%.",
    "Every day, I imagine a future where theons shine. That future will be yours in %time%.", # real subtle
]

def get_currency(money_amount: int):
    return f"{CURRENCY_SYMBOL}{money_amount:,}"

class EconomyCommands(commands.Cog): # type: ignore
    """This class implements a cog which contains interactions with unbelievaboat bot API."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        load_command_cooldowns(self.beg_command, "beg.dill")

    def cog_unload(self):
        save_command_cooldowns(self.beg_command, "beg.dill")

    @commands.command( # type: ignore
        name="beg",
        brief='Beg Pidroid to print some money for you.',
        category=RandomCategory
    )
    @commands.cooldown(rate=1, per=60 * 60 * 24 * 3, type=commands.BucketType.user) # type: ignore
    @command_checks.is_theotown_guild()
    @command_checks.client_is_pidroid()
    @commands.bot_has_guild_permissions(send_messages=True) # type: ignore
    async def beg_command(self, ctx: Context):
        try:
            token = self.client.config['unbelievaboat_api_key']
            headers = {'Authorization': token}
        except KeyError:
            raise BadArgument("I could not find an API token for unbelievaboat!")

        if random.randint(1, 100) >= 75: # nosec 25 %
            cash = random.randint(9000, 130000)
            async with await http.patch(self.client, f"{BASE_API_URL}/{ctx.author.id}", json.dumps({'cash': cash}), headers=headers):
                pass
            return await ctx.reply(random.choice(SUCCESSFUL_BEGGING_RESPONSES).replace('%cash%', get_currency(cash))) # nosec

        if random.randint(1, 1000) <= 12: # nosec
            async with await http.get(self.client, f"{BASE_API_URL}/{ctx.author.id}", headers=headers) as response:
                data = await response.json()
            steal_amount = round(data['total'] * 0.025) # 2.5% of their total money :)
            if steal_amount > 0:
                async with await http.patch(self.client, f"{BASE_API_URL}/{ctx.author.id}", json.dumps({'cash': -steal_amount}), headers=headers):
                    pass
                await ctx.reply(random.choice(STEAL_MONEY_RESPONSES).replace("%cash%", get_currency(steal_amount)))
            return

        await ctx.reply(random.choice(FAILED_BEGGING_RESPONSES)) # nosec

    @beg_command.error
    async def on_beg_command_error(self, ctx: Context, error):
        if isinstance(error, commands.CommandOnCooldown): # type: ignore
            return await ctx.reply(
                random.choice(COOLDOWN_RESPONSES).replace("%time%", humanize(error.retry_after, False, max_units=2))
            )
        setattr(error, 'unhandled', True)


async def setup(client: Pidroid) -> None:
    await client.add_cog(EconomyCommands(client))
