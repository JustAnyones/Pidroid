import os
import sys
import logging

from argparse import ArgumentParser
from dotenv import load_dotenv
from importlib import metadata

# Set up logging
formatter = logging.Formatter('[%(asctime)s %(name)s:%(levelname)s]: %(message)s', "%Y-%m-%d %H:%M:%S")
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

def _load_env():
    arg_parser = ArgumentParser()
    _ = arg_parser.add_argument("-e", "--envfile", help="specifies .env file to load environment from")

    args, unknown = arg_parser.parse_known_args()
    if args.envfile:
        root_logger.info(f"Loading environment from {args.envfile} file")
        _ = load_dotenv(args.envfile)
    else:
        _ = load_dotenv()

def _update_system_path():
    sys.path.append(os.getcwd())
    dir_path = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(dir_path)

_load_env()
_update_system_path()

from pidroid.utils.types import VersionInfo
version_field = metadata.version('pidroid')
major, minor, micro = version_field.split('.')
__VERSION__ = VersionInfo(major=int(major), minor=int(minor), micro=int(micro), commit_id=os.environ.get('GIT_COMMIT', ''))
