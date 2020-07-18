import datetime
import re
import typing

import dateutil.parser
import discord
import emojis as emoji_lib
import pytz
import tzlocal
from discord.ext import commands

from zbot import zbot
from . import exceptions
from . import utils

COMMUNITY_TIMEZONE = pytz.timezone('Europe/Brussels')
DATABASE_TIMEZONE = pytz.timezone('UTC')


# Time and timezone

def to_datetime(instant: str, print_error=True) -> datetime.datetime:
    time = None
    try:
        time = dateutil.parser.parse(instant)
    except (ValueError, OverflowError):
        if print_error:
            raise exceptions.MisformattedArgument(instant, "YYYY-MM-MM HH:MM:SS")
    return to_community_tz(time)


def to_past_datetime(arg: str):
    """Convert to datetime and check if it is in the past."""
    time = to_datetime(arg)
    if (utils.community_tz_now() - time).total_seconds() <= 0:
        argument_size = to_human_format(time)
        max_argument_size = to_human_format(utils.community_tz_now())
        raise exceptions.OversizedArgument(argument_size, max_argument_size)
    return time


def to_future_datetime(arg: str):
    """Convert to datetime and check if it is in the future."""
    time = to_datetime(arg)
    if (utils.community_tz_now() - time).total_seconds() > 0:
        argument_size = to_human_format(time)
        min_argument_size = to_human_format(utils.community_tz_now())
        raise exceptions.UndersizedArgument(argument_size, min_argument_size)
    return time


def to_timestamp(time: datetime.datetime) -> int:
    return int(to_utc(time).timestamp())


def from_timestamp(timestamp: int) -> datetime.datetime:
    return to_bot_tz(datetime.datetime.fromtimestamp(timestamp))


def to_bot_tz(time: datetime.datetime) -> datetime.datetime:
    if not time.tzinfo:
        return tzlocal.get_localzone().localize(time)
    else:
        return time.astimezone(tzlocal.get_localzone())


def to_community_tz(time: datetime.datetime) -> datetime.datetime:
    if not time.tzinfo:
        return COMMUNITY_TIMEZONE.localize(time)
    else:
        return time.astimezone(COMMUNITY_TIMEZONE)


def to_utc(time: datetime.datetime) -> datetime.datetime:
    if not time.tzinfo:
        return DATABASE_TIMEZONE.localize(time)
    else:
        return time.astimezone(DATABASE_TIMEZONE)


def to_human_format(time: datetime.datetime) -> str:
    if time.hour == 0 and time.minute == 0 and time.second == 0:
        return to_community_tz(time).strftime('%d/%m/%Y')
    else:
        return to_community_tz(time).strftime('%d/%m/%Y à %Hh%M')


# Emojis

def to_emoji(arg: str) -> typing.Union[discord.Emoji, str]:
    emojis = to_emoji_list(arg)
    if not emojis or len(emojis) > 1:  # Empty string or multiple emojis
        raise commands.BadArgument
    return emojis[0]


def to_emoji_list(arg: str) -> typing.List[typing.Union[discord.Emoji, str]]:
    emoji_pattern = re.compile(r'^<a?:([a-zA-Z0-9_]+):(\d+)>$')
    emoji_list = []
    for emoji_code in arg.split():
        if emoji_matches := emoji_lib.get(emoji_code):  # Emoji is a unicode string
            if len(emoji_matches) == 1 and emoji_matches.pop() == emoji_code:
                emoji_list.append(emoji_code)
            else:
                raise exceptions.ForbiddenEmoji(emoji_code)
        else:  # Emoji is a custom image
            # Match custom emoji looking strings
            if match_result := emoji_pattern.search(emoji_code):
                # Extract emoji_id from first regex group
                emoji_name, emoji_id = match_result.group(1, 2)
                # Get emoji from list of emojis visible by bot
                if emoji := discord.utils.get(zbot.bot.emojis, id=int(emoji_id)):
                    emoji_list.append(emoji)
                else:
                    raise exceptions.ForbiddenEmoji(f":{emoji_name}:")
            else:
                raise exceptions.ForbiddenEmoji(emoji_code)
    emoji_list = list(dict.fromkeys(emoji_list))  # Remove duplicates while preserving order
    return emoji_list


# Miscellaneous


def to_positive_int(arg: int):
    """Convert to int and check if it is strictly greater than 0."""
    try:
        value = int(arg)
    except ValueError:
        raise commands.BadArgument
    if value < 0:
        raise exceptions.UndersizedArgument(value, 1)
    return value
