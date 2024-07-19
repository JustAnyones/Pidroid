import os
import sys
import logging

from argparse import ArgumentParser
from dotenv import load_dotenv

# Setup Pidroid level logging
logger = logging.getLogger("Pidroid")
#logger.setLevel(logging.WARNING)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s %(name)s:%(levelname)s]: %(message)s', "%Y-%m-%d %H:%M:%S")
ch.setFormatter(formatter)
logger.addHandler(ch)

def _load_env():
    arg_parser = ArgumentParser()
    _ = arg_parser.add_argument("-e", "--envfile", help="specifies .env file to load environment from")

    args, unknown = arg_parser.parse_known_args()
    if args.envfile:
        logger.info(f"Loading environment from {args.envfile} file")
        _ = load_dotenv(args.envfile)
    else:
        _ = load_dotenv()

def _update_system_path():
    sys.path.append(os.getcwd())
    dir_path = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(dir_path)

_load_env()
_update_system_path()
