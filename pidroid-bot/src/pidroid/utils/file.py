import os

from pidroid.constants import RESOURCE_FILE_PATH

class Resource(str): # All this for type hints

    def __new__(cls, *paths: str):
        return str.__new__(cls, get_resource(*paths))

def get_resource(*paths: str) -> str:
    """Returns absolute path to a Pidroid resource file."""
    return os.path.join(RESOURCE_FILE_PATH, *paths)
