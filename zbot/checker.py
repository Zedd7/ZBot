import discord
from discord.ext import commands

from . import exceptions
from . import logger


async def has_any_mod_role(context, print_error=True):
    return await has_any_guild_role(context, 'MOD_ROLE_NAMES', print_error)


async def has_any_user_role(context, print_error=True):
    return await has_any_guild_role(context, 'USER_ROLE_NAMES', print_error)


async def has_any_guild_role(context, role_names_key, print_error=True):
    # Check if is a DM channel as some commands may be allowed in DMs
    if isinstance(context.message.channel, discord.DMChannel):
        raise commands.NoPrivateMessage()

    if hasattr(context.cog, role_names_key):
        role_names = getattr(context.cog, role_names_key)
        if await has_any_role(context.guild, context.author, role_names):
            return True
        elif print_error:
            raise exceptions.MissingRoles(role_names)
    else:
        logger.warning(f"No mod role defined for {context.cog}.")
    return False


async def has_any_role(guild: discord.Guild, user: discord.User, role_names: list):
    for role_name in role_names:
        if await has_role(guild, user, role_name):
            return True
    return False


async def has_role(guild: discord.Guild, user: discord.User, role_name: str):
    member = guild.get_member(user.id)
    return member and discord.utils.get(member.roles, name=role_name)