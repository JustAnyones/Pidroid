import os

from discord.mentions import AllowedMentions

ALLOWED_MENTIONS = AllowedMentions(everyone=False, replied_user=False)

PIDROID_ID = 700465365435678840

LOBBY_ID = 364343400461238272
JUSTANYONE_ID = 333871512496898059
ERKSMIT_ID = 308903727928967169
JESSE_ID = 1118969194680156240

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

# Pidroid file structure
DATA_FILE_PATH = os.path.join(os.getcwd(), 'data')
RESOURCE_FILE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')
TEMPORARY_FILE_PATH = os.path.join(DATA_FILE_PATH, 'temporary')
COOLDOWN_FILE_PATH = os.path.join(DATA_FILE_PATH, 'cooldowns')
