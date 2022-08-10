from __future__ import annotations

import httpx
import urllib.parse

from io import StringIO
from lxml import etree # type: ignore # nosec
from httpx._models import Response
from typing import Any, TYPE_CHECKING, Dict, Optional, List, Union
from enum import Enum

from pidroid.cogs.models.exceptions import APIException

def reformat_value(value) -> Optional[Any]:
    """Fixes any API response values which are empty strings or an integer of 0 to None.
    Otherwise, returns the original value."""
    if value == 0 or value == "":
        return None
    return value


PARSER = etree.HTMLParser()
BASE_URL = "https://mywaifulist.moe"
API_URL = BASE_URL + "/api"

class EntityType(Enum):
    WAIFU = "waifu"
    SERIES = "series"

class ResultType(Enum):
    WAIFU = "Waifu"
    TV = "TV"
    GAME = "Game"
    MANGA = "Manga"
    NOVEL = "Novel"
    HUSTBANDO = "Husbando"
    OVA = "OVA"
    HENTAI = "Hentai"
    MOVIE = "Movie"
    ONA = "ONA"
    SPECIAL = "Special"
    UNKNOWN = None

class Birthday:
    """This class represents birthday of a waifu."""

    if TYPE_CHECKING:
        year: Optional[str]
        month: Optional[str]
        day: Optional[int]

    def __init__(self, year, month, day) -> None:
        self.year = reformat_value(year)
        self.month = reformat_value(month)
        self.day = reformat_value(day)

class SearchResult:

    if TYPE_CHECKING:
        id: int
        slug: str
        type: ResultType
        url: str

        name: str
        original_name: Optional[str]
        romaji_name: Optional[str]
        description: Optional[str]
        display_picture: str

        relevance: int
        base: str
        entity_type: EntityType

    def __init__(self, data: dict) -> None:
        self.id = data["id"]
        self.slug = data["slug"]
        self.type = ResultType(data["type"])
        self.url = data["url"]

        self.name = data["name"]
        self.original_name = reformat_value(data["original_name"])
        self.romaji_name = reformat_value(data["romaji_name"])
        self.description = reformat_value(data["description"])
        self.display_picture = data["display_picture"]

        self.relevance = data["relevance"]
        self.base = data["base"]
        self.entity_type = EntityType(data["entity_type"])

class SeriesSearchResult(SearchResult):

    def __init__(self, data: dict) -> None:
        super().__init__(data)

class WaifuSearchResult(SearchResult):

    if TYPE_CHECKING:
        romaji: Optional[str]
        likes: int
        trash: int
        series: Optional[list]
        appearances: Optional[list]

    def __init__(self, api: MyWaifuListAPI, data: dict) -> None:
        super().__init__(data)
        self._api = api
        self.romaji = data["romaji"]
        self.likes = data["likes"]
        self.trash = data["trash"]
        self.series = data["series"] # TODO: add specific class
        self.appearances = data["appearances"] # TODO: add specific class

    async def fetch_waifu(self) -> Waifu:
        """Returns a full Waifu object by fetching the API."""
        return await self._api.fetch_waifu_by_id(self.id)


class Waifu:
    """This class represents Mywaifulist Waifu."""

    if TYPE_CHECKING:
        id: int
        slug: str
        url: str

        name: str
        original_name: Optional[str]
        romaji_name: Optional[str]
        description: Optional[str]
        display_picture: str

        is_husbando: bool
        is_nsfw: bool

        age: Optional[int]
        birthday: Birthday
        appearance: dict

        series: Optional[list]
        appearances: Optional[list]
        tags: list

    def __init__(self, dictionary: dict) -> None:
        self.id = dictionary["id"]
        self.slug = dictionary["slug"]
        self.url = dictionary["url"]

        self.name = dictionary["name"]
        self.original_name = reformat_value(dictionary["original_name"])
        self.romaji_name = reformat_value(dictionary["romaji_name"])
        self.description = reformat_value(dictionary["description"])
        self.display_picture = dictionary["display_picture"]

        self.is_husbando = dictionary["husbando"]
        self.is_nsfw = dictionary["nsfw"]

        self.age = reformat_value(dictionary["age"])
        self.birthday = Birthday(
            dictionary["birthday_year"],
            dictionary["birthday_month"],
            dictionary["birthday_day"]
        )

        # TODO: add specific class
        self.appearance = {
            "weight": dictionary["weight"],
            "height": dictionary["height"],
            "bust": dictionary["bust"],
            "hip": dictionary["hip"],
            "waist": dictionary["waist"],
            "blood_type": dictionary["blood_type"],
            "origin": dictionary["origin"],
        }

        self.series = dictionary["series"] # TODO: add specific class
        self.appearances = dictionary["appearances"] # TODO: add specific class
        self.tags = dictionary["tags"] # TODO: add specific class

    def __repr__(self) -> str:
        return f'<Waifu id={self.id} name="{self.name}">'


