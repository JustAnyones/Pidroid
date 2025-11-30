import asyncio
import aiodbm
import os

from contextlib import asynccontextmanager

from pidroid.constants import DATA_FILE_PATH

PERSISTENT_DATA_FILE = os.path.join(DATA_FILE_PATH, "data.dbm")

_DATA_STORE_LOCK = asyncio.Lock()

@asynccontextmanager
async def PersistentDataStore():
    """
    Asynchronously opens the persistent data store, protected by a lock.
    """
    await _DATA_STORE_LOCK.acquire()
    
    store = None
    try:
        store = await aiodbm.open(PERSISTENT_DATA_FILE, "c") # pyright: ignore[reportUnknownMemberType]
        yield store
    finally:
        if store is not None:
            await store.close()
        _DATA_STORE_LOCK.release()
