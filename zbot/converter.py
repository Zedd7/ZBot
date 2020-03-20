import datetime
import re
import typing

import dateutil.parser
import discord
import emojis
import pytz
from discord.ext import commands

from zbot import zbot
from . import exceptions

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


def to_emoji_list(emoji_chain: str) -> typing.List[typing.Union[discord.Emoji, str]]:
    emoji_list = []
    for emoji_code in emoji_chain.split():
        if match_emojis := emojis.get(emoji_code):
            # Emoji is a unicode string
            if len(match_emojis) == 1 and match_emojis.pop() == emoji_code:
                emoji_list.append(emoji_code)
            else:
                raise exceptions.ForbiddenEmoji(emoji_code)
        else:
            # Match custom emoji looking strings
            p = re.compile(r'^<a?:([a-zA-Z_]+):(\d+)>$')
            if match_result := p.search(emoji_code):
                # Extract emoji_id from first regex group
                emoji_name, emoji_id = match_result.group(1, 2)
                # Get emoji from list of emojis visible by bot
                if emoji := discord.utils.get(zbot.bot.emojis, id=int(emoji_id)):
                    # Emoji is a custom image
                    emoji_list.append(emoji)
                else:
                    raise exceptions.ForbiddenEmoji(f":{emoji_name}:")
            else:
                raise exceptions.ForbiddenEmoji(emoji_code)
    emoji_list = list(dict.fromkeys(emoji_list))  # Remove duplicates while preserving order
    return emoji_list
