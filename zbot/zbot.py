import os

import discord
import dotenv
from discord.ext import commands
from discord.ext.commands import ExtensionAlreadyLoaded
from discord.ext.commands import ExtensionFailed
from discord.ext.commands import ExtensionNotFound
from discord.ext.commands import NoEntryPointError

from . import database
from . import error_handler
from . import logger
from . import scheduler

__version__ = '1.3.1'

dotenv.load_dotenv()

OWNER_ID = int(os.getenv('OWNER_ID'))
COGS = [
    'zbot.cogs.admin',
    'zbot.cogs.info',
    'zbot.cogs.lottery',
    'zbot.cogs.stats',
]


def get_prefix(client, message):
    prefixes = ['+']
    return commands.when_mentioned_or(*prefixes)(client, message)


bot = commands.Bot(
    command_prefix=get_prefix,
    owner_id=OWNER_ID,
    case_insensitive=True
)

db = database.MongoDBConnector()


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}.")
    bot.remove_command('help')
    for cog in COGS:
        try:
            bot.load_extension(cog)
            logger.info(f"Loaded extension '{cog.split('.')[-1]}'.")
        except (ExtensionNotFound, ExtensionAlreadyLoaded, NoEntryPointError, ExtensionFailed):
            logger.error(f"Failed to loaded extension '{cog.split('.')[-1]}'.", exc_info=True)
    await bot.change_presence(activity=discord.Game(name="Commandes : +help"))


@bot.event
async def on_command_error(context: commands.Context, error: commands.CommandError):
    await error_handler.handle(context, error)


def run():
    dotenv.load_dotenv()
    db.open_connection()
    scheduler.setup(db)
    bot_token = os.getenv('BOT_TOKEN')
    if bot_token:
        bot.run(bot_token, bot=True, reconnect=True)
    else:
        logger.critical("Not bot token found in .env file under the key 'BOT_TOKEN'.")
