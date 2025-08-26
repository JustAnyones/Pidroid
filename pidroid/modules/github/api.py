import base64
import datetime
import json
import jwt
import time

from dataclasses import dataclass
from discord import Attachment, Member, User
from typing import TYPE_CHECKING

from pidroid.utils.http import get, post
from pidroid.utils.time import utcnow

if TYPE_CHECKING:
    from pidroid.client import Pidroid

INSTALLATION_ID_URL = "https://api.github.com/orgs/{owner}/installation"
ACCESS_ID_URL = "https://api.github.com/app/installations/{installation_id}/access_tokens"
CREATE_ISSUE_URL = "https://api.github.com/repos/{owner}/{repo}/issues"

@dataclass
class _TokenContainer:
    """A dataclass that holds a GitHub access token and its expiration time."""
    token: str
    expires_at: datetime.datetime

    @property
    def is_valid(self) -> bool:
        return utcnow() < self.expires_at

def authenticated_request_headers(token: str) -> dict[str, str]:
    """A function that generates headers for authenticated requests to the GitHub API."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }

class GithubAPI:
    """A class that provides methods to interact with the GitHub API."""

    def __init__(
        self,
        pidroid: "Pidroid"
    ):
        client_id = pidroid.config.get("github_app_id")  
        pem = pidroid.config.get("github_app_pem")
        owner = pidroid.config.get("github_owner")
        repo = pidroid.config.get("github_repo")

        if any(v is None for v in (client_id, pem, owner, repo)):
            raise ValueError("GitHub integration is not properly configured.")

        assert pem

        self.__pidroid = pidroid
        self.__client_id = client_id
        self.__pem = pem
        self.__owner = owner
        self.__repo = repo
        self.__installation_id: int | None = None
        self.__token_data: _TokenContainer | None = None

    def generate_jwt(self) -> str:
        """A method that generates a JWT for use in the GitHub API authentication."""
        signing_key = base64.b64decode(self.__pem)
        payload = {
            'iat': int(time.time()),
            'exp': int(time.time()) + 600,
            'iss': self.__client_id
        }
        return jwt.encode(payload, signing_key, algorithm='RS256')

    async def get_access_token(self) -> str:
        """A method that obtains a valid access token for use in the GitHub API."""
        # If we already have a valid token, return it
        if self.__token_data is not None and self.__token_data.is_valid:
            return self.__token_data.token

        # Otherwise, generate a new token
        jwt_token = self.generate_jwt()
        # If we don't have an installation ID, fetch it
        if self.__installation_id is None:
            async with await get(
                self.__pidroid,
                INSTALLATION_ID_URL.format(owner=self.__owner),
                headers=authenticated_request_headers(jwt_token)
            ) as r:
                r.raise_for_status()
                self.__installation_id = (await r.json())["id"]

        # Send request to get access token
        async with await post(
            self.__pidroid,
            ACCESS_ID_URL.format(installation_id=self.__installation_id),
            headers=authenticated_request_headers(jwt_token),
            data={}
        ) as r:
            r.raise_for_status()
            data = await r.json()
            self.__token_data = _TokenContainer(
                data["token"],
                datetime.datetime.strptime(data["expires_at"], "%Y-%m-%dT%H:%M:%SZ")
            )
        return self.__token_data.token

    async def create_suggestion(
        self,
        *,
        title: str,
        text: str,
        author: Member | User,
        attachments: list[Attachment] | None = None,
        message_url: str | None = None
    ) -> dict[str, str]:
        """A method that creates a suggestion issue on GitHub."""
        body = "# Suggestion\n\n"
        body += text

        if attachments:
            body += "\n\n# Attachments"
            for attachment in attachments:
                body += f"\n\n![{attachment.filename}]({attachment.url})"

        # Add responsible user info
        body += "\n\n# Suggester"
        body += f"\nSuggested by {str(author)} (ID: {author.id})"
        if message_url is not None:
            body += f"\n[Jump to message on Discord]({message_url})"

        data = {
            "title": title,
            "body": body,
            "type": "feature",
        }
        return await self._create_issue(data)


    async def _create_issue(self, data: dict[str, str]) -> dict[str, str]:
        """A method that creates an issue on GitHub."""
        async with await post(
            self.__pidroid,
            CREATE_ISSUE_URL.format(owner=self.__owner, repo=self.__repo),
            headers=authenticated_request_headers(await self.get_access_token()),
            data=json.dumps(data),
        ) as r:
            r.raise_for_status()
            return await r.json()
