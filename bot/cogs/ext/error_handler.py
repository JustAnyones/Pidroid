import discord
import sys
import traceback
import random

from contextlib import suppress
from discord.errors import HTTPException, InvalidArgument
from discord.ext import commands
from discord.ext.commands.context import Context
from jishaku.paginators import PaginatorInterface, WrappedPaginator
from typing import TYPE_CHECKING

from constants import REFUSE_COMMAND_RESPONSES
from cogs.models import exceptions
from cogs.utils.embeds import error as error_embed
from cogs.utils.time import humanize

# Errors which command error handler will ignore
ignored_exceptions = (
    commands.CommandNotFound,
    commands.DisabledCommand,
    exceptions.ClientIsNotPidroid
)

# Errors which command error handler won't modify the behaviour of
use_default = (
    # Permission exceptions
    commands.BotMissingPermissions,
    commands.MissingPermissions,
    exceptions.MissingUserPermissions,
    exceptions.NotInTheoTownGuild,

    # Cooldown and concurrency exceptions
    commands.MaxConcurrencyReached,

    # Argument exceptions
    commands.BadArgument,
    commands.BadUnionArgument,
    commands.TooManyArguments,
    commands.MissingRequiredArgument,
    exceptions.InvalidDuration,
    InvalidArgument,

    # API errors
    exceptions.APIException,

    # Quoted argument parser errors
    commands.UnexpectedQuoteError,
    commands.InvalidEndOfQuotedStringError,
    commands.ExpectedClosingQuoteError
)


if TYPE_CHECKING:
    from client import Pidroid

class Error(commands.Cog):
    """This class implements a cog for handling of unhandled bot command errors and exceptions."""

    def __init__(self, client: Pidroid):
        self.client = client

    async def notify(self, ctx: Context, message: str, delete_after: int = None):
        with suppress(discord.errors.Forbidden):
            await ctx.reply(embed=error_embed(message), delete_after=delete_after)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: Context, error):  # noqa: C901

        # Prevents commands with local error handling being handled here
        if hasattr(ctx.command, 'on_error'):
            return

        # Allows us to check for original exceptions raised and sent to CommandInvokeError.
        # If nothing is found. We keep the exception passed to on_command_error.
        error = getattr(error, 'original', error)

        # Resets command cooldown on command error
        if ctx.command is not None and not isinstance(error, commands.CommandOnCooldown):
            ctx.command.reset_cooldown(ctx)

        # Ignore errors
        if isinstance(error, ignored_exceptions):
            return

        # Do not modify specified errors
        if isinstance(error, use_default):
            return await self.notify(ctx, error)

        # Extensive logging for NotFound and Forbidden errors
        if isinstance(error, discord.errors.NotFound):
            print('Unhandled NotFound exception encountered!')
            print(error.args)
            print(error.code)
            print(error.response)
            print(error.status)
            print(error.text)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

        elif isinstance(error, discord.errors.Forbidden):
            print(f'A 403 error has been encountered in {ctx.command} command, printing stack trace')
            print(error.args)
            print(error.code)
            print(error.response)
            print(error.status)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

        # Handle specific errors
        elif isinstance(error, commands.NotOwner):
            await self.notify(ctx, "The command can only be used by the bot owner")

        elif isinstance(error, commands.PrivateMessageOnly):
            await self.notify(ctx, "The command can only be used in Private Messages")

        elif isinstance(error, commands.NoPrivateMessage):
            await self.notify(ctx, "The command can not be used in Private Messages")

        elif isinstance(error, commands.CommandOnCooldown):
            if error.cooldown.per < 10:
                await self.notify(ctx, "Woah, slow down!", delete_after=3)
                return
            await self.notify(ctx, f"You're on cooldown, try again in {humanize(error.retry_after, False, max_units=2)}.", delete_after=3)

        elif isinstance(error, exceptions.InvalidChannel):
            await self.notify(ctx, random.choice(REFUSE_COMMAND_RESPONSES)) # nosec

        elif isinstance(error, commands.NSFWChannelRequired):
            await self.notify(ctx, "The command can only be used inside NSFW channel")

        # All other errors get returned here with traceback
        else:
            if await self.client.is_owner(ctx.message.author):

                # Create a wrapped paginator which will keep our exception message
                paginator = WrappedPaginator(
                    prefix=f'Exception handler not found for {type(error).__name__}\n```py',
                    suffix='```',
                    max_size=1985
                )

                # Put traceback into a string and clean it
                trace = "".join(
                    traceback.format_exception(etype=type(error), value=error, tb=error.__traceback__)
                ).replace('```', '``\N{zero width space}`')

                paginator.add_line(trace)

                # Create paginator interface, I.E, the interactive buttons thing
                interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
                await interface.send_to(ctx)
                return
            with suppress(HTTPException):
                await ctx.reply(embed=error_embed(
                    f'Something broke while executing the ``{ctx.command.name}`` command that could not be handled by the main error handler. '
                    'If you\'ve encountered this multiple times, please notify my owner.'
                ))
            print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


def setup(client: Pidroid):
    client.add_cog(Error(client))
