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
