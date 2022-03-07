from __future__ import annotations
import httpx
import urllib.parse

from io import StringIO
from lxml import etree
from httpx._models import Response
from typing import Any, TYPE_CHECKING, Optional, List, Union
from enum import Enum

def reformat_value(value) -> Optional[Any]:
    """Fixes any API response values which are empty strings or an integer of 0 to None.
    Otherwise, returns the original value."""
    if value == 0 or value == "":
        return None
    return value


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


PARSER = etree.HTMLParser()

BASE_URL = "https://mywaifulist.moe"
API_URL = BASE_URL + "/api"


class MyWaifuListAPI:

    def __init__(self) -> None:
        """Initializes API instance."""
        self._xsrf_token = None
        self._csrf_token = None
        self._forever_alone_session = None
        self.client = httpx.Client(http2=True)

    def _acquire_tokens_for_forgery(self) -> None:
        """Sends a GET request to dash page to acquire tokens for forgery."""
        r = self.client.get(BASE_URL + "/dash") # Because fuck you, that's why
        tree = etree.parse(StringIO(r.text), PARSER)
        self._xsrf_token = r.cookies["XSRF-TOKEN"]
        self._forever_alone_session = r.cookies["forever_alone_session"]
        self._csrf_token = tree.xpath("//meta[@name='csrf-token']")[0].attrib['content']

    def reauthorize(self) -> None:
        self._acquire_tokens_for_forgery()

    @property
    def xsrf_token(self) -> str:
        """Returns XSRF token."""
        if self._xsrf_token is None:
            self._acquire_tokens_for_forgery()
        return self._xsrf_token

    @property
    def csrf_token(self) -> str:
        """Returns CSRF token."""
        if self._csrf_token is None:
            self._acquire_tokens_for_forgery()
        return self._csrf_token

    @property
    def forever_alone_session(self) -> str:
        """Returns some sort of token related to CSRF, no idea myself."""
        if self._forever_alone_session is None:
            self._acquire_tokens_for_forgery()
        return self._forever_alone_session

    @property
    def forged_cookies(self) -> dict:
        """Forged cookies for making API calls."""
        return {
            "XSRF-TOKEN": self.xsrf_token,
            "forever_alone_session": self.forever_alone_session
        }

    @property
    def forged_headers(self) -> dict:
        """Forged headers for making API calls."""
        return {
            "x-requested-with": "XMLHttpRequest",
            "Referer": "https://mywaifulist.moe/dash",
            "x-csrf-token": self.csrf_token,
            "x-xsrf-token": urllib.parse.unquote(self.xsrf_token)
        }

    def get_headers(self, json_as_string: bool = False) -> dict:
        """Returns a modified copy of forged headers.
        Mostly just an abstraction for dealing with crap POST request parameters."""
        headers = self.forged_headers.copy()
        if json_as_string:
            headers.setdefault("Content-Type", "application/json")
        return headers

    def get(self, endpoint: str) -> Response:
        """Sends a GET request to Mywaifulist API endpoint."""
        r = self.client.get(
            API_URL + endpoint,
            headers=self.forged_headers, cookies=self.forged_cookies
        )
        return r

    def post(self, endpoint: str, json: dict) -> Response:
        """Sends a POST request to Mywaifulist API endpoint."""
        r = self.client.post(
            API_URL + endpoint, json=json,
            headers=self.forged_headers, cookies=self.forged_cookies
        )
        return r

    def fetch_random_waifu(self) -> Waifu:
        """Returns a random waifu."""
        r = self.client.get(f"{BASE_URL}/random", headers=self.forged_headers, follow_redirects=True)
        tree = etree.parse(StringIO(r.text), PARSER)
        waifu_id = tree.xpath("//waifu-core")[0].attrib[':waifu-id']
        return self.fetch_waifu_by_id(waifu_id)

    def fetch_waifu_by_id(self, id: int) -> Waifu:
        """Returns a waifu by the specified ID."""
        r = self.get(f"/waifu/{id}")
        return Waifu(r.json()["data"])

    def search(self, query: str) -> List[Union[WaifuSearchResult, SeriesSearchResult, SearchResult]]:
        """Returns a list of results matching your query."""
        r = self.post("/waifu/search", {"query": query})
        results = []
        for i in r.json():
            if i["entity_type"] == "waifu":
                results.append(WaifuSearchResult(self, i))
            elif i["entity_type"] == "series":
                results.append(SeriesSearchResult(i))
            else:
                results.append(SearchResult(i))
        return results

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
    UNKNOWN = None

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

    def fetch_waifu(self) -> Waifu:
        """Returns a full Waifu object by fetching the API."""
        return self._api.fetch_waifu_by_id(self.id)
