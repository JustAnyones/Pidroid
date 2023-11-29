from __future__ import annotations

import re

from aiohttp.client import ClientTimeout
from urllib.parse import urlencode
from typing import Optional, Union, TYPE_CHECKING

from pidroid.models.exceptions import APIException

if TYPE_CHECKING:
    from pidroid.client import Pidroid

DEFAULT_HEADERS = {'User-Agent': 'Pidroid bot by JustAnyone'}

class HTTP:
    """This class implements a basic TheoTown API HTTP request handling system."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client

    async def request(self, method: str, route: Route, headers: Optional[dict] = None, data: Optional[dict] = None):
        # Deal with headers
        new_headers = DEFAULT_HEADERS.copy()
        if headers:
            new_headers.update(headers)
        if route.private:
            new_headers['Authorization'] = self.client.config['tt_api_key']

        # Do actual request
        assert self.client.session is not None
        async with self.client.session.request(
            method, route.url,
            headers=new_headers, data=data
        ) as r:
            # Handle errors
            if r.status == 501:
                raise APIException(r.status, "Requested API resource is not yet implemented!")

            if r.status >= 500:
                raise APIException(r.status, "Requested API resource has an internal backend error. Please try again later!")

            if r.status == 400:
                res = await r.json()
                raise APIException(r.status, f"Bad request sent to the API resource: {res['details']}")

            if r.status == 401:
                raise APIException(r.status, "Client is not authorized to make calls to the specified API endpoint!")

            if r.status == 404:
                raise APIException(r.status, "Requested API resource not found!")

            if r.status == 200:
                return await r.json()

            raise APIException(r.status)

class Route:
    """This class represents a TheoTown API route."""

    BASE_URL = "https://ja.theotown.com/api/v2"

    def __init__(self, path: str, query: dict = {}) -> None:
        self.path = path
        self._query = query
        self.private = self.path.startswith("/private/")

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
            return self.BASE_URL + self.path + self.query
        return self.BASE_URL + self.path

def get_filename(cd: str) -> str:
    """Returns filename from content disposition header."""
    return re.findall(r'filename\*?=[\'"]?(?:UTF-\d[\'"]*)?([^;\r\n"\']*)[\'"]?;?', cd)[0]

async def get(client: Pidroid, url: str, headers: Optional[dict] = None, cookies: Optional[dict] = None, timeout: int = 30):
    """Sends a GET request to the specified URL."""
    assert client.session is not None
    return client.session.get(url, headers=headers, cookies=cookies, timeout=ClientTimeout(timeout))

async def post(client: Pidroid, url: str, data: Union[dict, str], headers: Optional[dict] = None, cookies: Optional[dict] = None, timeout: int = 30):
    """Sends a POST request to the specified URL."""
    assert client.session is not None
    return client.session.post(url, data=data, headers=headers, cookies=cookies, timeout=ClientTimeout(timeout))

async def patch(client: Pidroid, url: str, data: Union[dict, str], headers: Optional[dict] = None, cookies: Optional[dict] = None, timeout: int = 30):
    """Sends a PATCH request to the specified URL."""
    assert client.session is not None
    return client.session.patch(url, data=data, headers=headers, cookies=cookies, timeout=ClientTimeout(timeout))
