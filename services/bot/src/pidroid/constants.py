from pathlib import Path

from discord.mentions import AllowedMentions

ALLOWED_MENTIONS = AllowedMentions(everyone=False, replied_user=False)

PIDROID_ID = 700465365435678840

LOBBY_ID = 364343400461238272
JUSTANYONE_ID = 333871512496898059
ERKSMIT_ID = 308903727928967169
JESSE_ID = 1118969194680156240

THEOTOWN_DEVELOPERS = [
    JUSTANYONE_ID,
    LOBBY_ID,
]

CHEESE_EATERS = [
    JUSTANYONE_ID,
    ERKSMIT_ID,
]

EMERGENCY_SHUTDOWN = [
    JUSTANYONE_ID,
    LOBBY_ID,
    ERKSMIT_ID,
]

EMBED_COLOUR = 5928495

# Common constants used for command checking whether they are guild specific
THEOTOWN_GUILD = 365478391719264276

# Pidroid file structure
DATA_FILE_PATH = Path(Path.cwd()) / "data"
RESOURCE_FILE_PATH = Path(__file__).resolve().parent / "resources"
TEMPORARY_FILE_PATH = DATA_FILE_PATH / "temporary"
COOLDOWN_FILE_PATH = DATA_FILE_PATH / "cooldowns"
