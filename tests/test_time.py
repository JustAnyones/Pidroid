import datetime

import pytest

from pidroid.utils.time import utcnow, humanize, timestamp_to_datetime, datetime_to_date, datetime_to_duration

FAKE_TIME = datetime.datetime(2023, 12, 26, 12, 14, 46, tzinfo=datetime.timezone.utc)

@pytest.fixture
def patch_datetime_now(monkeypatch: pytest.MonkeyPatch):

    class OwnDateTime:
        @classmethod
        def now(cls, tz: datetime.timezone):
            return FAKE_TIME

    monkeypatch.setattr(datetime, 'datetime', OwnDateTime)

def test_utcnow(patch_datetime_now):
    assert utcnow() == datetime.datetime.now(tz=datetime.timezone.utc)


def test_humanize():
    # Timestamp handling is not implemented
    with pytest.raises(NotImplementedError):
        humanize(delta=1701079883, timestamp=True, precision="hours", max_units=10)

    # Max units cannot be less than or equal to 0
    with pytest.raises(ValueError):
        humanize(delta=50, timestamp=False, precision="seconds", max_units=0)

    # Some formatting checks
    assert humanize(delta=50, timestamp=False, precision="seconds", max_units=10) == "50 seconds"
    assert humanize(delta=360, timestamp=False, precision="seconds", max_units=10) == "6 minutes"
    assert humanize(delta=361, timestamp=False, precision="seconds", max_units=10) == "6 minutes and 1 second"
    assert humanize(delta=360, timestamp=False, precision="hours", max_units=10) == "less than a hour"
    assert humanize(delta=360, timestamp=False, precision="years", max_units=10) == "less than a year"
    assert humanize(delta=60*60*24*365*10 + 361, timestamp=False, precision="seconds", max_units=50) == "3650 days, 6 minutes and 1 second"


def test_timestamp_to_datetime():
    date = datetime.datetime.now(tz=datetime.timezone.utc)
    assert timestamp_to_datetime(date.timestamp()) == date

def test_datetime_to_date():
    date = FAKE_TIME
    assert datetime_to_date(date, style="default") == "Tue, Dec 26, 2023 12:14 PM"
    assert datetime_to_date(date, style="iso-8601") == "2023-12-26T12:14:46+00:00"

def test_datetime_to_duration(patch_datetime_now):
    date = FAKE_TIME + datetime.timedelta(days=5)
    assert datetime_to_duration(date) == 5*24*60*60
