import json
import os

from typing import Dict, Optional

from constants import DATA_FILE_PATH

PERSISTENT_DATA_FILE = os.path.join(DATA_FILE_PATH, 'data.json')

class PersistentDataManager:
    """This class manages Pidroid's persistent data."""

    def __init__(self) -> None:
        self._data: Optional[Dict] = None

    @property
    def data(self) -> dict:
        """Returns a mutable dictionary of persistent data."""
        if self._data is None:
            self.load()
        return self._data or {}

    def load(self) -> None:
        """Loads persistent data from a file. Returns a plain dictionary if data file doesn't exist."""
        if not os.path.exists(PERSISTENT_DATA_FILE):
            self._data = {}
        else:
            with open(PERSISTENT_DATA_FILE, encoding="utf-8") as f:
                self._data = json.load(f)

    def save(self) -> None:
        """Saves persistent data to a file."""
        with open(f"{PERSISTENT_DATA_FILE}.tmp", "w", encoding="utf-8") as f:
            json.dump(self._data, f)
        os.rename(f"{PERSISTENT_DATA_FILE}.tmp", PERSISTENT_DATA_FILE)
