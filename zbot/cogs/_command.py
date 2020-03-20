from discord.ext import commands


class Command(commands.Cog):

    """Superclass of cogs for inherited constants."""

    DISPLAY_NAME = "Undefined display name"
    DISPLAY_SEQUENCE = 99
    MOD_ROLE_NAMES = ['Administrateur']
    USER_ROLE_NAMES = []
    EMBED_COLOR = 0xFAA61A  # Mention message color (gold)

    def __init__(self, bot):
        self.bot = bot
        self.user = self.bot.user
