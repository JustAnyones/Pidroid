from typing import NamedTuple, TypedDict

class ConfigDict(TypedDict):
    debugging: bool
    token: str
    prefixes: list[str]
    postgres_dsn: str
    tt_api_key: str | None
    deepl_api_key: str | None
    tenor_api_key: str | None
    unbelievaboat_api_key: str | None

class VersionInfo(NamedTuple):
    major: int
    minor: int
    micro: int
    commit_id: str