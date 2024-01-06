import os

import discord
from discord.ext import commands
from discord.ext.commands import ExtensionAlreadyLoaded
from discord.ext.commands import ExtensionFailed
from discord.ext.commands import ExtensionNotFound
from discord.ext.commands import NoEntryPointError
from dotenv import load_dotenv

from . import database
from . import error_handler
from . import logger
from . import scheduler


__version__ = '2.0.0'

load_dotenv()


class ZBot(commands.Bot):

    EXTENSIONS = [
        'zbot.cogs.admin',
        'zbot.cogs.bot',
        'zbot.cogs.lottery',
        'zbot.cogs.poll',
        'zbot.cogs.messaging',
        'zbot.cogs.server',
        'zbot.cogs.special',
        'zbot.cogs.stats',
    ]

    def __init__(self, db):
        super().__init__(
            command_prefix=self.get_prefix,
            case_insensitive=True,
            help_command=None,
            owner_id=int(os.getenv('OWNER_ID')),
            intents=discord.Intents.all(),
        )
        self.db = db

    async def setup_hook(self):
        self.db.open_connection()
        scheduler.setup(self.db)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user}.")
        for extension in self.EXTENSIONS:
            try:
                await self.load_extension(extension)
                logger.info(f"Loaded extension '{extension.split('.')[-1]}'.")
            except (ExtensionNotFound, ExtensionAlreadyLoaded, NoEntryPointError, ExtensionFailed):
                logger.error(f"Failed to loaded extension '{extension.split('.')[-1]}'.", exc_info=True)
        await self.change_presence(activity=discord.Game(name="Commandes : +help"))

    async def on_command_error(self, context: commands.Context, error: commands.CommandError):
        await error_handler.handle(context, error)

    async def get_prefix(self, message):
        prefixes = ['+']
        return commands.when_mentioned_or(*prefixes)(self, message)


def run():
    db = database.MongoDBConnector()
    bot = ZBot(db)
    bot.run(os.getenv('BOT_TOKEN'))
