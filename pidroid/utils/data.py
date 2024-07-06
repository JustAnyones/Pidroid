import aiodbm
import os

from pidroid.constants import DATA_FILE_PATH

PERSISTENT_DATA_FILE = os.path.join(DATA_FILE_PATH, "data.dbm")

def PersistentDataStore():
    return aiodbm.open(PERSISTENT_DATA_FILE, "c")
