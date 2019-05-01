# -*- coding: utf-8 -*-

import datetime
import json

import discord
import pytz
import requests
from discord.ext import commands

TIMEZONE = pytz.timezone('Europe/Brussels')


# Command manipulations

async def send_usage(context, command_name) -> None:
    command = await get_command(context, command_name)
    command_usage = command.usage if command else None
    if command_usage:
        bot_user = context.bot.user
        prefix = f"@{bot_user.name}#{bot_user.discriminator} " if '@' in context.prefix else context.prefix
        await context.send(f"Syntaxe: `{prefix}{command.qualified_name} {command_usage}`\n")
    else:
        print(f"No usage defined for {command_name}")


async def is_subcommand(bot, command_name):
    return command_name not in bot.all_commands


async def get_command(context, command_name) -> commands.Command or None:
    if await is_subcommand(context.bot, command_name):
        if hasattr(context.cog, 'MAIN_COMMAND_NAME'):
            main_command_name = context.cog.MAIN_COMMAND_NAME
            parent_command = context.bot.all_commands[main_command_name]
            return await get_subcommand(parent_command, command_name)
        else:
            print(f"No main command defined for {context.cog}.")
    else:
        return context.bot.all_commands[command_name]
    return None


async def get_subcommand(parent_command, subcommand_name) -> commands.Command or None:
    """
    Recursively search for the given command in the subcommands of the parent command and return it.
    :param parent_command: commands.Command
    :param subcommand_name: str
    :return: command: commands.Command
    """
    if parent_command.name == subcommand_name:
        return parent_command
    elif isinstance(parent_command, commands.core.Group):
        for candidate_subcommand in parent_command.all_commands.values():
            subcommand = await get_subcommand(candidate_subcommand, subcommand_name)
            if subcommand:
                return subcommand
    return None


# WoT data manipulations

async def parse_player(context, player):
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


# Inline getters

async def try_get(error: commands.CommandError, iterable, **filters):
    try:
        result = discord.utils.get(iterable, **filters)
        if not result:
            raise error
        return result
    except discord.NotFound:
        raise error


async def try_get_message(error: commands.CommandError, channel: discord.TextChannel, message_id: int):
    try:
        message = await channel.fetch_message(message_id)
        if not message:
            raise error
        return message
    except discord.NotFound:
        raise error


# Printers

async def make_user_list(users, mention=True, separator=", "):
    return separator.join(user.mention if mention else f"@{user.name}#{user.discriminator}" for user in users)


async def make_announce(context, channel: discord.TextChannel, announce_role_name: str, announce: str, embed: discord.Embed = False):
    announce_role = discord.utils.find(lambda role: role.name == announce_role_name, context.guild.roles)
    content = f"{announce_role.mention + ' ' if announce_role is not None else ''}{announce}"
    return await channel.send(content=content, embed=embed)


# Miscellaneous

async def get_current_time():
    return datetime.datetime.now(TIMEZONE)


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
