from __future__ import annotations

import discord
import sys
import traceback

from contextlib import suppress
from discord.errors import HTTPException
from discord.ext import commands # type: ignore
from discord.ext.commands.context import Context # type: ignore
from jishaku.paginators import PaginatorInterface, WrappedPaginator # type: ignore
from typing import TYPE_CHECKING, Optional

from pidroid.models import exceptions
from pidroid.utils.embeds import ErrorEmbed as ErrorEmbed
from pidroid.utils.time import humanize

# Errors which command error handler will ignore
ignored_exceptions = (
    commands.CommandNotFound, # type: ignore
    commands.DisabledCommand, # type: ignore
    exceptions.ClientIsNotPidroid
)

# Errors which command error handler won't modify the behaviour of
use_default = (
    # Permission exceptions
    commands.BotMissingPermissions, # type: ignore
    commands.MissingPermissions, # type: ignore
    exceptions.MissingUserPermissions,
    exceptions.NotInTheoTownGuild,

    # Cooldown and concurrency exceptions
    commands.MaxConcurrencyReached, # type: ignore

    # Argument exceptions
    commands.BadArgument, # type: ignore
    commands.BadUnionArgument, # type: ignore
    commands.TooManyArguments, # type: ignore
    #commands.MissingRequiredArgument, # type: ignore
    exceptions.InvalidDuration,

    # API errors
    exceptions.APIException,

    # Quoted argument parser errors
    commands.UnexpectedQuoteError, # type: ignore
    commands.InvalidEndOfQuotedStringError, # type: ignore
    commands.ExpectedClosingQuoteError # type: ignore
)

async def notify(ctx: Context, message: str, delete_after: Optional[int] = None):
    with suppress(discord.errors.Forbidden):
        await ctx.reply(embed=ErrorEmbed(message), delete_after=delete_after) # type: ignore

if TYPE_CHECKING:
    from pidroid.client import Pidroid

class Error(commands.Cog): # type: ignore
    """This class implements a cog for handling of unhandled bot command errors and exceptions."""

    def __init__(self, client: Pidroid):
        self.client = client

    @commands.Cog.listener() # type: ignore
    async def on_command_error(self, ctx: Context, error):  # noqa: C901
        # Prevents commands with local error handling being handled here twice
        if hasattr(ctx.command, 'on_error'):
            unhandled = getattr(error, 'unhandled')
            # If value is not set or is set to False, we consider that
            # the local error handler handled it
            if not unhandled:
                return

        # Allows us to check for original exceptions raised and sent to CommandInvokeError.
        # If nothing is found. We keep the exception passed to on_command_error.
        error = getattr(error, 'original', error)

        # If error does not exist?
        if error is None:
            return

        # Resets command cooldown on command error if it's not a cooldown error
        if ctx.command is not None and not isinstance(error, commands.CommandOnCooldown): # type: ignore
            ctx.command.reset_cooldown(ctx)

        # Ignore errors
        if isinstance(error, ignored_exceptions):
            return

        # Do not modify specified errors
        if isinstance(error, use_default):
            return await notify(ctx, str(error))

        assert ctx.command is not None

        # Extensive logging for NotFound and Forbidden errors
        if isinstance(error, discord.errors.NotFound):
            print('Unhandled NotFound exception encountered!')
            print(error.args)
            print(error.response)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            await notify(ctx, "I could not find a resource on Discord, you should not see this")

        elif isinstance(error, discord.errors.Forbidden):
            print(f'A 403 error has been encountered in {ctx.command} command, printing stack trace')
            print(error.args)
            print(error.response)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            await notify(ctx, "I do not have the required permissions, you should not see this")

        # Handle specific errors
        elif isinstance(error, commands.NotOwner):
            await notify(ctx, "The command can only be used by the bot owner")

        elif isinstance(error, commands.PrivateMessageOnly):
            await notify(ctx, "The command can only be used in Private Messages")

        elif isinstance(error, commands.NoPrivateMessage):
            await notify(ctx, "The command can not be used in Private Messages")

        elif isinstance(error, commands.MissingRequiredArgument):
            #print("Name:", error.param.name)
            #print("Description:", error.param.description or "")
            #print("Annotation:", error.param.annotation)
            #print("Converter:", error.param.converter)

            parameter_type = ""
            if isinstance(error.param.annotation, int):
                parameter_type = "number"
            elif isinstance(error.param.annotation, str):
                parameter_type = "text"

            if parameter_type != "":
                return await notify(ctx, f"{error.param.name} is a required {parameter_type} argument that is missing.")
            return await notify(ctx, f"{error.param.name} is a required argument that is missing.")

        elif isinstance(error, commands.CommandOnCooldown):
            if error.cooldown.per <= 5:
                return await notify(ctx, "Woah, slow down!", delete_after=3)
            await notify(ctx, f"You're on cooldown, try again in {humanize(error.retry_after, False, max_units=2)}.", delete_after=3)

        elif isinstance(error, commands.NSFWChannelRequired):
            await notify(ctx, "The command can only be used inside NSFW channel")

        # All other errors get returned here with traceback
        else:
            if await self.client.is_owner(ctx.message.author): # type: ignore

                # Create a wrapped paginator which will keep our exception message
                paginator = WrappedPaginator(
                    prefix=f'Exception handler not found for {type(error).__name__}\n```py',
                    suffix='```',
                    max_size=1985
                )

                # Put traceback into a string and clean it
                trace = "".join(
                    traceback.format_exception(type(error), value=error, tb=error.__traceback__)
                ).replace('```', '``\N{zero width space}`')

                paginator.add_line(trace)

                # Create paginator interface, I.E, the interactive buttons thing
                interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
                await interface.send_to(ctx)
                return
            with suppress(HTTPException):
                await ctx.reply(embed=ErrorEmbed(
                    f'Something broke while executing the ``{ctx.command.name}`` command that could not be handled by the main error handler. '
                    'If you\'ve encountered this multiple times, please notify my owner.'
                ))
            print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


async def setup(client: Pidroid):
    await client.add_cog(Error(client))
