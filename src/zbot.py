import os

import dotenv
from discord.ext import commands

import src.utils as utils

__version__ = '1.0.4'

COGS = ['src.cogs.lottery']


def get_prefix(client, message):
    prefixes = ['+']
    return commands.when_mentioned_or(*prefixes)(client, message)


bot = commands.Bot(
    command_prefix=get_prefix,
    owner_id=156837349966217216,
    case_insensitive=True
)


@bot.event
async def on_ready():
    bot.remove_command('help')
    print(f"Logged in as {bot.user}.")
    for cog in COGS:
        bot.load_extension(cog)
        print(f"Loaded extension '{cog.split('.')[-1]}'.")


@bot.event
async def on_command_error(context, error):
    if isinstance(error, commands.CommandNotFound):
        pass  # TODO ignore messages not looking like a command
        # await context.send("Commande inconnue.")
    elif isinstance(error, commands.NoPrivateMessage):
        await context.send("Cette commande ne peut pas être utilisée en message privé.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await context.send(f"Argument manquant: `{error.param.name}`")
        await utils.send_usage(context)
    elif isinstance(error, commands.TooManyArguments):
        await context.send(f"Argument(s) surnuméraire(s).")
        await utils.send_usage(context)
    elif isinstance(error, commands.BadArgument):
        await context.send(f"Argument(s) incorrect(s).")
        await utils.send_usage(context)
    elif isinstance(error, commands.MissingPermissions):
        await context.send(f"Permissions requises: {', '.join(error.missing_perms)}")
    elif isinstance(error, utils.MissingRoles):
        await context.send(f"Rôles requis: {', '.join([f'@{r}' for r in error.missing_roles])}")
    elif isinstance(error, utils.MissingMessage):
        await context.send(f"Aucun message trouvé pour l'id: `{error.missing_message_id}`")
    elif isinstance(error, utils.ForbiddenEmoji):
        await context.send(f"Cet emoji n'est pas autorisé: {error.forbidden_emoji}")
    elif isinstance(error, utils.UndersizedArgument):
        await context.send(f"Cet argument est trop petit: `{error.argument_size}` (max: `{error.min}`)")
    elif isinstance(error, utils.OversizedArgument):
        await context.send(f"Cet argument est trop grand: `{error.argument_size}` (max: `{error.max}`)")
    elif isinstance(error, commands.errors.CheckFailure):
        pass
    else:
        print(f"Caught unhandled error.\n"
              f"Type: {type(error)}\n"
              f"Description: {error}")


def run():
    dotenv.load_dotenv()
    bot_token = os.getenv("BOT_TOKEN")
    if bot_token:
        bot.run(bot_token, bot=True, reconnect=True)
    else:
        print("Not bot token found in .env file under the key 'BOT_TOKEN'.")
