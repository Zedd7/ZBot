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
    elif any(isinstance(error, error_type) for error_type in (
        commands.InvalidEndOfQuotedStringError,
        commands.ExpectedClosingQuoteError,
        commands.UnexpectedQuoteError
    )):
        await context.send(
            f"Argument texte mal construit. "
            f"Entourez chaque texte de double guillemets `\"comme ceci\"`.")
        await utils.send_command_usage(context, context.invoked_with)
    elif isinstance(error, commands.MissingPermissions):
        await context.send(f"Permissions requises : {', '.join(error.missing_perms)}")
    elif isinstance(error, commands.MissingRequiredArgument):
        await context.send(f"Argument manquant : `{error.param.name}`")
        await utils.send_command_usage(context, context.invoked_with)
    elif isinstance(error, commands.NoPrivateMessage):
        await context.send("Cette commande ne peut pas être utilisée en message privé.")
    elif isinstance(error, commands.TooManyArguments):
        await context.send(f"Argument(s) surnuméraire(s).")
        await utils.send_command_usage(context, context.invoked_with)

    # ZBot exceptions

    elif isinstance(error, exceptions.ForbiddenChannel):
        await context.send(f"Ce canal n'est pas autorisé : {error.forbidden_channel.mention}")
    elif isinstance(error, exceptions.ForbiddenEmoji):
        await context.send(
            "Cet emoji n'est pas autorisé" +
            (f" : `{error.forbidden_emoji}`" if error.forbidden_emoji else ".")
        )
    elif isinstance(error, exceptions.MisformattedArgument):
        await context.send(
            f"Format d'argument incorrect. Format attendu : `{error.correct_format}`. Valeur "
            f"de l'argument reçu: `{error.argument}`.")
    elif isinstance(error, exceptions.MissingClan):
        await context.send(f"Aucun clan WoT trouvé pour le joueur : `{error.player_name}`")
    elif isinstance(error, exceptions.MissingConditionalArgument):
        await context.send(error.message)
    elif isinstance(error, exceptions.MissingEmoji):
        await context.send(f"Cet emoji n'a pas été trouvé : {error.missing_emoji}")
    elif isinstance(error, exceptions.MissingMessage):
        await context.send(f"Aucun message trouvé pour l'id : `{error.missing_message_id}`")
    elif isinstance(error, exceptions.MissingRoles):
        await context.send(f"Rôle(s) requis : {', '.join([f'@{r}' for r in error.missing_roles])}")
    elif isinstance(error, exceptions.MissingSubCommand):
        await context.send(
            f"Sous-commande manquante ou inconnue pour : `+{error.group_command_name}`\n"
            f"Affichez la liste des sous-commandes disponibles avec `+help {error.group_command_name}`")
    elif isinstance(error, exceptions.MissingUser):
        await context.send(f"Utilisateur Discord inconnu : `{error.missing_user_name}`")
    elif isinstance(error, exceptions.OversizedArgument):
        await context.send(
            f"Cet argument est trop grand : `{error.argument_size}` (max : `{error.max_size}`)")
    elif isinstance(error, exceptions.UndersizedArgument):
        await context.send(
            f"Cet argument est trop petit : `{error.argument_size}` (min : `{error.min_size}`)")
    elif isinstance(error, exceptions.UnknownClan):
        await context.send(f"Clan WoT inconnu : `{error.unknown_clan_name}`")
    elif isinstance(error, exceptions.UnknownCommand):
        await context.send(f"Commande inconnue : `{error.unknown_command_name}`")
    elif any(isinstance(error, error_type) for error_type in (
        exceptions.UnknownLottery,
        exceptions.UnknownPoll
    )):
        await context.send(f"Identifiant inconnu : `{error.unknown_id}`")
    elif isinstance(error, exceptions.UnknownPlayer):
        await context.send(f"Joueur WoT inconnu : `{error.unknown_player_name}`")
    elif isinstance(error, exceptions.UnknownRole):
        await context.send(f"Rôle inconnu : `{error.unknown_role_name}`")

    # Unhandled exceptions

    elif isinstance(error, commands.errors.CheckFailure):
        pass
    else:
        logger.error(error, exc_info=True)
