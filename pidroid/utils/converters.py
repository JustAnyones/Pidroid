import datetime

from dateutil import relativedelta
from discord.ext.commands import BadArgument, Context, Converter
from typing import override

from pidroid.utils.time import delta_to_datetime, try_convert_duration_to_relativedelta

class DurationDelta(Converter):
    """Convert duration strings into dateutil.relativedelta.relativedelta objects."""

    @override
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
        return try_convert_duration_to_relativedelta(duration_str)

class Duration(Converter):
    """Convert duration strings into UTC datetime.datetime objects."""

    @override
    async def convert(self, ctx: Context, duration: str) -> datetime.datetime:
        """
        Converts a `duration` string to a datetime object that's `duration` in the future.
        The converter supports the same symbols for each unit of time as its parent class.
        """
        delta = try_convert_duration_to_relativedelta(duration)

        try:
            return delta_to_datetime(delta)
        except (ValueError, OverflowError):
            raise BadArgument(f"`{duration}` results in a datetime outside the supported range.")
