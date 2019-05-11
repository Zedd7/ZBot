import datetime

import dateutil.parser
import pytz

TIMEZONE = pytz.timezone('Europe/Brussels')


def to_datetime(instant: str):
    timestamp = dateutil.parser.parse(instant)
    return TIMEZONE.localize(timestamp)


def humanize_datetime(timestamp: datetime.datetime):
    return timestamp.strftime('%d/%m/%Y à %Hh%M')
