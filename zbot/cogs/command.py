from discord.ext import commands


class Command(commands.Cog):

    DISPLAY_NAME = "Undefined display name"
    DISPLAY_SEQUENCE = 99
    MAIN_COMMAND_NAME = 'undefined command'
    MOD_ROLE_NAMES = ['Administrateur']
    USER_ROLE_NAMES = []
    EMBED_COLOR = 0x91b6f2

    def __init__(self, bot):
        self.bot = bot  # TODO make use of in cogs instead of zbot.bot
        self.user = self.bot.user
