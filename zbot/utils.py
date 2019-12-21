import datetime
import http
import json
import typing

import discord
import pytz
import requests
from discord.ext import commands

from . import exceptions, logger

TIMEZONE = pytz.timezone('Europe/Brussels')
MAX_MESSAGE_LENGTH = 2000


# Command manipulations

async def send_command_usage(context, command_name) -> None:
    command = get_command(context, command_name)
    if not command:
        raise exceptions.UnknownCommand(command_name)
    if command.usage is not None:
        bot_user = context.bot.user
        prefix = f"@{bot_user.name}#{bot_user.discriminator} " if '@' in context.prefix else context.prefix
        await context.send(f"Syntaxe : `{prefix}{command.qualified_name} {command.usage}`")
        await context.send(f"Aide : `{prefix}help {command.qualified_name}`")
    else:
        logger.warning(f"No usage defined for {command_name}")


def get_command(context, command_name) -> commands.Command or None:
    if command_name not in context.bot.all_commands:
        for _, cog in context.bot.cogs.items():
            if hasattr(cog, 'MAIN_COMMAND_NAME'):
                parent_command = context.bot.all_commands.get(cog.MAIN_COMMAND_NAME)
                subcommand = parent_command and get_subcommand(parent_command, command_name)
                if subcommand:
                    return subcommand
            else:
                logger.warning(f"No main command defined for {context.cog}.")
    else:
        return context.bot.all_commands[command_name]
    return None


def get_subcommand(parent_command, subcommand_name) -> commands.Command or None:
    """
    Recursively search for the given command in the subcommands of the parent command and return it.
    :param parent_command: commands.Command
    :param subcommand_name: str
    :return: command: commands.Command
    """
    if subcommand_name in [parent_command.name] + parent_command.aliases:
        return parent_command
    elif isinstance(parent_command, commands.core.Group):
        for candidate_subcommand in parent_command.all_commands.values():
            subcommand = get_subcommand(candidate_subcommand, subcommand_name)
            if subcommand:
                return subcommand
    return None


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


# Miscellaneous

def get_current_time():
    return datetime.datetime.now(TIMEZONE)


def get_emoji(emoji_code: typing.Union[str, int], guild_emojis):
    if isinstance(emoji_code, str):  # Emoji is a unicode string
        return emoji_code
    else:  # Emoji is custom (discord.Emoji) and emoji_code is its id
        return discord.utils.find(lambda e: e.id == emoji_code, guild_emojis)


def get_exp_values(exp_values_file_path, exp_values_file_url) -> dict or None:
    """Download or load the last version of WN8 expected values."""
    exp_values_file_path.parent.mkdir(parents=True, exist_ok=True)
    if not exp_values_file_path.exists():  # TODO update if too old (check header in json)
        response = requests.get(exp_values_file_url)
        with exp_values_file_path.open(mode='w') as exp_values_file:
            exp_values_file.write(response.text)
            exp_values_json = response.json()
    else:
        with exp_values_file_path.open(mode='r') as exp_values_file:
            exp_values_json = json.load(exp_values_file)

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
