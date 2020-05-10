import discord
from discord.ext import commands

from . import exceptions
from . import logger


def has_any_mod_role(context, user: discord.User = None, print_error=True):
    """Return True if the context author or provided user has a mod role defined in the context's cog."""
    return has_any_guild_role(context, 'MOD_ROLE_NAMES', user=user, print_error=print_error)


def has_any_user_role(context, user: discord.User = None, print_error=True):
    """Return True if the context author or provided user has a user role defined in the context's cog."""
    return has_any_guild_role(context, 'USER_ROLE_NAMES', user=user, print_error=print_error)


def has_any_guild_role(context, role_names_key, user: discord.User = None, print_error=True):
    # Check if is a DM channel as some commands may be allowed in DMs
    if isinstance(context.message.channel, discord.DMChannel):
        raise commands.NoPrivateMessage()

    if hasattr(context.cog, role_names_key):
        role_names = getattr(context.cog, role_names_key)
        if has_any_role(context.guild, user or context.author, role_names):
            return True
        elif print_error:
            raise exceptions.MissingRoles(role_names)
    else:
        logger.warning(f"No mod role defined for {context.cog}.")
    return False


def has_any_role(guild: discord.Guild, user: discord.User, role_names: list):
    for role_name in role_names:
        if has_guild_role(guild, user, role_name):
            return True
    return False


def has_guild_role(guild: discord.Guild, user: discord.User, role_name: str):
    member = guild.get_member(user.id)
    return member and has_role(member, role_name)


def has_role(member: discord.Member, role_name: str):
    return discord.utils.get(member.roles, name=role_name)


async def is_allowed_in_current_channel(context):
    if context.channel.name not in context.cog.ALLOWED_CHANNELS \
            and not has_any_mod_role(context, print_error=False):
        try:
            await context.message.add_reaction("❌")
            await context.author.send(f"Ce canal n'est pas autorisé : {context.channel.mention}")
            return False
        except discord.Forbidden:
            pass
    return True


async def is_allowed_in_all_channels(context):
    """Placeholder check returning always True."""
    return True
