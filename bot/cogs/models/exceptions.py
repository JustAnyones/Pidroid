from __future__ import annotations

from discord.ext.commands import CheckFailure, BadArgument
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from client import Pidroid


class NotInTheoTownGuild(CheckFailure):
    def __init__(self, message: str = None):
        super().__init__(message or "The command can only be used inside the TheoTown server!")

class InvalidChannel(CheckFailure):
    def __init__(self, message: str):
        super().__init__(message)

class InvalidDuration(BadArgument):
    def __init__(self, message: str):
        super().__init__(message)

class MissingUserPermissions(CheckFailure):
    def __init__(self, message: str = None):
        super().__init__(message or "You are missing the required permissions to proceed!")

class ClientIsNotPidroid(CheckFailure):
    def __init__(self, message: str = None):
        super().__init__(message or "Client user is not Pidroid!")

class APIException(BadArgument):
    """Called when TheoTown API error is encountered"""
    def __init__(self, status: int, message: str = None):
        if message is None:
            return super().__init__(f"An error has been encountered inside TheoTown API, status code: {status}")
        return super().__init__(message)


def setup(client: Pidroid) -> None:
    pass

def teardown(client: Pidroid) -> None:
    pass
