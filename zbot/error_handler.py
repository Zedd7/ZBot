# -*- coding: utf-8 -*-

import sys
import traceback

from discord.ext import commands

from . import exceptions
from . import utils


async def handle(context, error):
    if isinstance(error, commands.CommandNotFound):
        pass  # TODO Enable but ignore messages not looking like a command
        # await context.send("Commande inconnue.")
    elif isinstance(error, commands.NoPrivateMessage):
        await context.send("Cette commande ne peut pas être utilisée en message privé.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await context.send(f"Argument manquant: `{error.param.name}`")
        await utils.send_usage(context, context.invoked_with)
    elif isinstance(error, commands.TooManyArguments):
        await context.send(f"Argument(s) surnuméraire(s).")
        await utils.send_usage(context, context.invoked_with)
    elif isinstance(error, commands.BadArgument):
        await context.send(f"Argument(s) incorrect(s).")
        await utils.send_usage(context, context.invoked_with)
    elif isinstance(error, commands.MissingPermissions):
        await context.send(f"Permissions requises: {', '.join(error.missing_perms)}")
    elif isinstance(error, exceptions.MissingRoles):
        await context.send(f"Rôles requis: {', '.join([f'@{r}' for r in error.missing_roles])}")
    elif isinstance(error, exceptions.MissingMessage):
        await context.send(f"Aucun message trouvé pour l'id: `{error.missing_message_id}`")
    elif isinstance(error, exceptions.ForbiddenEmoji):
        await context.send(f"Cet emoji n'est pas autorisé: {error.forbidden_emoji}")
    elif isinstance(error, exceptions.UndersizedArgument):
        await context.send(f"Cet argument est trop petit: `{error.argument_size}` (min: `{error.min_size}`)")
    elif isinstance(error, exceptions.OversizedArgument):
        await context.send(f"Cet argument est trop grand: `{error.argument_size}` (max: `{error.max_size}`)")
    elif isinstance(error, commands.errors.CheckFailure):
        pass
    else:
        print_traceback(error)


def print_traceback(error):
    traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)