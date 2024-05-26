from __future__ import annotations

from discord.ext.commands import CheckFailure, BadArgument

class NotInTheoTownGuild(CheckFailure):
    def __init__(self):
        super().__init__("The command can only be used inside the TheoTown server!")

class InvalidDuration(BadArgument):
    def __init__(self, message: str):
        super().__init__(message)

class MissingUserPermissions(CheckFailure):
    def __init__(self, message: str | None = None):
        super().__init__(message or "You are missing the required permissions to proceed!")

class ClientIsNotPidroid(CheckFailure):
    def __init__(self):
        super().__init__("Client user is not Pidroid!")

class GenericPidroidError(CheckFailure):
    def __init__(self):
        super().__init__("Generic Pidroid error raised!")

class GeneralCommandError(BadArgument):
    def __init__(self, message: str):
        super().__init__(message)

class APIException(BadArgument):
    """Called when TheoTown API error is encountered"""
    def __init__(self, status: int, message: str | None = None):
        if message is None:
            return super().__init__(f"An error has been encountered inside TheoTown API, status code: {status}")
        return super().__init__(message)
