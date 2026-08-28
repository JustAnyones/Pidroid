import logging
import os
import sys
from argparse import ArgumentParser
from importlib import metadata
from pathlib import Path

from dotenv import load_dotenv

# Set up logging
formatter = logging.Formatter("[%(asctime)s %(name)s:%(levelname)s]: %(message)s", "%Y-%m-%d %H:%M:%S")
# Set up root logger and legacy logger for compatibility
root_logger = logging.getLogger("pidroid")
root_logger_legacy = logging.getLogger("Pidroid")
root_logger.setLevel(logging.DEBUG)
root_logger_legacy.setLevel(logging.DEBUG)
# Add a StreamHandler to both loggers
ch = logging.StreamHandler()
ch.setFormatter(formatter)
root_logger.addHandler(ch)
root_logger_legacy.addHandler(ch)

def _load_env() -> None:
    arg_parser = ArgumentParser()
    _ = arg_parser.add_argument("-e", "--envfile", help="specifies .env file to load environment from")

    args, _ = arg_parser.parse_known_args()
    if args.envfile:
        root_logger.info("Loading environment from %s file", args.envfile)
        _ = load_dotenv(args.envfile)
    else:
        _ = load_dotenv()

def _update_system_path() -> None:
    sys.path.append(str(Path.cwd()))
    dir_path = Path(__file__).resolve().parent
    sys.path.append(str(dir_path))

_load_env()
_update_system_path()

from pidroid.utils.types import VersionInfo # noqa: E402,I001
version_field = metadata.version("pidroid-bot")
major, minor, micro = version_field.split(".")
__VERSION__ = VersionInfo(major=major, minor=minor, micro=micro, commit_id=os.environ.get("GIT_COMMIT", ""))
