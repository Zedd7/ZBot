import datetime
import re
import typing

import dateutil.parser
import discord
import emojis
import pytz
from dateutil.tz import tzlocal

from zbot import zbot
from . import exceptions

COMMUNITY_TIMEZONE = pytz.timezone('Europe/Brussels')
GUILD_TIMEZONE = pytz.timezone('UTC')


# Time and timezone manipulations

def to_datetime(instant: str, print_error=True) -> datetime.datetime:
    local_time = None
    try:
        time = dateutil.parser.parse(instant)
        local_time = COMMUNITY_TIMEZONE.localize(time)
    except (ValueError, OverflowError):
        if print_error:
            raise exceptions.MisformattedArgument(instant, "YYYY-MM-MM HH:MM:SS")
    return local_time


def to_timestamp(time: datetime.datetime) -> int:
    return int(time.timestamp())


def from_timestamp(timestamp: int) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(timestamp)


def humanize_datetime(time: datetime.datetime) -> str:
    return time.strftime('%d/%m/%Y à %Hh%M')


def get_tz_aware_datetime_now() -> datetime.datetime:
    return datetime.datetime.now(tzlocal())


def to_community_tz(time: datetime.datetime) -> datetime.datetime:
    return COMMUNITY_TIMEZONE.localize(time)


def to_guild_tz(time: datetime.datetime) -> datetime.datetime:
    return GUILD_TIMEZONE.localize(time)


# Emojis manipulations

def to_emoji_list(emoji_chain: str) -> typing.List[typing.Union[discord.Emoji, str]]:
    emoji_list = []
    for emoji_code in emoji_chain.split():
        if match_emojis := emojis.get(emoji_code):  # Emoji is a unicode string
            if len(match_emojis) == 1 and match_emojis.pop() == emoji_code:
                emoji_list.append(emoji_code)
            else:
                raise exceptions.ForbiddenEmoji(emoji_code)
        else:  # Emoji is a custom image
            # Match custom emoji looking strings
            p = re.compile(r'^<a?:([a-zA-Z_]+):(\d+)>$')
            if match_result := p.search(emoji_code):
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
