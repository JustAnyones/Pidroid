import datetime
import discord
import typing

from dateutil import relativedelta
from discord.ext.commands import Context, Converter
from discord.ext.commands.converter import MemberConverter, UserConverter
from discord.ext.commands.errors import BadArgument, CommandError

from cogs.models.exceptions import InvalidDuration
from cogs.utils.checks import member_above_bot, is_guild_moderator, member_above_moderator
from cogs.utils.time import duration_to_relativedelta, utcnow

class DurationDelta(Converter):
    """Convert duration strings into dateutil.relativedelta.relativedelta objects."""

    async def convert(self, ctx: Context, duration_str: str) -> relativedelta.relativedelta:
        """
        Converts a `duration` string to an int object.
        The converter supports the following symbols for each unit of time:
        - years: `Y`, `y`, `year`, `years`
        - months: `mo`, `month`, `months`
        - weeks: `w`, `W`, `week`, `weeks`
        - days: `d`, `D`, `day`, `days`
        - hours: `H`, `h`, `hour`, `hours`
        - minutes: `m`, `minute`, `minutes`
        - seconds: `S`, `s`, `second`, `seconds`
        The units need to be provided in descending order of magnitude.
        """

        delta = duration_to_relativedelta(duration_str)
        if delta is None:
            raise InvalidDuration((
                f"'{duration_str}' is not a valid duration!\n"
                "Pidroid supports the following symbols for each unit of time:\n"
                "- years: `Y`, `y`, `year`, `years`\n"
                "- months: `mo`, `month`, `months`\n"
                "- weeks: `w`, `W`, `week`, `weeks`\n"
                "- days: `d`, `D`, `day`, `days`\n"
                "- hours: `H`, `h`, `hour`, `hours`\n"
                "- minutes: `m`, `minute`, `minutes`\n"
                "- seconds: `S`, `s`, `second`, `seconds`\n"
                "The units need to be provided in descending order of magnitude."
            ))
        return delta

class Duration(DurationDelta):
    """Convert duration strings into UTC datetime.datetime objects."""

    async def convert(self, ctx: Context, duration: str) -> datetime.datetime:
        """
        Converts a `duration` string to a datetime object that's `duration` in the future.
        The converter supports the same symbols for each unit of time as its parent class.
        """
        delta = await super().convert(ctx, duration)

        try:
            return utcnow() + delta
        except (ValueError, OverflowError):
            raise BadArgument(f"`{duration}` results in a datetime outside the supported range.")

class Offender(Converter):
    """Convert usernames, names, nicknames and IDs to discord member or user objects."""

    async def convert(self, ctx: Context, user: str, require_member=False) -> typing.Union[discord.Member, discord.User]:
        command_name = ctx.command.name

        if user is None:
            raise BadArgument(f"Please specify someone you are trying to {command_name}!")

        # discord.py uses similiar method, but it just wraps it in a for loop
        try:
            user = await MemberConverter().convert(ctx, user)
        except CommandError:
            if require_member:
                raise BadArgument("Unable to resolve member")

            user = await UserConverter().convert(ctx, user)

        if user == ctx.message.author:
            raise BadArgument(f"You cannot {command_name} yourself!")

        if command_name != "warn":
            if is_guild_moderator(ctx.guild, ctx.channel, user):
                if command_name == 'kidnap':
                    raise BadArgument("You cannot kidnap one of your own!")
                raise BadArgument(f"You cannot {command_name} a moderator!")

        if member_above_moderator(user, ctx.author):
            raise BadArgument("Specified member is above you!")

        if member_above_bot(ctx.guild, user):
            raise BadArgument("Specified member is above me!")

        return user


def setup(client):
    pass

def teardown(client):
    pass
