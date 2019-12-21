import datetime

import dateutil.parser
import pytz

TIMEZONE = pytz.timezone('Europe/Brussels')


def to_datetime(instant: str):
    time = dateutil.parser.parse(instant)
    return TIMEZONE.localize(time)


def to_timestamp(time: datetime.datetime) -> int:
    return int(time.timestamp())


def from_timestamp(timestamp: int) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(timestamp)


def humanize_datetime(time: datetime.datetime) -> str:
    return time.strftime('%d/%m/%Y à %Hh%M')
