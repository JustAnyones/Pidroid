from __future__ import annotations

import re

from aiohttp import ContentTypeError
from aiohttp.client import ClientTimeout
from urllib.parse import urlencode
from typing import Any, TYPE_CHECKING, override

from pidroid.models.exceptions import APIException

if TYPE_CHECKING:
    from pidroid.client import Pidroid

DEFAULT_HEADERS = {'User-Agent': 'Pidroid bot by JustAnyone'}

DataDict = dict[str, bytes | int | str | None]
HeaderDict = dict[str, str]

class HTTP:
    """This class implements a basic TheoTown API HTTP request handling system."""

    def __init__(self, client: Pidroid) -> None:
        super().__init__()
        self.client = client

    async def request(self, method: str, route: Route, headers: HeaderDict | None = None, data: DataDict | None = None) -> dict[Any, Any]:
        # Deal with headers
        new_headers = DEFAULT_HEADERS.copy()
        if headers:
            new_headers.update(headers)
        new_headers['Authorization'] = self.client.config['tt_api_key']

        # Do actual request
        assert self.client.session is not None
        async with self.client.session.request(
            method, route.url,
            headers=new_headers, data=data
        ) as r:
            if r.status == 200:
                return await r.json()

            try:
                data = await r.json()
                if data:
                    raise APIException(r.status, data["details"])
            except ContentTypeError:
                pass
                    
            raise APIException(r.status)

class Route:
    """This class represents a TheoTown API route."""

    BASE_URL = "https://ja.theotown.com/api/v3"

    def __init__(self, path: str, query: DataDict | None = None) -> None:
        super().__init__()
        self.path = path
        self._query = query or {}

    @override
    def __repr__(self) -> str:
        return self.url

    @override
    def __str__(self) -> str:
        return self.url

    @property
    def query(self) -> str | None:
        """Returns route query dictionary as string."""
        query = urlencode(self._query).strip()
        if query == "":
            return None
        return f"?{query}"

    @property
    def url(self) -> str:
        """Returns route request URL."""
        if self.query:
            return self.BASE_URL + self.path + self.query
        return self.BASE_URL + self.path

def get_filename(cd: str) -> str:
    """Returns filename from content disposition header."""
    return re.findall(r'filename\*?=[\'"]?(?:UTF-\d[\'"]*)?([^;\r\n"\']*)[\'"]?;?', cd)[0]

async def get(client: Pidroid, url: str, headers: HeaderDict | None = None, timeout: int = 30):
    """Sends a GET request to the specified URL."""
    assert client.session is not None
    return client.session.get(url, headers=headers, timeout=ClientTimeout(timeout))

async def post(client: Pidroid, url: str, data: DataDict | str, headers: HeaderDict | None = None, timeout: int = 30):
    """Sends a POST request to the specified URL."""
    assert client.session is not None
    return client.session.post(url, data=data, headers=headers, timeout=ClientTimeout(timeout))

async def patch(client: Pidroid, url: str, data: DataDict | str, headers: HeaderDict | None = None, timeout: int = 30):
    """Sends a PATCH request to the specified URL."""
    assert client.session is not None
    return client.session.patch(url, data=data, headers=headers, timeout=ClientTimeout(timeout))
