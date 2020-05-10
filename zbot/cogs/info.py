import discord
from discord.ext import commands

from zbot import checker
from zbot import exceptions
from zbot import utils
from zbot import zbot
from . import _command


class Info(_command.Command):

    """Commands for information about the bot."""

    DISPLAY_NAME = "Aide & Informations"
    DISPLAY_SEQUENCE = 1
    MOD_ROLE_NAMES = ['Administrateur', 'Modérateur']
    USER_ROLE_NAMES = ['Joueur']
    EMBED_COLOR = 0x91b6f2  # Pastel blue
    MAX_COMMAND_NEST_LEVEL = 1

    def __init__(self, bot):
        super().__init__(bot)

    @commands.command(
        name='help',
        aliases=['h'],
        usage="[command] [--nest=level]",
        brief="Affiche les commandes disponibles",
        help="Si aucune commande n'est fournie en argument, toutes les commandes existantes sont "
             "affichées. Si une commande de groupe est fournie en argument, les commandes du "
             "groupe sont affichées. Si une commande normale est fournie en argument, c'est cette "
             "fenêtre-ci qui est affichée. Par défaut, seules les commandes ou groupes de "
             "commandes du niveau suivant sont affichées. Pour changer cela, il faut fournir "
             "l'argument `--nest=level` où `level` est le nombre de niveaux à parcourir.",
        ignore_extra=False,
    )
    @commands.check(checker.is_allowed_in_current_channel)
    async def help(self, context, *, args: str = ""):
        max_nest_level = utils.get_option_value(args, 'nest')
        if max_nest_level:
            try:
                max_nest_level = int(max_nest_level)
            except ValueError:
                raise exceptions.MisformattedArgument(max_nest_level, "valeur entière")
        else:
            max_nest_level = Info.MAX_COMMAND_NEST_LEVEL
        full_command_name = utils.remove_option(args, 'nest')
        if not full_command_name:  # No command specified
            if max_nest_level < 1:
                raise exceptions.UndersizedArgument(max_nest_level, 1)
            await self.display_generic_help(context, max_nest_level)
        else:  # Request help commands matching the given pattern
            command_name = full_command_name.split(' ')[-1]
            command_chain = full_command_name.split(' ')[:-1]
            matching_commands = utils.get_commands(context, command_chain, command_name)
            if not matching_commands:
                raise exceptions.UnknownCommand(command_name)
            else:
                for command in matching_commands:
                    if isinstance(command, commands.Group):
                        await self.display_group_help(context, command, max_nest_level)
                    else:
                        await self.display_command_help(context, command)

    @staticmethod
    async def display_generic_help(context, max_nest_level):
        bot_display_name = await Info.get_bot_display_name(context.bot.user, context.guild)
        embed = discord.Embed(title=f"Commandes de @{bot_display_name}", color=Info.EMBED_COLOR)
        command_list = Info.get_command_list(context.bot, max_nest_level)
        commands_by_cog = {}
        for command in command_list:
            if not command.hidden or checker.has_any_mod_role(context, print_error=False):
                commands_by_cog.setdefault(command.cog, []).append(command)
        for cog in sorted(commands_by_cog, key=lambda c: c.DISPLAY_SEQUENCE):
            embed.add_field(
                name=cog.DISPLAY_NAME,
                value="\n".join([f"• `+{command}` : {command.brief}" for command in commands_by_cog[cog]]),
                inline=False
            )
        embed.set_footer(text="Utilisez +help <commande> pour plus d'informations")
        await context.send(embed=embed)

    @staticmethod
    async def display_group_help(context, group, max_nest_level):
        if group.hidden:
            checker.has_any_mod_role(context, print_error=True)

        command_list = Info.get_command_list(group, max_nest_level)
        authorized_command_list = list(filter(
            lambda c: not c.hidden or checker.has_any_mod_role(context, print_error=False),
            command_list
        ))
        embed = discord.Embed(
            title=group.cog.DISPLAY_NAME,
            description="\n".join([
                f"• `+{command}` : {command.brief}" for command in authorized_command_list
            ]),
            color=Info.EMBED_COLOR
        )
        await context.send(embed=embed)

    @staticmethod
    async def display_command_help(context, command):
        if command.hidden:
            checker.has_any_mod_role(context)

        parent = command.full_parent_name
        embed_description = f"**Description** : {command.brief}" if command.brief else ""
        embed_description += ("\n**Alias** : " +
                              ", ".join([f"`+{(parent + ' ') if parent else ''}{alias}`" for alias in command.aliases])
                              ) if command.aliases else ""
        if command.usage:
            embed_description += f"\n**Arguments** : `{command.usage}`"
            embed_description += "\n**Légende** : `<arg>` = obligatoire ; `[arg]` = facultatif ; " \
                                 "`\"arg\"` = argument devant être entouré de guillemets"
        embed_description += f"\n\n{command.help}" if command.help else ""
        embed = discord.Embed(title=f"Commande `+{command}`", description=embed_description, color=Info.EMBED_COLOR)
        await context.send(embed=embed)

    @staticmethod
    def get_command_list(command_container, max_nest_level, nest_level=0):
        """
        Recursively lists all existing (sub-)commands starting from a command container.
        :param command_container: The bot, a command group or a command
        :param max_nest_level: The maximum nesting level allowed
        :param nest_level: The current nesting level
        :return The list of commands starting from the container up to the maximum nesting level
        """
        if nest_level < max_nest_level and (
                isinstance(command_container, commands.core.Group)
                or isinstance(command_container, commands.Bot)
        ):  # commands.core.Command is a superclass of commands.core.Group, no need to test for it.
            command_list = []
            for command_group in command_container.commands:
                command_list += Info.get_command_list(command_group, max_nest_level, nest_level + 1)
            return command_list
        else:  # Max nesting level is reached or container is in fact a command.
            return [command_container]

    @commands.command(
        name='version',
        aliases=['v'],
        brief="Affiche la version du bot",
        help="La version affichée est celle du bot répondant à la commande. Il se peut que le bot en cours d'exécution "
             "soit en développement et que la version de celui-ci ne corresponde donc pas à celle du code source.",
        ignore_extra=False,
    )
    @commands.check(checker.is_allowed_in_current_channel)
    async def version(self, context):
        bot_display_name = await self.get_bot_display_name(self.user, self.guild)
        embed = discord.Embed(
            title=f"Version de @{bot_display_name}",
            description=f"**{zbot.__version__}**",
            color=self.EMBED_COLOR
        )
        await context.send(embed=embed)

    @commands.command(
        name='source',
        aliases=['src', 'git', 'github'],
        brief="Affiche un lien vers le code source du bot",
        help="L'entièreté du code source du bot, à l'exceptions des tokens d'authentification, est hébergé sur GitHub. "
             "Les droits d'utilisation du code source sont repris dans le fichier LICENSE.",
        ignore_extra=False,
    )
    @commands.check(checker.is_allowed_in_current_channel)
    async def source(self, context):
        bot_display_name = await self.get_bot_display_name(self.user, self.guild)
        embed = discord.Embed(
            title=f"Code source de @{bot_display_name}",
            description=f"https://github.com/Zedd7/ZBot",
            color=self.EMBED_COLOR
        )
        await context.send(embed=embed)

    @staticmethod
    async def get_bot_display_name(bot_user, guild):
        if guild:
            bot_user = guild.get_member(bot_user.id)
        return bot_user.display_name


def setup(bot):
    bot.add_cog(Info(bot))
