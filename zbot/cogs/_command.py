import os

from discord.ext import commands

GUILD_ID = 268364530914951168


class Command(commands.Cog):

    """Superclass of cogs for inherited constants."""

    DISPLAY_NAME = "Undefined display name"
    DISPLAY_SEQUENCE = 99
    MOD_ROLE_NAMES = ['Administrateur']
    USER_ROLE_NAMES = []
    ALLOWED_CHANNELS = ['spam', 'zbot', 'modération', 'logs']
    EMBED_COLOR = 0xFAA61A  # Mention message color (gold)

    def __init__(self, bot):
        self.bot = bot
        self.user = self.bot.user
        self.guild = bot.get_guild(GUILD_ID)
        self.app_id = os.getenv('WG_API_APPLICATION_ID') or 'demo'
