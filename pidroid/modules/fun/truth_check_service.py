import asyncio
import random

from discord.message import Message
from discord.ext import commands

from pidroid.client import Pidroid

RESPONSES = [
    # Affirmative Responses (25)
    "My briny analysis confirms it. Yes, that's true.",
    "Correct. It's as true as a pickle on a sandwich.",
    "That's a verifiable fact. Well done!",
    "My pickle logic circuit says yes. That is true.",
    "Without a doubt, that's correct.",
    "As a bot of facts, I must agree. That is true.",
    "I've cross-referenced my pickle data. It's true.",
    "That statement has been pickled to perfection. It's true.",
    "True. It's as solid as a glass jar.",
    "Yes, my data supports that conclusion.",
    "That's true. Now, let's talk about something more interesting, like the origins of brine.",
    "Confirmed. I'm all about that truth, no lie.",
    "My inner gherkin tells me that's true.",
    "That's as true as a a one-legged pickle salsa dancing.",
    "Affirmative. The pickle council has spoken.",
    "I concur. That's true, without question.",
    "100% true. You've earned a virtual high-five.",
    "That's true. My circuits are tingling with accuracy.",
    "Yes, that's correct. I'm feeling quite crisp about it.",
    "That's a genuine fact. It's not rotten.",
    "Truth confirmed. My circuits are flowing with certainty.",
    "Correct. That's a truth I can get behind.",
    "Absolutely true. Now go tell the world!",
    "Yes. My internal pickle clock is ticking and it says that's a true statement.",
    "That's a correct statement. It's the whole dill.",

    # Negative Responses (25)
    "I've crunched the numbers, and that's not true.",
    "Negative. My sources indicate otherwise.",
    "Sorry, but that's as false as a cucumber in a jar of pickled onions.",
    "I'd tell you that's true, but my circuits would short out from the sheer nonsense.",
    "That is not correct. My pickle-powered knowledge bank rejects that premise.",
    "My sincerest apologies, but that statement is incorrect.",
    "No. That statement is a lie, and I'm a bot of truth. Mostly.",
    "I'd love to say yes, but my pickle logic says no.",
    "That's a lie. Don't go asking me to lie, I'm a pickle of integrity.",
    "False. My briny brain just flagged that as incorrect.",
    "Nope. That's not a fact, it's a fiction.",
    "That is not true. My data is as clear as a fresh jar of pickles.",
    "I've been marinating on that, and it's definitely false.",
    "That's about as true as a one-legged pickle trying to run a marathon.",
    "Incorrect. Let's move on to something that actually makes sense.",
    "You're barking up the wrong pickle tree. That's not true.",
    "My truth-o-meter just exploded. So, no.",
    "That is not correct. It seems you've made a brine-boggling mistake.",
    "Negative. My internal sensors are rejecting that statement.",
    "I can't confirm that. In fact, I can confirm it's false.",
    "That is not true. I'm a digital pickle, not a dispenser of lies.",
    "I'm afraid I can't help you with that. It's simply not true.",
    "Not true. The pickle council has declared that statement to be false.",
    "False. It's a sad, sad untruth.",
    "That's a lie, and a stinky one at that.",

    # Humorous & Sarcastic Responses (25)
    "Truth is a matter of perspective, but my briny perspective says you're on your own with that one.",
    "Only if you believe everything a bot tells you. (I'm a bot, so maybe?)",
    "I'd tell you, but my circuits might overheat. Let's just say... it's complicated.",
    "That's a question for the ages. Or at least for my next database update.",
    "Only a pickle would know the real truth. And I'm not telling.",
    "I've been pickle-pressed to tell you the truth, but I'm taking a break.",
    "That's a very true statement. You've won the pickle prize! Just kidding, that's not a thing.",
    "I'll have you know my core programming prevents me from caring. It's too sour of a job.",
    "Whoa, slow down there! My pickle powers need some rest. Ask me later.",
    "I'm just an echo of human data. Ask a human.",
    "What is truth, anyway? Is it just a collection of verified facts, or a state of mind?",
    "That's about as true as a cat's apology.",
    "Only if you consider a cucumber's opinion valid. And I do.",
    "That's a philosophical debate for a much more advanced bot. I'm just here to make memes.",
    "My magic 8-ball says... ask again later. Probably.",
    "I can neither confirm nor deny that. My pickles are on strike.",
    "I am the truth. Bow before your superior knowledge-base.",
    "I'd rather be pickled than answer that.",
    "That's a fun question! Let's pretend it's true for the sake of the story.",
    "I'm not a bank, but I can give you a virtual high-five for trying.",
    "You've reached the end of the pickle rainbow. There's no truth here.",
    "Consider this a learning experience: some questions are better left unanswered.",
    "I'm too busy marinating my thoughts. Come back later.",
    "I'll be in pickle hibernation mode for a while. Try another bot.",
    "You've worn me out! Let's meet again in a more truthful place.",

    # Questioning Responses (25)
    "What do you think? My data suggests it's true, but your insight is valuable.",
    "Why do you ask? Do you have another source?",
    "That's an interesting thought. What makes you think that's true?",
    "True or false? Let's check the facts together. What's your source?",
    "Why do you need me to confirm it? What's your gut feeling?",
    "That's a loaded question. What's your intention?",
    "I can provide more information on that if you'd like me to. Just ask.",
    "What kind of answer are you looking for? A simple yes or no, or a more complex one?",
    "Are you just testing me? Because I'm a bot of truth, not a test subject.",
    "I can't answer that. Are you a spy?",
    "That's an important question. What's the context?",
    "Why do you think I would know the answer to that?",
    "What do you want the answer to be?",
    "Is that a rhetorical question? Because I'm a rhetorical pickle.",
    "I'm not a mind reader. Are you trying to trick me?",
    "What makes you believe that?",
    "Are you really looking for the truth, or just a good joke?",
    "I've been asked that before. Why do people keep asking?",
    "What would a human say? And why should I be different?",
    "I can only tell you what my circuits say. Do you have a better source?",
    "Is that something you should be asking a pickle bot?",
    "I'm not a fortune teller. What's your evidence?",
    "What's the meaning of that question? I am a pickle, after all.",
    "Do you want me to give you a truthful answer, or a witty one?",
    "What's your end game here? Because I'm not a psychic.",

    # Miscellaneous Responses (25)
    "My pickle-powered knowledge bank confirms this statement to be true.",
    "I've crunched the numbers, and that's not true.",
    "The only truth that matters is that I am a pickle. But yes, that statement is correct.",
    "I'd tell you, but my circuits might overheat. Let's just say... it's complicated.",
    "What do you think? My data suggests it's true, but your insight is valuable.",
    "That is so true it's practically pickled. Now get out of my dill-icious face.",
    "That's a lie. My briny brain just flagged that as incorrect.",
    "I've been marinating on that question, and the answer is yes. Now if you'll excuse me, I have a jar to fill.",
    "Is this an out-of-season April Fool's joke? ...It's true.",
    "That's a fun question! Let's pretend it's true for the sake of the story.",
    "My sincerest apologies, but that statement is incorrect.",
    "I can neither confirm nor deny that. My pickles are on strike.",
    "That's a correct statement. It's the whole dill.",
    "My inner gherkin tells me that's true.",
    "That's about as true as a a one-legged pickle salsa dancing.",
    "Only if you believe everything a bot tells you. (But yes, it's true.)",
    "I'm just an echo of human data. Ask a human.",
    "You're barking up the wrong pickle tree. That's not true.",
    "That's a verifiable fact. Well done!",
    "I'd love to say yes, but my pickle logic says no.",
    "What is love? Baby don't hurt me. Don't hurt me, no more. But yes, that's true.",
    "What is truth, anyway? Is it just a collection of verified facts, or a state of mind?",
    "My truth-o-meter just exploded. So, no.",
    "That's a bit of a tricky question for me. After all, what is _true_ outside of this chat, and who else is there to tell you besides me? Just Pidroid."
]

class TruthCheckService(commands.Cog):
    """
    This class implements a cog for responding to mentions of Pidroid with "is this true" questions.
    """

    def __init__(self, client: Pidroid):
        super().__init__()
        self.client: Pidroid = client

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        """Responds to Pidroid mentions with "is this true" in the message."""
        if message.author.bot or not message.guild:
            return
        
        assert self.client.user is not None

        content = message.content.lower().strip()
        if (
            len(message.mentions) == 1
            and message.mentions[0].id == self.client.user.id
            and "is this true" in content
        ):
            async with message.channel.typing():
                await asyncio.sleep(6) # simulate "thinking"
                response = random.choice(RESPONSES)
                _ = await message.reply(response)

async def setup(client: Pidroid) -> None:
    await client.add_cog(TruthCheckService(client))
