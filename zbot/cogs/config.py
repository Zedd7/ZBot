import sys

from discord.ext import commands

from zbot import checker
from zbot import logger
from . import command


class Config(command.Command):

    MAIN_COMMAND_NAME = 'config'
    MOD_ROLE_NAMES = ['Administrateur']
    USER_ROLE_NAMES = []

    def __init__(self, bot):
        super(Config, self).__init__(bot)

    @commands.group(
        name=MAIN_COMMAND_NAME,
        invoke_without_command=True
    )
    @commands.guild_only()
    async def config(self, context):
        if context.invoked_subcommand is None:
            await context.send("Commande manquante.")

    @config.command(
        name='logout',
        aliases=['stop', 'disconnect'],
        usage="",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def logout(self, context):
        logger.info("Logging out...")
        await context.send(f"Déconnexion.")
        await self.bot.logout()
        sys.exit()


def setup(bot):
    bot.add_cog(Config(bot))
    command.setup(bot)
