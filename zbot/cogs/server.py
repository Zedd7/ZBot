import discord
from discord.ext import commands

from zbot import checker
from zbot import utils
from . import _command


class Server(_command.Command):

    """Commands for information about the bot."""

    DISPLAY_NAME = "Informations sur le serveur"
    DISPLAY_SEQUENCE = 2
    MOD_ROLE_NAMES = ['Administrateur', 'Modérateur']
    USER_ROLE_NAMES = ['Joueur']
    EMBED_COLOR = 0x91b6f2  # Pastel blue

    PRIMARY_ROLES = [
        'Administrateur',
        'Modérateur',
        'Wargaming',
        'Contributeur',
        'Mentor',
        'Contact de clan',
        'Joueur',
        'Visiteur',
    ]

    def __init__(self, bot):
        super().__init__(bot)

    @commands.command(
        name='members',
        aliases=['membres', 'joueurs'],
        brief="Affiche le nombre de membres du serveur par rôle",
        help="Le total des membres du serveur est affiché, ainsi qu'un décompte détaillé pour chacun "
             "des rôles principaux.",
        ignore_extra=False,
    )
    @commands.check(checker.has_any_user_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def members(self, context: commands.Context):
        role_sizes = {}
        for primary_role_name in self.PRIMARY_ROLES:
            guild_role = utils.try_get(context.guild.roles, name=primary_role_name)
            role_sizes[primary_role_name] = len(guild_role.members)

        embed = discord.Embed(
            title=f"Décompte des membres du serveur",
            description=f"Total : **{len(context.guild.members)}** membres pour "
                        f"**{len(self.PRIMARY_ROLES)}** rôles principaux",
            color=self.EMBED_COLOR
        )
        for role_name in self.PRIMARY_ROLES:
            embed.add_field(
                name=role_name,
                value=f"**{role_sizes[role_name]}** membres",
                inline=True
            )
        embed.add_field(
            name="Banni",
            value=f"**{len(await context.guild.bans())}** boulets",
            inline=True
        )
        await context.send(embed=embed)


def setup(bot):
    bot.add_cog(Server(bot))
