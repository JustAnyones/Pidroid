import dill
import logging
import os

from discord.ext import commands

from pidroid.constants import COOLDOWN_FILE_PATH

logger = logging.getLogger("Pidroid")

def _get_cooldown_file(filename: str) -> str:
    """Returns path to the cooldown file by the specified name."""
    if not os.path.exists(COOLDOWN_FILE_PATH):
        os.mkdir(COOLDOWN_FILE_PATH)
    return os.path.join(COOLDOWN_FILE_PATH, filename)

def save_command_cooldowns(command: commands.Command, filename: str) -> None:
    """Saves command cooldowns to a file by using dill."""
    cooldown_file = _get_cooldown_file(filename)
    logger.debug(f"Saving cooldown buckets of {command.name} command")
    with open(cooldown_file, "wb") as f:
        dill.dump(command._buckets._cache, f) # pyright: ignore[reportUnknownMemberType, reportPrivateUsage]
    
def load_command_cooldowns(command: commands.Command, filename: str) -> None:
    """Loads command cooldowns from a dill file."""
    cooldown_file = _get_cooldown_file(filename)
    if os.path.exists(cooldown_file):
        logger.debug(f"Restoring cooldown buckets of {command.name} command")
        with open(cooldown_file, "rb") as f:
            command._buckets._cache = dill.load(f) # pyright: ignore[reportUnknownMemberType, reportPrivateUsage]

