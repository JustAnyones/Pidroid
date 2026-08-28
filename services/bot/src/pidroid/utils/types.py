from discord import ClientUser, Member, User
from typing import NamedTuple, TypedDict

DiscordUser = ClientUser | Member | User

class ConfigDict(TypedDict):
    debugging: bool
    token: str
    prefixes: list[str]
    postgres_dsn: str
    tt_api_key: str | None
    deepl_api_key: str | None
    tenor_api_key: str | None
    unbelievaboat_api_key: str | None
    github_app_id: str | None
    github_app_pem: str | None
    github_owner: str | None
    github_repo: str | None
    rabbitmq_url: str | None

class VersionInfo(NamedTuple):
    major: str
    minor: str
    micro: str
    commit_id: str