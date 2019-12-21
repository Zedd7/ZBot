import discord
from discord.ext import commands

from zbot import exceptions
from zbot import utils
from zbot import zbot
from . import command as bot_command


class Info(bot_command.Command):

    DISPLAY_NAME = "Aide & Informations"
    DISPLAY_SEQUENCE = 1
    MOD_ROLE_NAMES = ['Administrateur']
    USER_ROLE_NAMES = ['Joueur']

    def __init__(self, bot):
        super(Info, self).__init__(bot)

    @commands.command(
        name='help',
        aliases=['h'],
        usage="[command|category]",
        brief="Affiche les commandes disponibles",
        help="Si un groupe de commande est fourni en argument, les commandes du groupe sont affichées. "
             "Si une commande est fournie en argument, c'est cette fenêtre d'informations qui est affichée.",
        ignore_extra=False,
    )
    async def help(self, context, *, full_command_name: str = None):
        if not full_command_name:
            await self.display_generic_help(context)
        else:
            command_name = full_command_name.split(' ')[-1]
            command = utils.get_command(context, command_name)
            if not command:
                raise exceptions.UnknownCommand(command_name)
            elif isinstance(command, commands.Group):
                await self.display_group_help(context, command)
            else:
                await self.display_command_help(context, command)

    @staticmethod
    async def display_generic_help(context):
        bot_display_name = await Info.get_bot_display_name(context.bot.user, context)
        embed = discord.Embed(title=f"Commandes de @{bot_display_name}", color=Info.EMBED_COLOR)
        command_list = Info.get_command_list(context.bot)
        commands_by_cog = {}
        for command in command_list:
            commands_by_cog.setdefault(command.cog, []).append(command)
        for cog in sorted(commands_by_cog, key=lambda cog: cog.DISPLAY_SEQUENCE):
            embed.add_field(
                name=cog.DISPLAY_NAME,
                value="\n".join([f"• `+{command}` : {command.brief}" for command in commands_by_cog[cog]]),
                inline=False
            )
        embed.set_footer(text="Utilisez +help <commande> pour plus d'informations")
        await context.send(embed=embed)

    @staticmethod
    async def display_group_help(context, group):
        command_list = Info.get_command_list(group)
        embed = discord.Embed(
            title=group.cog.DISPLAY_NAME,
            description="\n".join([f"• `+{command}` : {command.brief}" for command in command_list]),
            color=Info.EMBED_COLOR
        )
        await context.send(embed=embed)

    @staticmethod
    async def display_command_help(context, command):
        parent = command.full_parent_name
        embed_description = f"Description : {command.brief}" if command.brief else ""
        embed_description += ("\nAlias : " +
                              ", ".join([f"`+{(parent + ' ') if parent else ''}{alias}`" for alias in command.aliases])
                              ) if command.aliases else ""
        if command.usage:
            embed_description += f"\nArguments : `{command.usage}`"
            embed_description += "\nLégende : `<arg>` = obligatoire ; `[arg]` = facultatif"
        embed_description += f"\n\n{command.help}" if command.help else ""
        embed = discord.Embed(title=f"Commande `+{command}`", description=embed_description, color=Info.EMBED_COLOR)
        await context.send(embed=embed)

    @staticmethod
    def get_command_list(command_container):
        if isinstance(command_container, commands.core.Group) or isinstance(command_container, commands.Bot):
            command_list = []
            for command_group in command_container.commands:
                command_list += Info.get_command_list(command_group)
            return command_list
        else:  # Do not test for commands.core.Command as it is a superclass of commands.core.Group
            return [command_container]

    @commands.command(
        name='version',
        aliases=['v'],
        brief="Affiche la version du bot",
        help="La version affichée est celle du bot répondant à la commande. Il se peut que le bot en cours d'exécution "
             "soit en développement et que la version de celui-ci ne corresponde donc pas à celle du code source.",
        ignore_extra=False,
    )
    async def version(self, context):
        bot_display_name = await self.get_bot_display_name(self.user, context)
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
    async def source(self, context):
        bot_display_name = await self.get_bot_display_name(self.user, context)
        embed = discord.Embed(
            title=f"Code source de @{bot_display_name}",
            description=f"https://github.com/Zedd7/ZBot",
            color=self.EMBED_COLOR
        )
        await context.send(embed=embed)

    @staticmethod
    async def get_bot_display_name(bot_user, context):
        if context.guild:
            bot_user = context.guild.get_member(bot_user.id)
        return bot_user.display_name


def setup(bot):
    bot.add_cog(Info(bot))
