# -*- coding: utf-8 -*-

import os

import dotenv
from discord.ext import commands

from . import database
from . import error_handler
from . import scheduler

__version__ = '1.0.6'

COGS = ['zbot.cogs.lottery']


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
async def on_command_error(context: commands.Context, error: commands.CommandError):
    await error_handler.handle(context, error)


def run():
    dotenv.load_dotenv()
    db = database.MongoDBDonnector()
    db.open_connection()
    scheduler.setup(db)
    bot_token = os.getenv("BOT_TOKEN")
    if bot_token:
        bot.run(bot_token, bot=True, reconnect=True)
    else:
        print("Not bot token found in .env file under the key 'BOT_TOKEN'.")


if __name__ == '__main__':
    run()
