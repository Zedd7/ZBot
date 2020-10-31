import os

from discord.ext import commands

GUILD_ID = 268364530914951168


class Command(commands.Cog):

    """Superclass of cogs for inherited constants."""

    DISPLAY_NAME = "Undefined display name"
    DISPLAY_SEQUENCE = 99
    MOD_ROLE_NAMES = ['Administrateur']
    USER_ROLE_NAMES = []
    COMMAND_CHANNELS = ['spam', 'zbot', 'modération', 'logs']
    EMBED_COLOR = 0xFAA61A  # Mention message color (gold)

    send_buffer = []  # Serves as a buffer for the message sent to the context

    def __init__(self, bot):
        self.bot = bot
        self.user = self.bot.user
        self.guild = self.bot.get_guild(GUILD_ID)
        self.app_id = os.getenv('WG_API_APPLICATION_ID') or 'demo'

    @staticmethod
    async def mock_send(content=None, *_args, **_kwargs):
        """Catch all messages sent to the context whose `send` method has been matched with this."""
        Command.send_buffer.append(content)
