# -*- coding: utf-8 -*-

import datetime

import discord
import pytz
from discord.ext import commands

TIMEZONE = pytz.timezone('Europe/Brussels')


async def send_usage(context, command_name) -> None:
    command = await get_command(context, command_name)
    command_usage = command.usage
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
    :param command_name: str
    :return: command: commands.Command
    """
    if parent_command.name == subcommand_name:
        return parent_command
    else:
        for candidate_subcommand in parent_command.all_commands.values():
            subcommand = await get_subcommand(candidate_subcommand, subcommand_name)
            if subcommand:
                return subcommand
    return None


async def has_role(guild: discord.Guild, user: discord.User, role_name: str):
    member = guild.get_member(user.id)
    if member:
        role = discord.utils.get(member.roles, name=role_name)
        if role:
            return True
    return False


async def get_current_time():
    return datetime.datetime.now(TIMEZONE)


async def get_user_list(users, mention=True, separator=", "):
    return separator.join(user.mention if mention else f"@{user.name}#{user.discriminator}" for user in users)


async def make_announce(context, channel: discord.TextChannel, announce_role_name: str, announce: str, embed: discord.Embed = False):
    announce_role = discord.utils.find(lambda role: role.name == announce_role_name, context.guild.roles)
    content = f"{announce_role.mention + ' ' if announce_role is not None else ''}{announce}"
    return await channel.send(content=content, embed=embed)


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
