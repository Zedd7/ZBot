import datetime
import http
import re
import shlex
import typing

import discord
from discord.ext import commands

from . import converter
from . import exceptions
from . import logger

MAX_MESSAGE_LENGTH = 2000
PLAYER_NAME_PATTERN = re.compile(
    r'^(\w+)'  # One-word player name
    r'([ ]\[([\w-]{2,5})\])?'  # Space-separated clan tag between square brackets
    r'([ ](🕯+))?$'  # Space-separated arbitrary repetition of an emoji
)


# Command manipulations


def get_commands(context, command_chain: typing.List[str], command_name: str) -> typing.Set[commands.Command]:
    """
    Loop over all top-level commands and groups, and trigger a search for the given command.
    If only the command is given, return all matching commands.
    If the full command chain is given, return only the matching command corresponding to the chain.
    :param context: The invocation context
    :param command_chain: The command chain passed to `help`, excluding the searched command
    :param command_name: The command to search
    :return: The set of matching commands
    """

    def _find_subcommands(
        _parent_command: typing.Union[commands.core.Group, commands.core.Command],
        _searched_command_name: str,
    ) -> None:
        """
        Recursively search for matches of the given command in the subcommands of the parent command.
        :param _parent_command: The parent command
        :param _searched_command_name: The name of the command to match with subcommands
        :return: None
        """
        if _searched_command_name in [_parent_command.name] + _parent_command.aliases:
            matching_commands.add(_parent_command)
        elif isinstance(_parent_command, commands.core.Group):
            for _candidate_matching_command in _parent_command.all_commands.values():
                _find_subcommands(_candidate_matching_command, _searched_command_name)

    matching_commands = set()  # `all_commands` contains one entry per alias for each command
    for main_command_name, main_command in context.bot.all_commands.items():
        if main_command_name == command_name:
            matching_commands.add(main_command)
        elif main_command:  # TODO when is this falsy ?
            _find_subcommands(main_command, command_name)
    if len(command_chain) > 0:  # Only return commands whose parents match the command chain, if any
        for matching_command in matching_commands.copy():
            parent_chain = matching_command.full_parent_name.split(' ')
            parent_chain_length, command_chain_length = len(parent_chain), len(command_chain)
            if command_chain != parent_chain[parent_chain_length - command_chain_length:] \
               or command_chain_length > parent_chain_length:
                matching_commands.remove(matching_command)
    return matching_commands


# Printers

def make_user_list(users: typing.List[discord.User], mention=True, separator=", ") -> str:
    """
    Build a list of user names separated by a given separator.
    :param users: The list of users
    :param mention: Whether the names should be mentions or follow the format @name#discrim
    :param separator: The separator to insert between name, space included
    :return: A string of the list of users
    """
    return separator.join([
        user.mention if mention else f"@{user.name}#{user.discriminator}" for user in users
    ])


def make_message_blocks(messages: [str], separator: str = "\n"):
    """Join a list of messages by a separator in a block. Split the block if it is too long."""
    blocks, block = [], ""
    for index, message in enumerate(messages):
        if len(block) + len(message) + len(separator) <= MAX_MESSAGE_LENGTH:
            block += message + (separator if index < len(messages) - 1 else "")
        elif len(message) + len(separator) <= MAX_MESSAGE_LENGTH:
            blocks.append(block)
            block = ""
        else:
            raise ValueError("message is longer than maximum message length")
    blocks.append(block)
    return blocks


def make_announce(guild, announce: str, announce_role_name: str = None) -> str:
    """Prefix the announce with the mention of the announce role, if any."""
    if announce_role_name:
        announce_role = try_get(
            guild.roles, error=exceptions.UnknownRole(announce_role_name), name=announce_role_name
        )
        return f"{announce_role.mention} {announce}"
    else:
        return announce


# Safe utilities

def try_get(iterable, error: commands.CommandError = None, **filters):
    """Attempt to find a element and raises if not found and if an error is provided."""
    try:
        result = discord.utils.get(iterable, **filters)
        if not result and error:
            raise error
        return result
    except discord.NotFound:
        if error:
            raise error


def try_get_emoji(
    emojis, emoji_code: typing.Union[str, int], error: commands.CommandError = None
) -> typing.Union[str, discord.Emoji] or None:
    """
    Attempt to retrieve an emoji by code (unicode string or integer ID) and raises if not found and
    if an error is provided.
    """
    if isinstance(emoji_code, str):  # Emoji is a unicode string
        return emoji_code
    else:  # Emoji is custom (discord.Emoji) and emoji_code is its id
        try:
            emoji = discord.utils.find(lambda e: e.id == emoji_code, emojis)
            if not emoji and error:
                raise error
            return emoji
        except discord.NotFound:
            if error:
                raise error


