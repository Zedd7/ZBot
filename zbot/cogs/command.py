# -*- coding: utf-8 -*-

from discord.ext import commands

_bot = None


class Command(commands.Cog):

    MAIN_COMMAND_NAME = 'undefined command'
    MOD_ROLE_NAMES = ['Administrateur']
    USER_ROLE_NAMES = []

    def __init__(self, bot):
        self.bot = bot
        self.user = self.bot.user


def setup(bot):
    global _bot
    _bot = bot


def bot():
    return _bot