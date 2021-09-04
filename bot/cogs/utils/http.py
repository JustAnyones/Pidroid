from __future__ import annotations

import aiofiles
import json
import re
import os

from aiohttp.client import ClientTimeout
from urllib.parse import urlparse, urlencode
from typing import Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from client import Pidroid

BASE_API_URL = "https://ja.theotown.com/api"

with open('./config.json') as data:
    AUTH_TOKEN = json.load(data)['authentication']['theotown api token']

DEFAULT_HEADERS = {'User-Agent': 'Pidroid bot by JustAnyone'}
DEFAULT_TIMEOUT = 30


class Route:
    """This class represents a TheoTown API route."""

    def __init__(self, path: str, query: dict = {}, headers: dict = None, private: bool = False) -> None:
        self.path = path
        self._query = query
        self._headers = headers

        self.private = private
        if self.path.startswith("/private/"):
            self.private = True

    def __repr__(self) -> str:
        return self.url

    def __str__(self) -> str:
        return self.url

    @property
    def query(self) -> Optional[str]:
        """Returns route query dictionary as string."""
        query = urlencode(self._query).strip()
        if query == "":
            return None
        return f"?{query}"

    @property
    def url(self) -> str:
        """Returns route request URL."""
        if self.query:
            return BASE_API_URL + self.path + self.query
        return BASE_API_URL + self.path

    @property
    def headers(self) -> dict:
        """Returns route request headers."""
        return get_headers(self._headers, self.private)

def get_headers(headers: Optional[dict], require_auth: bool = False) -> dict:
    """Returns merged headers including or excluding TheoTown API auth token."""
    new_headers = DEFAULT_HEADERS.copy()
    if headers:
        new_headers.update(headers)
    if require_auth:
        new_headers['Authorization'] = AUTH_TOKEN
    return new_headers

def get_filename(cd: str) -> str:
    """Returns filename from content disposition header."""
    return re.findall(r'filename\*?=[\'"]?(?:UTF-\d[\'"]*)?([^;\r\n"\']*)[\'"]?;?', cd)[0]

def get_unique_filename(path: str, filename: str) -> str:
    """Returns unique filename for specified filename and path."""
    name, extension = os.path.splitext(filename)
    i = 0
    while os.path.exists(path + filename):
        i += 1
        filename = name + '_' + str(i) + extension
    return filename


async def download_file(client: Pidroid, url: str, file_path, filename=None, headers=None, override=True, require_auth=False):
    """Downloads a file from url to specified path."""
    headers = get_headers(headers, require_auth)

    async with await get(client, url, headers) as r:
        status = r.status
        response_headers = r.headers
        payload = await r.read()

    if status != 200:
        return None

    if filename is None:
        if 'Content-Disposition' in response_headers:
            filename = get_filename(response_headers['Content-Disposition'])
        else:
            filename = os.path.basename(urlparse(url).path)

    if not override:
        filename = get_unique_filename(file_path, filename)
    file_path = file_path + filename
    f = await aiofiles.open(file_path, mode='wb')
    await f.write(payload)
    await f.close()
    return filename

async def get(client: Pidroid, url: str, headers: dict = None, cookies: dict = None, timeout: int = 30):
    """Sends a GET request to the specified URL."""
    return client.session.get(url, headers=headers, cookies=cookies, timeout=ClientTimeout(timeout))

async def post(client: Pidroid, url: str, data: Union[dict, str], headers: dict = None, cookies: dict = None, timeout: int = 30):
    """Sends a POST request to the specified URL."""
    return client.session.post(url, data=data, headers=headers, cookies=cookies, timeout=ClientTimeout(timeout))

async def patch(client: Pidroid, url: str, data: Union[dict, str], headers: dict = None, cookies: dict = None, timeout: int = 30):
    """Sends a PATCH request to the specified URL."""
    return client.session.patch(url, data=data, headers=headers, cookies=cookies, timeout=ClientTimeout(timeout))


def setup(client):
    pass

def teardown(client):
    pass
