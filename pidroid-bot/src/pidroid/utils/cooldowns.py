import logging
from pathlib import Path

import dill
from discord.ext import commands

from pidroid.constants import COOLDOWN_FILE_PATH

logger = logging.getLogger("pidroid.utils.cooldowns")

def _get_cooldown_file(filename: str) -> Path:
    """Return path to the cooldown file by the specified name."""
    if not COOLDOWN_FILE_PATH.exists():
        COOLDOWN_FILE_PATH.mkdir()
    return COOLDOWN_FILE_PATH / filename

def save_command_cooldowns(command: commands.Command, filename: str) -> None:
    """Save command cooldowns to a file by using dill."""
    cooldown_file = _get_cooldown_file(filename)
    logger.debug("Saving cooldown buckets of %s command", command.name)

    with cooldown_file.open("wb") as f:
        dill.dump(command._buckets._cache, f) # pyright: ignore[reportUnknownMemberType, reportPrivateUsage]

def load_command_cooldowns(command: commands.Command, filename: str) -> None:
    """Load command cooldowns from a dill file."""
    cooldown_file = _get_cooldown_file(filename)
    if cooldown_file.exists():
        logger.debug("Restoring cooldown buckets of %s command", command.name)
        with cooldown_file.open("rb") as f:
            command._buckets._cache = dill.load(f) # pyright: ignore[reportUnknownMemberType, reportPrivateUsage]