async def try_get_message(
    channel: discord.TextChannel, message_id: int, error: commands.CommandError = None
) -> discord.Message:
    """Attempt to retrieve a message by id and raises if not found and if an error is provided."""
    try:
        message = await channel.fetch_message(message_id)
        if not message and error:
            raise error
        return message
    except discord.NotFound:
        if error:
            raise error


async def try_dm(user: discord.User, message: str) -> bool:
    """Attempt to dm a user and return True if it was successful, False otherwise."""
    try:
        await user.send(message)
        return True
    except discord.errors.HTTPException as error:
        if error.status != http.HTTPStatus.FORBIDDEN:  # DM blocked by user
            logger.error(error, exc_info=True)
        return False


async def try_dms(user: discord.User, messages: typing.List[str], group_in_blocks: bool) -> bool:
    """Attempt to dm a list of messages to a user and return True if it was successful, False otherwise."""
    result = True
    for content in (make_message_blocks(messages) if group_in_blocks else messages):
        result &= await try_dm(user, content)
    return result


# Parsers

def parse_player(guild, player: typing.Union[discord.Member, str], fallback: discord.Member):
    """
    Parse a name as a WoT player name. The name can be empty, the username of a member or the
    nickname of a member, and can have a clan tag.
    :param: guild: The Discord guild of the bot
    :param: player: The name to parse
    :param: fallback: The member whose name to use if none was provided
    """
    # Try to cast player name as Discord guild member
    if not player:
        player = guild.get_member(fallback.id)
    elif not isinstance(player, discord.Member):
        player = guild.get_member_named(player) or player

    # Parse Wot account name
    if isinstance(player, discord.Member):
        result = PLAYER_NAME_PATTERN.match(player.display_name)
        player_name = result.group(1)
    else:
        player_name = player
    return player, player_name


# Miscellaneous

def community_tz_now():
    """Return the current datetime for the community timezone."""
    return converter.to_community_tz(bot_tz_now())


def bot_tz_now():
    """Return the current datetime for the bot timezone."""
    return converter.to_bot_tz(datetime.datetime.now())


def utc_now():
    """Return the current datetime for the UTC timezone."""
    return converter.to_utc(bot_tz_now())


def is_time_elapsed(past_time, now, delay):
    return past_time < now - delay


def is_time_almost_elapsed(past_time, now, delay, tolerance: datetime.timedelta = datetime.timedelta(minutes=1)):
    return is_time_elapsed(past_time, now, delay - tolerance)


def is_option_enabled(options: str, option_name: str, has_value=False) -> bool:
    """
    Search a match for the option prefixed with `--`.
    :param options: The string of options
    :param option_name: The name of the option to search, without `--`
    :param has_value: Whether the option should be found with a value assigned
    :return: True if found, False otherwise
    """
    p = re.compile(rf'^--{option_name}' + ('$' if not has_value else ''))
    for option in options and shlex.split(options) or []:  # Preserve inner quoted strings
        if p.search(option):
            return True
    return False


def get_option_value(options: str, option_name: str) -> str or None:
    """
    Search a match for the option prefixed with `--` and return its value.
    :param options: The string of options
    :param option_name: The name of the option whose value to search, without `--`
    :return: The option value if found, None otherwise
    """
    p = re.compile(rf'^--{option_name}=(.+)$')
    for option in options and shlex.split(options) or []:  # Preserve inner quoted strings
        if match_result := p.search(option):
            # Extract option value from regex group
            return match_result.group(1)
    return None


def remove_option(options: str, option_name: str) -> str:
    """
    Search a match for the option prefixed with `--` and return the result of its removal.
    :param options: The string of options
    :param option_name: The name of the option to search, without `--`
    :return: The options stripped from the searched option and its value
    """
    p = re.compile(rf'--{option_name}+(=\w+)?')
    return re.sub(p, '', options).rstrip()


def sanitize_player_names(member_names):
    """Filter out member names that do not follow either the `player` or `player [CLAN]` pattern."""
    sanitized_player_names = []
    for member_name in member_names:
        result = PLAYER_NAME_PATTERN.match(member_name)
        if result:
            sanitized_player_name = result.group(1)
            sanitized_player_names.append(sanitized_player_name)
    return sanitized_player_names
