import requests
import urllib.parse

from io import StringIO
from lxml import etree
from requests.models import Response

from cogs.models.waifu import Waifu


PARSER = etree.HTMLParser()

BASE_URL = "https://mywaifulist.moe"
API_URL = BASE_URL + "/api"


class MyWaifuListAPI:

    def __init__(self) -> None:
        """Initializes API instance."""
        self._xsrf_token = None
        self._csrf_token = None
        self._forever_alone_session = None

    def _acquire_tokens_for_forgery(self) -> None:
        """Sends a GET request to dash page to acquire tokens for forgery."""
        r = requests.get(BASE_URL + "/dash", headers={"x-requested-with": "XMLHttpRequest"}) # Because fuck you, that's why
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
        r = requests.get(
            API_URL + endpoint,
            headers=self.forged_headers, cookies=self.forged_cookies
        )
        return r

    def post(self, endpoint: str, data: dict, json_as_string: bool = False) -> Response:
        """Sends a POST request to Mywaifulist API endpoint."""
        r = requests.post(
            API_URL + endpoint, data,
            headers=self.get_headers(json_as_string), cookies=self.forged_cookies
        )
        return r

    def fetch_random_waifu(self) -> Waifu:
        """Returns a random waifu."""
        r = requests.get(f"{BASE_URL}/random", headers=self.forged_headers)
        tree = etree.parse(StringIO(r.text), PARSER)
        waifu_id = tree.xpath("//waifu-core")[0].attrib[':waifu-id']
        return self.get_waifu_by_id(waifu_id)

    def fetch_waifu(self, id: int) -> Waifu:
        """Returns a waifu by the specified ID."""
        r = self.get(f"/waifu/{id}")
        return Waifu(r.json()["data"])
