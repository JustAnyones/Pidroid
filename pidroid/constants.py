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

# Common constants used for command checking whether they are guild specific
THEOTOWN_GUILD = 365478391719264276
BOT_COMMANDS_CHANNEL = 367299681635794954

# Pidroid file structure
DATA_FILE_PATH = os.path.join(os.getcwd(), 'data')
RESOURCE_FILE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')
CACHE_FILE_PATH = os.path.join(DATA_FILE_PATH, 'cache.json')
TEMPORARY_FILE_PATH = os.path.join(DATA_FILE_PATH, 'temporary')
COOLDOWN_FILE_PATH = os.path.join(DATA_FILE_PATH, 'cooldowns')

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
