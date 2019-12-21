from discord.ext import commands

from . import exceptions
from . import logger
from . import utils


async def handle(context, error):
    # Discord.py exceptions
    if isinstance(error, commands.BadArgument):
        await context.send(f"Argument(s) incorrect(s).")
        await utils.send_command_usage(context, context.invoked_with)
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore messages starting with '+'
        # Use exceptions.UnknownCommand or exceptions.MissingSubCommand for manual raise
    elif isinstance(error, commands.MissingPermissions):
        await context.send(f"Permissions requises: {', '.join(error.missing_perms)}")
    elif isinstance(error, commands.MissingRequiredArgument):
        await context.send(f"Argument manquant: `{error.param.name}`")
        await utils.send_command_usage(context, context.invoked_with)
    elif isinstance(error, commands.NoPrivateMessage):
        await context.send("Cette commande ne peut pas être utilisée en message privé.")
    elif isinstance(error, commands.TooManyArguments):
        await context.send(f"Argument(s) surnuméraire(s).")
        await utils.send_command_usage(context, context.invoked_with)
    # ZBot exceptions
    elif isinstance(error, exceptions.ForbiddenEmoji):
        await context.send(f"Cet emoji n'est pas autorisé: `{error.forbidden_emoji}`")
    elif isinstance(error, exceptions.MissingClan):
        await context.send(f"Aucun clan WoT trouvé pour le joueur: `{error.player_name}`")
    elif isinstance(error, exceptions.MissingConditionalArgument):
        await context.send(error.message)
    elif isinstance(error, exceptions.MissingEmoji):
        await context.send(f"Cet emoji n'a pas été trouvé: {error.missing_emoji}")
    elif isinstance(error, exceptions.MissingMessage):
        await context.send(f"Aucun message trouvé pour l'id: `{error.missing_message_id}`")
    elif isinstance(error, exceptions.MissingRoles):
        await context.send(f"Rôle(s) requis: {', '.join([f'@{r}' for r in error.missing_roles])}")
    elif isinstance(error, exceptions.MissingSubCommand):
        await context.send(f"Sous-commande manquante ou inconnue pour : `+{error.group_command_name}`")
    elif isinstance(error, exceptions.MissingUser):
        await context.send(f"Utilisateur Discord inconnu: `{error.missing_user_name}`")
    elif isinstance(error, exceptions.OversizedArgument):
        await context.send(f"Cet argument est trop grand: `{error.argument_size}` (max: `{error.max_size}`)")
    elif isinstance(error, exceptions.UndersizedArgument):
        await context.send(f"Cet argument est trop petit: `{error.argument_size}` (min: `{error.min_size}`)")
    elif isinstance(error, exceptions.UnknownClan):
        await context.send(f"Clan WoT inconnu: `{error.unknown_clan_name}`")
    elif isinstance(error, exceptions.UnknownCommand):
        await context.send(f"Commande inconnue: `{error.unknown_command_name}`")
    elif isinstance(error, exceptions.UnknownLottery):
        await context.send(f"Identifiant de tirage au sort inconnu: `{error.unknown_lottery_id}`")
    elif isinstance(error, exceptions.UnknownPlayer):
        await context.send(f"Joueur WoT inconnu: `{error.unknown_player_name}`")
    # Unhandled exceptions
    elif isinstance(error, commands.errors.CheckFailure):
        pass
    else:
        logger.error(error, exc_info=True)