class MyWaifuListAPI:

    def __init__(self) -> None:
        """Initializes API instance."""
        self._xsrf_token: Optional[str] = None
        self._csrf_token: Optional[str] = None
        self._forever_alone_session: Optional[str] = None
        self.client = httpx.AsyncClient(http2=True)
        self.search_cache: Dict[str, List[Union[WaifuSearchResult, SeriesSearchResult, SearchResult]]] = {}
        self.waifu_cache: Dict[int, Waifu] = {}

    async def _acquire_tokens_for_forgery(self) -> None:
        """Sends a GET request to dash page to acquire tokens for forgery."""
        r = await self.client.get(BASE_URL + "/dash")
        tree = etree.parse(StringIO(r.text), PARSER) # nosec
        self._xsrf_token = r.cookies["XSRF-TOKEN"]
        self._forever_alone_session = r.cookies["forever_alone_session"]
        self._csrf_token = tree.xpath("//meta[@name='csrf-token']")[0].attrib['content']

    async def reauthorize(self) -> None:
        """Sends a GET request to dash page to acquire tokens for forgery."""
        await self._acquire_tokens_for_forgery()

    @property
    async def xsrf_token(self) -> str:
        """Returns XSRF token."""
        if self._xsrf_token is None:
            await self._acquire_tokens_for_forgery()
        assert self._xsrf_token is not None
        return self._xsrf_token

    @property
    async def csrf_token(self) -> str:
        """Returns CSRF token."""
        if self._csrf_token is None:
            await self._acquire_tokens_for_forgery()
        assert self._csrf_token is not None
        return self._csrf_token

    @property
    async def forever_alone_session(self) -> str:
        """Returns some sort of token related to CSRF, no idea myself."""
        if self._forever_alone_session is None:
            await self._acquire_tokens_for_forgery()
        assert self._forever_alone_session is not None
        return self._forever_alone_session

    @property
    async def forged_cookies(self) -> dict:
        """Forged cookies for making API calls."""
        return {
            "XSRF-TOKEN": await self.xsrf_token,
            "forever_alone_session": await self.forever_alone_session
        }

    @property
    async def forged_headers(self) -> dict:
        """Forged headers for making API calls."""
        return {
            "x-requested-with": "XMLHttpRequest",
            "Referer": "https://mywaifulist.moe/dash",
            "x-csrf-token": await self.csrf_token,
            "x-xsrf-token": urllib.parse.unquote(await self.xsrf_token)
        }

    async def get(self, endpoint: str) -> Response:
        """Sends a GET request to Mywaifulist API endpoint."""
        r = await self.client.get(
            API_URL + endpoint,
            headers=await self.forged_headers, cookies=await self.forged_cookies
        )
        return r

    async def post(self, endpoint: str, json: dict, attempts: int = 0) -> Response:
        """Sends a POST request to Mywaifulist API endpoint."""
        r = await self.client.post(
            API_URL + endpoint, json=json,
            headers=await self.forged_headers, cookies=await self.forged_cookies
        )
        if r.status_code == 419:
            if attempts > 2:
                raise APIException(401, 'Re-authorization attempts have failed. Try again later.')
            await self.reauthorize()
            return await self.post(endpoint, json, attempts + 1)
        return r

    async def fetch_random_waifu(self) -> Waifu:
        """Returns a random waifu."""
        r = await self.client.get(f"{BASE_URL}/random", headers=await self.forged_headers, follow_redirects=True)
        tree = etree.parse(StringIO(r.text), PARSER) # nosec
        waifu_id = tree.xpath("//waifu-core")[0].attrib[':waifu-id']
        waifu = await self.fetch_waifu_by_id(waifu_id)
        return waifu

    async def fetch_waifu_by_id(self, id: int) -> Waifu:
        """Returns a waifu by the specified ID."""
        waifu = self.waifu_cache.get(id)
        if waifu:
            return waifu

        r = await self.get(f"/waifu/{id}")
        waifu = Waifu(r.json()["data"])
        self.waifu_cache[id] = waifu
        return waifu

    async def search(self, query: str) -> List[Union[WaifuSearchResult, SeriesSearchResult, SearchResult]]:
        """Returns a list of results matching your query."""
        query = query.lower()
        cached_res = self.search_cache.get(query)
        if cached_res:
            return cached_res
        r = await self.post("/waifu/search", {"query": query})
        results: List[Union[WaifuSearchResult, SeriesSearchResult, SearchResult]] = []
        for i in r.json():
            if i["entity_type"] == "waifu":
                results.append(WaifuSearchResult(self, i))
            elif i["entity_type"] == "series":
                results.append(SeriesSearchResult(i))
            else:
                results.append(SearchResult(i))
        self.search_cache[query] = results
        return results
