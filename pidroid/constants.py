import os

from discord.mentions import AllowedMentions

ALLOWED_MENTIONS = AllowedMentions(everyone=False, replied_user=False)

PIDROID_ID = 700465365435678840

LOBBY_ID = 364343400461238272
JUSTANYONE_ID = 333871512496898059
ERKSMIT_ID = 308903727928967169
JESSE_ID = 272477590663462922

THEOTOWN_DEVELOPERS = [
    JUSTANYONE_ID,
    LOBBY_ID
]

CHEESE_EATERS = [
    JUSTANYONE_ID,
    ERKSMIT_ID
]

EMERGENCY_SHUTDOWN = [
    JUSTANYONE_ID,
    LOBBY_ID,
    ERKSMIT_ID
]

EMBED_COLOUR = 5928495

THEOTOWN_FORUM_URL = "https://forum.theotown.com"

# Constants used for command checking whether they are guild specific
THEOTOWN_GUILD = 365478391719264276
SPOILERS_CHANNEL = 416906073207996416
EVENTS_CHANNEL = 371731826601099264
SUGGESTIONS_CHANNEL = 409800607466258445
BOT_COMMANDS_CHANNEL = 367299681635794954


# Lobster's Kitchen Minecraft server
MINECRAFT_LISTENER_GUILD = 822246810961182742
MINECRAFT_LISTENER_CHANNEL = 823215670534733824
MINECRAFT_LISTENER_USER = 823210405295292416

# Pidroid file structure
DATA_FILE_PATH = os.path.join(os.getcwd(), 'data')
RESOURCE_FILE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')
CACHE_FILE_PATH = os.path.join(DATA_FILE_PATH, 'cache.json')
TEMPORARY_FILE_PATH = os.path.join(DATA_FILE_PATH, 'temporary')
COOLDOWN_FILE_PATH = os.path.join(DATA_FILE_PATH, 'cooldowns')

# Used for fact command
FACTS = [
    'Javascript isn\'t the greatest programming language in the world, but at least it counts its arrays from 0 unlike some other languages...',
    'RemainsStay is a lovely sloth administrator of TheoTown server.',
    'Ene7 is our detective pingu.',
    'Evan? Oh, you mean that helpful firetruck. Yeah, he\'s awesome.',
    'Lobby is an entranceway or foyer in a building. What? That\'s not what Lobby is?',
    'I\'ve heard a user by the name of The26 likes ducks. I suggest you send them a duck picture.',
    'Yo, Q||_REMOVED_||02, do you know where I can get some of them wide monitors you have?',
    'KolaKattz? Nope, never heard of him. Have you?',
    'I have multiple brothers, one of them is named Pidroid Beta. Perhaps you\'ve met him already?',
    'This bot is built using discord.py wrapper made by an awesome guy called Rapptz.',
    'Man, the other day I was searching for some medic bags and I couldn\'t find any. They are all gone!',
    'Yes, *kentucky* fried chicken is indeed my good friend',
    'Did I ever tell you the definition of insanity? No? Welp, I can\'t just do it now!',
    'Lucas King is a great musician with the great soundtrack he made for the game.',
    'NOLOGIC? ah, it is a secret gamemode which is broken in every way possible. It very familiar to sandbox mode.',
    'This fact feature was introduced in version 2.8.0 of Pidroid, with later versions expanding the facts.',
    'January 15th is Fire Truck Appreciation Day!',
    'Jesse does indeed like to talk, he doesn\'t like starting the conversation though.',
    'The name of DSA agency has no meaning.',
    'The name Theo comes from a previous developer of the game named theotheoderich.',
    'Ever wanted to reset your in-game progress and get an achievement for that? Just open the developer console of the game and run ``rm -rf /theotown``'
]

# Used for responding to suggest command outside of bot-commands channel
REFUSE_COMMAND_RESPONSES = [
    'I do not recommend using my commands here. Perhaps there\'s a better channel for that?',
    'It wouldn\'t be wise to run your command here, therefore, I won\'t.',
    'You may not run your command here.',
    'Sorry, I cannot do that here.'
]

# Used for beg command of the economy cog
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
