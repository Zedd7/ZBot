import datetime

import pytz
from dateutil import parser

TIMEZONE = pytz.timezone('Europe/Brussels')


def to_datetime(instant: str):
    timestamp = parser.parse(instant)
    return TIMEZONE.localize(timestamp)


def humanize_datetime(timestamp: datetime.datetime):
    return timestamp.strftime('%d/%m/%Y à %Hh%M')
