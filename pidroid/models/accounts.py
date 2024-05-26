import datetime

from typing import TYPE_CHECKING, Any, override

from pidroid.constants import THEOTOWN_FORUM_URL
from pidroid.utils.time import timestamp_to_datetime

class ForumAccount:

    if TYPE_CHECKING:
        id: int
        name: str
        group_name: str
        rank: str
        post_count: int
        reaction_count: int
        date_registered: datetime.datetime
        date_latest_login: datetime.datetime | None
        _avatar: str

    def __init__(self, data: dict[str, Any]) -> None:
        super().__init__()
        self.id = data["user_id"]
        self.name = data["username"]

        self.group_name = data["group_name"]
        if self.group_name.isupper():
            self.group_name = self.group_name.replace("_", " ").capitalize()

        self.rank = data["rank_title"]
        self.post_count = data["user_posts"]
        self.reaction_count = data["user_reactions"]

        self.date_registered = timestamp_to_datetime(data["user_regdate"])
        if data["user_lastvisit"] == 0:
            self.date_latest_login = None
        else:
           self.date_latest_login = timestamp_to_datetime(data["user_lastvisit"])

        self._avatar = data["user_avatar"]

    @override
    def __repr__(self) -> str:
        return f'<ForumAccount id={self.id} name="{self.name}">'

    @property
    def avatar_url(self) -> str:
        """Returns URL to the account avatar."""
        return f'{THEOTOWN_FORUM_URL}/download/file.php?avatar={self._avatar}'

    @property
    def profile_url(self) -> str:
        """Returns URL to the account profile."""
        return f'{THEOTOWN_FORUM_URL}/memberlist.php?mode=viewprofile&u={self.id}'

    @property
    def forum_plugin_url(self) -> str:
        """Returns URL to the account forum plugins."""
        return f'{THEOTOWN_FORUM_URL}/search.php?author_id={self.id}&fid%5B%5D=43&sc=1&sr=topics&sk=t&sf=firstpost'

    @property
    def plugin_store_url(self) -> str:
        """Returns URL to the account plugin store plugins."""
        return f'{THEOTOWN_FORUM_URL}/plugins/list?mode=user&user_id={self.id}'

class TheoTownAccount:

    def __init__(self, data: dict[str, Any]) -> None:
        super().__init__()
        self.id: int = data["id"]
        self.name: str = data["name"]
        self.forum_account = ForumAccount(data["forum_account"])
