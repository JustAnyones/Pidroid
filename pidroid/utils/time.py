import datetime
import re

from dateutil.relativedelta import relativedelta # type: ignore
from typing import Optional, Union

from pidroid.models.exceptions import InvalidDuration

DURATION_PATTERN = re.compile(
    r"((?P<years>\d+?) ?(years|year|Y|y) ?)?"
    r"((?P<months>\d+?) ?(months|month|mo) ?)?"
    r"((?P<weeks>\d+?) ?(weeks|week|W|w) ?)?"
    r"((?P<days>\d+?) ?(days|day|D|d) ?)?"
    r"((?P<hours>\d+?) ?(hours|hour|H|h) ?)?"
    r"((?P<minutes>\d+?) ?(minutes|minute|m) ?)?"
    r"((?P<seconds>\d+?) ?(seconds|second|S|s))?"
)

DATE_STYLES = {
    "custom": "%d/%m/%Y @ %I:%M %p (UTC)",
    "iso-8601": "%Y-%m-%dT%H:%M:%S+00:00",
    "hybrid": "%Y-%m-%d @ %I:%M %p",
    "default": "%a, %b %d, %Y %I:%M %p"
}

def _stringify_time_unit(value: int, unit: str, resolve_zero_seconds_to_moment=False) -> str:
    """
    Returns a string to represent a value and time unit, ensuring that it uses the right plural form of the unit.
    >>> _stringify_time_unit(1, "seconds")
    "1 second"
    >>> _stringify_time_unit(24, "hours")
    "24 hours"
    >>> _stringify_time_unit(0, "minutes")
    "less than a minute"
    """
    if unit == "seconds" and value == 0:
        if resolve_zero_seconds_to_moment:
            return "a moment"
        return "0 seconds"
    if value == 1:
        return f"{value} {unit[:-1]}"
    if value == 0:
        return f"less than a {unit[:-1]}"
    return f"{value} {unit}"

def utcnow() -> datetime.datetime:
    """Returns current datetime."""
    return datetime.datetime.now(tz=datetime.timezone.utc)

def duration_string_to_relativedelta(duration_str: str) -> relativedelta:
    """Converts a duration string to a relativedelta object."""
    match = DURATION_PATTERN.fullmatch(duration_str)
    if not match:
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

    duration_dict = {unit: int(amount) for unit, amount in match.groupdict(default=0).items()}
    return relativedelta(**duration_dict)

def duration_to_relativedelta(duration_str: str) -> Optional[relativedelta]:
    """Converts a duration string to a relativedelta object."""
    match = DURATION_PATTERN.fullmatch(duration_str)
    if not match:
        return None

    duration_dict = {unit: int(amount) for unit, amount in match.groupdict(default=0).items()}
    return relativedelta(**duration_dict)

def datetime_to_timedelta(date: datetime.datetime) -> datetime.timedelta:
    """Converts a datetime object to a timedelta object."""
    return date - utcnow()

def datetime_to_duration(date: datetime.datetime) -> float:
    """Convers a datetime object to UNIX timestamp."""
    return datetime_to_timedelta(date).total_seconds()

def timedelta_to_datetime(delta: datetime.timedelta) -> datetime.datetime:
    """Converts a timedelta object to a datetime object."""
    return utcnow() + delta

def delta_to_datetime(delta: Union[datetime.timedelta, relativedelta]) -> datetime.datetime:
    """Converts a timedelta object to a datetime object."""
    return utcnow() + delta

def humanize(
    delta: Union[datetime.datetime, int, float, relativedelta],
    timestamp: bool = True, precision: str = "seconds", max_units: int = 6
) -> str:
    """
    Returns a human-readable version of the relativedelta or datetime.datetime.
    timestamp specifies whether to parse delta values of ints and floats as a timestamp or as duration in seconds
    precision specifies the smallest unit of time to include (e.g. "seconds", "minutes").
    max_units specifies the maximum number of units of time to include (e.g. 1 may include days but not hours).
    """
    if max_units <= 0:
        raise ValueError("max_units must be positive")

    if isinstance(delta, datetime.datetime):
        delta = relativedelta(utcnow(), delta)
    elif isinstance(delta, (int, float)):
        if not timestamp:
            delta = relativedelta(seconds=int(delta))
        else:
            raise NotImplementedError

    delta = abs(delta)

    units = (
        ("years", delta.years),
        ("months", delta.months),
        ("days", delta.days),
        ("hours", delta.hours),
        ("minutes", delta.minutes),
        ("seconds", delta.seconds),
    )

    # Add the time units that are >0, but stop at accuracy or max_units.
    time_strings = []
    unit_count = 0
    for unit, value in units:
        if value:
            time_strings.append(_stringify_time_unit(value, unit))
            unit_count += 1

        if unit == precision or unit_count >= max_units:
            break

    # Add the 'and' between the last two units, if necessary
    if len(time_strings) > 1:
        time_strings[-1] = f"{time_strings[-2]} and {time_strings[-1]}"
        del time_strings[-2]

    # If nothing has been found, just make the value 0 precision, e.g. `0 days`.
    if not time_strings:
        humanized = _stringify_time_unit(0, precision, True)
    else:
        humanized = ", ".join(time_strings)

    return humanized

def time_since(past_datetime: datetime.datetime, precision: str = "seconds", max_units: int = 6) -> str:
    """
    Takes a datetime and returns a human-readable string that describes how long ago that datetime was.
    precision specifies the smallest unit of time to include (e.g. "seconds", "minutes").
    max_units specifies the maximum number of units of time to include (e.g. 1 may include days but not hours).
    """
    delta = abs(relativedelta(utcnow(), past_datetime))

    humanized = humanize(delta, precision=precision, max_units=max_units)

    return f"{humanized} ago"

def timestamp_to_datetime(timestamp: int) -> datetime.datetime:
    """Converts a timestamp to a UTC datetime object."""
    return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)

def timestamp_to_date(timestamp: int, style: str = "default", custom_format: Optional[str] = None) -> str:
    """Converts a timestamp to a UTC human readable date string."""
    datetime = timestamp_to_datetime(timestamp)
    return datetime_to_date(datetime, style, custom_format)

def datetime_to_date(datetime: datetime.datetime, style="default", custom_format: Optional[str] = None) -> str:
    """Converts a datetime object to a UTC human readable date string."""
    if style == 'custom' and custom_format is not None:
        style = custom_format
    else:
        style = DATE_STYLES.get(style, "%a, %b %d, %Y %I:%M %p")
    return datetime.strftime(style)
