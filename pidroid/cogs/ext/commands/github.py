import json

from discord.ext import commands # type: ignore
from discord.ext.commands.context import Context # type: ignore
from typing import List

from client import Pidroid
from cogs.utils.decorators import command_checks
from cogs.utils.http import post

ISSUE_URL = "https://api.github.com/repos/TheoTown-Team/oauth-experiment/issues"
GH_HEADERS = {"Accept": "application/vnd.github.v3+json"}

def _serialize(data: dict) -> str:
    return json.dumps(data)

def create_issue_body(title: str, body: str, labels: List[str] = None) -> dict:
    return {
        "title": title,
        "body": body + "\n\n> Created automatically using Pidroid",
        "labels": labels
    }


class GitHubCommands(commands.Cog): # type: ignore
    """This class implements a cog which contains commands for communication via GitHub.

    This cog is dedicated for easier integration to TheoTown GitHub."""

    def __init__(self, client: Pidroid):
        self.client = client

    @property
    def _headers(self) -> dict:
        headers = GH_HEADERS.copy()
        headers["Authorization"] = f"token {self.client.config['github_token']}"
        return headers

    @commands.command( # type: ignore
        name='create-issue',
        brief='Creates an issue on GitHub with a bug label.',
        usage='<title> <body>',
        hidden=True,
        enabled=False
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.is_theotown_developer()
    async def create_issue(self, ctx: Context, title: str, *, body: str):
        req = create_issue_body(title, body, ["bug"])

        async with await post(self.client, ISSUE_URL, data=_serialize(req), headers=self._headers) as response:
            data = await response.json()

        await ctx.send(f"New issue created at {data['html_url']}")


async def setup(client: Pidroid) -> None:
    await client.add_cog(GitHubCommands(client))
