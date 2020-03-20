import datetime
import http
import json
import pathlib
import re
import shlex
import typing

import discord
import pytz
import requests
from discord.ext import commands

from . import exceptions
from . import logger

TIMEZONE = pytz.timezone('Europe/Brussels')
MAX_MESSAGE_LENGTH = 2000


# Command manipulations

async def send_command_usage(context, command_name) -> None:
    command = context.command
    if not command:
        raise exceptions.UnknownCommand(command_name)
    if command.usage is not None:
        bot_user = context.bot.user
        prefix = f"@{bot_user.name}#{bot_user.discriminator} " if '@' in context.prefix else context.prefix
        await context.send(f"Syntaxe : `{prefix}{command.qualified_name} {command.usage}`")
        await context.send(f"Aide : `{prefix}help {command.qualified_name}`")
    else:
        logger.warning(f"No usage defined for {command_name}")


def get_commands(context, command_chain: typing.List[str], command_name: str) -> typing.Set[commands.Command]:
    """
    Loop over all top-level commands and groups and trigger a search for the given command.
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

def make_user_list(users, mention=True, separator=", "):
    return separator.join(user.mention if mention else f"@{user.name}#{user.discriminator}" for user in users)


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


def make_announce(context, announce: str, announce_role_name: str = None) -> str:
    """Prefix the announce with the mention of the announce role, if any."""
    if announce_role_name:
        announce_role = try_get(context.guild.roles, error=exceptions.UnknownRole(announce_role_name), name=announce_role_name)
        return f"{announce_role.mention} {announce}"
    else:
        return announce


# WoT data manipulations

def parse_player(context, player):
    # Try to cast player name as Discord guild member
    if not player:
        player = context.guild.get_member(context.author.id)
    elif not isinstance(player, discord.Member):
        player = context.guild.get_member_named(player) or player
    # Parse Wot account name
    if isinstance(player, discord.Member):
        if player.nick:  # Use nickname if set
            player_name = player.nick.split(' ')[0]  # Remove clan tag
        else:  # Else use username
            player_name = player.display_name.split(' ')[0]  # Remove clan tag
    else:
        player_name = player
    return player, player_name


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


async def try_get_message(
        channel: discord.TextChannel, message_id: int, error: commands.CommandError = None) -> discord.Message:
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


# Miscellaneous

def get_current_time():
    return datetime.datetime.now(TIMEZONE)


def get_emoji(emoji_code: typing.Union[str, int], guild_emojis):
    """Return an already validated emoji from its code (unicode string or integer ID)."""
    if isinstance(emoji_code, str):  # Emoji is a unicode string
        return emoji_code
    else:  # Emoji is custom (discord.Emoji) and emoji_code is its id
        return discord.utils.find(lambda e: e.id == emoji_code, guild_emojis)


def get_exp_values(exp_values_file_path: pathlib.Path, exp_values_file_url) -> dict or None:
    """
    Download or load the last version of expected WN8 values.
    On Heroku, the file storing expected WN8 values gets deleted automatically when the bot shuts down.
    """
    exp_values_json = None
    exp_values_file_path.parent.mkdir(parents=True, exist_ok=True)
    if not exp_values_file_path.exists():
        response = requests.get(exp_values_file_url)
        if response.ok:
            with exp_values_file_path.open(mode='w') as exp_values_file:
                exp_values_file.write(response.text)
                exp_values_json = response.json()
            logger.debug(f"Could not find {exp_values_file_path.name}, created it.")
        else:
            logger.warning(f"Could not reach {exp_values_file_url} - "
                           f"Skipped loading of expected WN8 values.")
    else:
        with exp_values_file_path.open(mode='r') as exp_values_file:
            exp_values_json = json.load(exp_values_file)
        logger.debug(f"Loaded expected WN8 values from {exp_values_file_path.name}.")

    if exp_values_json:
        exp_values = {}
        for tank_data in exp_values_json['data']:
            exp_values[tank_data['IDNum']] = {
                'damage_ratio': tank_data['expDamage'],
                'spot_ratio': tank_data['expSpot'],
                'kill_ratio': tank_data['expFrag'],
                'defense_ratio': tank_data['expDef'],
                'win_ratio': tank_data['expWinRate'],
            }
        return exp_values


def is_option_enabled(options: str, option_name: str) -> bool:
    """
    Search a match prefixed with `--` for the option in the list of options.
    :param options: The string of options
    :param option_name: The name of the option to search, without `--`
    :return: True if found, False otherwise
    """
    p = re.compile(rf'^--{option_name}$')
    for option in options and shlex.split(options) or []:  # Preserve inner quoted strings
        if p.search(option):
            return True
    return False


def get_option_value(options: str, option_name: str) -> str or None:
    """
    Search a match prefixed with `--` for the option in the list of options and return its value.
    :param options: The string of options
    :param option_name: The name of the option whose value to search, without `--`
    :return: The option value if found, None otherwise
    """
    p = re.compile(rf'^--{option_name}+=(.+)$')
    for option in options and shlex.split(options) or []:  # Preserve inner quoted strings
        if match_result := p.search(option):
            # Extract option value from regex group
            return match_result.group(1)
    return None
