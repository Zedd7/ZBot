import pathlib
import re
import sys

import discord
from discord.ext import commands

from .. import checker
from .. import exceptions
from .. import logger
from .. import utils
from .. import zbot
from .. import converter
from . import _command


class Bot(_command.Command):

    """Commands for information about the bot."""

    DISPLAY_NAME = "Informations sur le bot"
    DISPLAY_SEQUENCE = 1
    MOD_ROLE_NAMES = ['Administrateur', 'Modérateur']
    USER_ROLE_NAMES = ['Joueur']
    EMBED_COLOR = 0x91b6f2  # Pastel blue

    DEFAULT_HELP_NEST_LEVEL = 1
    CHANGELOG_FILE_PATH = pathlib.Path('changelog.md')

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
    @commands.check(checker.has_no_role_requirement)
    @commands.check(checker.is_allowed_in_private_or_current_guild_channel)
    async def help(self, context, *, args: str = ""):
        max_nest_level = utils.get_option_value(args, 'nest')
        if max_nest_level:
            try:
                max_nest_level = int(max_nest_level)
            except ValueError:
                raise exceptions.MisformattedArgument(max_nest_level, "valeur entière")
        else:
            max_nest_level = self.DEFAULT_HELP_NEST_LEVEL
        full_command_name = utils.remove_option(args, 'nest')

        if not full_command_name:  # No command specified
            if max_nest_level < 1:
                raise exceptions.UndersizedArgument(max_nest_level, 1)
            await self.display_generic_help(context, max_nest_level)
        else:  # Request help for commands matching the given pattern
            command_name = full_command_name.split(' ')[-1]
            command_chain = full_command_name.split(' ')[:-1]
            matching_commands = utils.get_commands(context, command_chain, command_name)
            if not matching_commands:
                raise exceptions.UnknownCommand(command_name)
            else:
                # Don't show the helper of all matching commands if one matches exactly
                if exactly_matching_commands := set(filter(
                    lambda c: c.qualified_name == full_command_name, matching_commands
                )):
                    matching_commands = exactly_matching_commands

                # Don't show an error for missing permissions if there is at least one public command
                public_commands = list(filter(lambda c: not c.hidden, matching_commands))
                if len(public_commands) < len(matching_commands):  # At least one command is hidden
                    try:  # Don't print the error right away
                        checker.has_any_mod_role(context)
                    except exceptions.MissingRoles as error:
                        if not public_commands:  # All commands requires permissions
                            raise error  # Print the error
                        else:  # At least one command is public
                            matching_commands = public_commands  # Filter out hidden commands

                # Show the helper of matching commands
                sorted_matching_commands = sorted(matching_commands, key=lambda c: c.qualified_name)
                for command in sorted_matching_commands:
                    if isinstance(command, commands.Group):
                        await self.display_group_help(context, command, max_nest_level)
                    else:
                        await self.display_command_help(context, command)

    @staticmethod
    async def display_generic_help(context, max_nest_level):
        bot_display_name = Bot.get_bot_display_name(context.bot.user, context.guild)
        embed = discord.Embed(title=f"Commandes de @{bot_display_name}", color=Bot.EMBED_COLOR)
        commands_by_cog = {}
        for command in Bot.get_command_list(context.bot, max_nest_level):
            if not command.hidden or checker.has_any_mod_role(context, print_error=False):
                commands_by_cog.setdefault(command.cog, []).append(command)
        for cog in sorted(commands_by_cog, key=lambda c: c.DISPLAY_SEQUENCE):
            sorted_cog_commands = sorted(commands_by_cog[cog], key=lambda c: c.qualified_name)
            embed.add_field(
                name=cog.DISPLAY_NAME,
                value="\n".join([f"• `+{command}` : {command.brief}" for command in sorted_cog_commands]),
                inline=False
            )
        embed.set_footer(text="Utilisez +help <commande> pour plus d'informations")
        await context.send(embed=embed)

    @staticmethod
    async def display_group_help(context, group, max_nest_level=DEFAULT_HELP_NEST_LEVEL):
        # Fetch visible subcommands
        command_list = Bot.get_command_list(group, max_nest_level)
        authorized_command_list = list(filter(
            lambda c: not c.hidden or checker.has_any_mod_role(context, print_error=False),
            command_list
        ))
        sorted_group_commands = sorted(authorized_command_list, key=lambda c: c.qualified_name)

        # Compute generic command header
        parent = group.full_parent_name
        embed_description = f"**Description** : {group.brief}" if group.brief else ""
        embed_description += (
            "\n**Alias** : " + ", ".join(
                [f"`+{(parent + ' ') if parent else ''}{alias}`" for alias in group.aliases]
            )) if group.aliases else ""

        # Append group helper
        embed_description += "\n\n" + "\n".join(
            [f"• `+{command}` : {command.brief}" for command in sorted_group_commands]
        )
        embed = discord.Embed(
            title=f"Commande `+{group}`", description=embed_description, color=Bot.EMBED_COLOR
        )
        await context.send(embed=embed)

    @staticmethod
    async def display_command_help(context, command):
        # Compute generic command header
        bot_user = context.bot.user
        parent = command.full_parent_name
        prefix = f"@{bot_user.name}#{bot_user.discriminator} " if '@' in context.prefix else context.prefix
        embed_description = f"**Description** : {command.brief}" if command.brief else ""
        embed_description += (
            "\n**Alias** : " + ", ".join(
                [f"`{prefix}{(parent + ' ') if parent else ''}{alias}`" for alias in command.aliases]
            )) if command.aliases else ""

        # Append command helper
        if command.usage:
            embed_description += f"\n**Arguments** : `{command.usage}`"
            embed_description += "\n**Légende** : `<arg>` = obligatoire ; `[arg]` = facultatif ; " \
                                 "`\"arg\"` = argument devant être entouré de guillemets"
        embed_description += "\n\n" + command.help if command.help else ""
        embed = discord.Embed(
            title=f"Commande `{prefix}{command}`", description=embed_description, color=Bot.EMBED_COLOR
        )
        await context.send(embed=embed)

    @staticmethod
    async def display_command_usage(context, command_name) -> None:
        command = context.command
        if not command:
            raise exceptions.UnknownCommand(command_name)
        bot_user = context.bot.user
        prefix = f"@{bot_user.name}#{bot_user.discriminator} " if '@' in context.prefix else context.prefix
        await context.send(
            f"Syntaxe : `{prefix}{command.qualified_name}{f' {command.usage}' if command.usage else ''}`"
        )
        await context.send(f"Aide : `{prefix}help {command.qualified_name}`")

    @staticmethod
    def get_command_list(command_container, max_nest_level, nest_level=0):
        """
        Recursively lists all existing (sub-)commands starting from a command container.
        :param command_container: The bot, a command group or a command
        :param max_nest_level: The maximum nesting level allowed
        :param nest_level: The current nesting level
        :return The list of commands starting from the container up to the maximum nesting level
        """
        if nest_level < max_nest_level and (isinstance(command_container, (commands.core.Group, commands.Bot))):
            # commands.core.Command is a superclass of commands.core.Group, no need to test for it
            command_list = []
            for command_group in command_container.commands:
                command_list += Bot.get_command_list(command_group, max_nest_level, nest_level + 1)
            return command_list
        else:  # Max nesting level is reached or container is in fact a command.
            return [command_container]

    @commands.command(
        name='version',
        aliases=['v'],
        usage='[--all]',
        brief="Affiche la version du bot",
        help="La version affichée est celle du bot répondant à la commande. Il se peut que le bot en cours d'exécution "
             "soit en développement et que la version de celui-ci ne corresponde donc pas à celle du code source. Par "
             "défaut, seule la dernière version est affichée. Pour afficher la liste de toutes les versions, il faut "
             "fournir l'argument `--all`.",
        ignore_extra=True,
    )
    @commands.check(checker.has_no_role_requirement)
    @commands.check(checker.is_allowed_in_private_or_current_guild_channel)
    async def version(self, context, *, options=''):
        bot_display_name = self.get_bot_display_name(self.user, self.guild)
        if not utils.is_option_enabled(options, 'all'):  # Display current version
            current_version = zbot.__version__
            embed = discord.Embed(title=f"Version actuelle de @{bot_display_name}", color=self.EMBED_COLOR)
            embed.add_field(name="Numéro", value=f"**{current_version}**")
            if changelog := self.get_changelog(current_version):
                date_iso, description, _ = changelog
                embed.add_field(name="Date", value=converter.to_human_format(converter.to_datetime(date_iso)))
                embed.add_field(name="Description", value=description, inline=False)
            embed.set_footer(text="Utilisez +changelog <version> pour plus d'informations")
            await context.send(embed=embed)
        else:  # Display all versions
            versions_data = self.get_versions_data()
            for block in utils.make_message_blocks([
                f"v**{version}** - {converter.to_human_format(versions_data[version]['date'])}\n"
                f"> {versions_data[version]['description']}" for version in sorted(versions_data, reverse=True)
            ]):
                await context.send(block)

    @commands.command(
        name='changelog',
        aliases=['patchnote'],
        usage="[version]",
        brief="Affiche les changements d'une version du bot",
        help="Si aucune version n'est spécifiée (au format `a.b.c` avec `a`, `b` et `c` des valeurs entières), la "
             "version courante est utilisée. Les changements affichées ne concernent que les améliorations "
             "fonctionnelles et les corrections de bug.",
        ignore_extra=False,
    )
    @commands.check(checker.has_no_role_requirement)
    @commands.check(checker.is_allowed_in_private_or_current_guild_channel)
    async def changelog(self, context, version: str = None):
        current_version = zbot.__version__
        if not version:
            version = current_version
        else:
            result = re.match(r'(\d+)\.(\d+)\.(\d+)', version)
            if not result:
                raise exceptions.MisformattedArgument(version, 'a.b.c (a, b et c valeurs entières)')
            major, minor, patch = (int(value) for value in result.groups())  # Cast as int to remove leading zeros
            if self.is_out_of_version_range(major, minor, patch):
                raise exceptions.OversizedArgument(version, current_version)
            version = '.'.join(str(value) for value in (major, minor, patch))

        changelog = self.get_changelog(version)
        bot_display_name = self.get_bot_display_name(self.user, self.guild)
        if not changelog:
            await context.send(f"Aucune note de version trouvée pour @{bot_display_name} v{version}")
        else:  # This is only executed if there is a match and if both the date and changes are present
            date_iso, description, raw_changes = changelog
            changes = [raw_change.removeprefix('- ') for raw_change in raw_changes.split('\n') if raw_change]
            embed = discord.Embed(
                title=f"Notes de version de @{bot_display_name} v{version}",
                description="",
                color=self.EMBED_COLOR
            )
            embed.add_field(name="Date", value=converter.to_human_format(converter.to_datetime(date_iso)), inline=False)
            description and embed.add_field(name="Description", value=description, inline=False)
            embed.add_field(name="Changements", value='\n'.join([f"• {change}" for change in changes]), inline=False)
            await context.send(embed=embed)

    @staticmethod
    def get_versions_data():
        versions_data = {}
        major, minor, patch = 1, 0, 0
        while not Bot.is_out_of_version_range(major, minor, patch):
            version = '.'.join(str(value) for value in (major, minor, patch))
            if changelog := Bot.get_changelog(version):
                date_iso, description, _ = changelog
                versions_data[version] = {'date': converter.to_datetime(date_iso), 'description': description}
                patch += 1
            elif patch > 0:
                minor += 1
                patch = 0
            else:
                major += 1
                minor = 0
                patch = 0
        return versions_data

    @staticmethod
    def is_out_of_version_range(major, minor, patch):
        current_version = zbot.__version__
        current_major, current_minor, current_patch = (int(value) for value in current_version.split('.'))
        return major > current_major \
            or (major == current_major and minor > current_minor) \
            or (major == current_major and minor == current_minor and patch > current_patch)

    @staticmethod
    def get_changelog(version: str):
        changelog = None
        if not Bot.CHANGELOG_FILE_PATH.exists():
            logger.warning(f"Could not find changelog file at {Bot.CHANGELOG_FILE_PATH.name}")
        else:
            with Bot.CHANGELOG_FILE_PATH.open(mode='r') as f:
                file_content = f.read()
                result = re.search(
                    '## ' + re.escape(version) + r' - (\d{4}-\d{2}-\d{2})'  # Date in ISO format
                                                 r'(?: - (.+))'  # One-liner description
                                                 r'\n((?:- .+\n)+)',  # Multi-line changes
                    file_content
                )
                changelog = result and result.groups()
        return changelog

    @commands.command(
        name='source',
        aliases=['src', 'git', 'github'],
        brief="Affiche un lien vers le code source du bot",
        help="L'entièreté du code source du bot, à l'exceptions des tokens d'authentification, est hébergé sur GitHub. "
             "Les droits d'utilisation du code source sont repris dans le fichier LICENSE.",
        ignore_extra=False,
    )
    @commands.check(checker.has_no_role_requirement)
    @commands.check(checker.is_allowed_in_private_or_current_guild_channel)
    async def source(self, context):
        bot_display_name = self.get_bot_display_name(self.user, self.guild)
        embed = discord.Embed(
            title=f"Code source de @{bot_display_name}",
            description=f"https://github.com/Zedd7/ZBot",
            color=self.EMBED_COLOR
        )
        await context.send(embed=embed)

    @commands.group(
        name='work',
        brief="Gère les notifications de travaux sur le bot",
        invoke_without_command=True
    )
    @commands.check(checker.has_any_user_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def work(self, context):
        if not context.subcommand_passed:
            await Bot.display_group_help(context, context.command)
        else:
            raise exceptions.MissingSubCommand(context.command.name)

    @work.command(
        name='start',
        aliases=['begin'],
        brief="Annonce le début des travaux sur le bot",
        help="L'annonce est postée dans le canal courant, la commande est supprimée et le status "
             "est défini sur travaux en cours.",
        hidden=True,
        ignore_extra=True
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def work_start(self, context):
        self.db.update_metadata('work_in_progress', True)
        await context.message.delete()
        await context.send(
            f"**Début des travaux sur le bot {self.user.mention}** :man_factory_worker:"
        )

    @work.command(
        name='done',
        brief="Annonce la fin des travaux sur le bot",
        help="L'annonce est postée dans le canal courant, la commande est supprimée et le status "
             "est défini sur travaux terminés.",
        hidden=True,
        ignore_extra=True
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def work_done(self, context):
        self.db.update_metadata('work_in_progress', False)
        await context.message.delete()
        await context.send(
            f"**Fin des travaux sur le bot {self.user.mention}** :mechanical_arm:"
        )

    @work.command(
        name='status',
        aliases=['statut'],
        brief="Affiche l'état des travaux sur le bot",
        help="Le résultat est posté dans le canal courant.",
        ignore_extra=True
    )
    @commands.check(checker.has_any_user_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def work_status(self, context):
        work_in_progress = self.db.get_metadata('work_in_progress') or False  # Might not be set
        if work_in_progress:
            await context.send(
                f"**Les travaux sur le bot {self.user.mention} sont toujours en cours** :tools:"
            )
        else:
            await context.send(
                f"**Les travaux sur le bot {self.user.mention} sont terminés** :ok_hand:"
            )

    @commands.command(
        name='logout',
        aliases=['stop', 'disconnect'],
        brief="Déconnecte le bot",
        help="Déconnecte le bot du serveur sans arrêter le processus.",
        hidden=True,
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_all_channels)
    async def logout(self, context):
        logger.info("Logging out...")
        await context.send(f"Déconnexion.")
        await self.bot.close()
        sys.exit()

    @staticmethod
    def get_bot_display_name(bot_user, guild):
        if guild:
            bot_user = guild.get_member(bot_user.id)
        return bot_user.display_name


async def setup(bot):
    await bot.add_cog(Bot(bot))
