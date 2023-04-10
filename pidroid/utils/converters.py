import datetime

from dateutil import relativedelta # type: ignore
from discord.ext.commands import Context, Converter # type: ignore
from discord.ext.commands.errors import BadArgument # type: ignore

from pidroid.models.exceptions import InvalidDuration
from pidroid.utils.time import duration_to_relativedelta, utcnow

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
