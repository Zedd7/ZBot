import sys

from discord.ext import commands

from zbot import checker
from zbot import logger
from . import command


class Admin(command.Command):

    DISPLAY_NAME = "Administration"
    DISPLAY_SEQUENCE = 10
    MAIN_COMMAND_NAME = 'admin'
    MOD_ROLE_NAMES = ['Administrateur']
    USER_ROLE_NAMES = []

    def __init__(self, bot):
        super(Admin, self).__init__(bot)

    @commands.group(
        name=MAIN_COMMAND_NAME,
        invoke_without_command=True
    )
    @commands.guild_only()
    async def admin(self, context):
        if context.invoked_subcommand is None:
            await context.send("Commande manquante.")

    @admin.command(
        name='logout',
        aliases=['stop', 'disconnect'],
        brief="Déconnecte le bot",
        help="Force le bot à se déconnecter du serveur sans arrêter le processus.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def logout(self, context):
        logger.info("Logging out...")
        await context.send(f"Déconnexion.")
        await self.bot.logout()
        sys.exit()


def setup(bot):
    bot.add_cog(Admin(bot))
