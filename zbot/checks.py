# -*- coding: utf-8 -*-

import discord
from discord.ext import commands

from zbot import exceptions


async def has_any_mod_role(context, print_error=True):
    # Check if is a DM channel as some commands may be allowed in DMs
    if isinstance(context.message.channel, discord.DMChannel):
        raise commands.NoPrivateMessage()

    if hasattr(context.cog, 'MOD_ROLE_NAMES'):
        author_role_names = [role.name for role in context.author.roles]
        for author_role_name in author_role_names:
            if author_role_name in context.cog.MOD_ROLE_NAMES:
                return True
        if print_error:
            raise exceptions.MissingRoles(context.cog.MOD_ROLE_NAMES)
    else:
        print(f"No mod role defined for {context.cog}.")
    return False
