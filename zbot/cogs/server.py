import datetime
import io
import math

import discord
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from discord.ext import commands
from discord.ext import tasks

from zbot import checker
from zbot import converter
from zbot import exceptions
from zbot import logger
from zbot import utils
from zbot import zbot
from . import _command


class Server(_command.Command):

    """Commands for information about the bot."""

    DISPLAY_NAME = "Informations sur le serveur"
    DISPLAY_SEQUENCE = 2
    MOD_ROLE_NAMES = ['Administrateur', 'Modérateur']
    USER_ROLE_NAMES = ['Joueur']
    EMBED_COLOR = 0x91b6f2  # Pastel blue

    MEMBER_COUNT_FREQUENCY = datetime.timedelta(hours=1)  # How often members are counted
    HOURS_GRANULARITY_LIMIT = 3  # In days, the maximum time-frame (excl.) to display records on a datetime axis
    DAYS_GRANULARITY_LIMIT = 365  # In days, the maximum time-frame (excl.) to display records on a day-to-day date axis
    MONTHS_GRANULARITY_LIMIT = 365*2  # In days, the maximum time-frame (excl.) to display records on a month axis

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
        self.record_member_count.start()

    @tasks.loop(seconds=MEMBER_COUNT_FREQUENCY.seconds)
    async def record_member_count(self):
        now = converter.get_tz_aware_datetime_now()
        last_member_count_date = zbot.db.get_metadata('last_member_count_date')
        if last_member_count_date:
            last_member_count_date_localized = converter.to_guild_tz(last_member_count_date)  # MongoDB uses UTC
            if last_member_count_date_localized >= now - self.MEMBER_COUNT_FREQUENCY:
                logger.debug(f"Prevented recording member count because running above define frequency.")
                return

        member_count = len(self.guild.members)
        zbot.db.insert_timed_member_count(member_count, now)
        zbot.db.update_metadata('last_member_count_date', now)

    @commands.command(
        name='members',
        aliases=['membres', 'joueurs'],
        brief="Affiche le nombre de membres du serveur par rôle",
        help="Le total des membres du serveur est affiché, ainsi qu'un décompte détaillé pour "
             "chacun des rôles principaux.",
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

    @commands.group(
        name='graph',
        aliases=['graphe', 'graphique', 'chart', 'plot'],
        brief="Gère la génération de graphiques sur le serveur",
        invoke_without_command=True
    )
    @commands.check(checker.has_any_user_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def graph(self, context):
        if context.invoked_subcommand is None:
            raise exceptions.MissingSubCommand(context.command.name)

    @graph.command(
        name='members',
        aliases=['membres', 'joueurs', 'total'],
        usage="[--time=days]",
        brief="Affiche le total des membres du serveur au cours du temps",
        help="Par défaut, une période de 30 jours est utilisée. Pour changer cela il faut fournir l'argument "
             "`--time=days` où `days` est le nombre de jours à considérer.",
        ignore_extra=True,
    )
    @commands.check(checker.has_any_user_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def graph_members(self, context, *, options=""):
        # Check arguments
        time_option = utils.get_option_value(options, 'time')
        if time_option is not None:  # Value assigned
            try:
                days_number = int(time_option)
            except ValueError:
                raise exceptions.MisformattedArgument(time_option, "valeur entière")
            if days_number < 1:
                raise exceptions.UndersizedArgument(days_number, 1)
            elif days_number > 1000:
                raise exceptions.OversizedArgument(days_number, 1000)
        elif utils.is_option_enabled(options, 'time', has_value=True):  # No value assigned
            raise exceptions.MisformattedArgument(time_option, "valeur entière")
        else:  # Option not used
            days_number = 30

        # Load, compute and reshape data
        today = converter.get_tz_aware_datetime_now()
        time_limit = today - datetime.timedelta(days=days_number)
        years_number = today.year - time_limit.year
        months_number = years_number * 12 + (today.month - time_limit.month)
        granularity = 'hour' if days_number < self.HOURS_GRANULARITY_LIMIT \
            else 'day' if days_number < self.DAYS_GRANULARITY_LIMIT \
            else 'month' if days_number < self.MONTHS_GRANULARITY_LIMIT \
            else 'year'
        member_counts_data = zbot.db.load_member_counts({'time': {'$gt': time_limit}}, ['count', 'time'])
        times, counts = [], []
        if granularity == 'hour':
            times = [data['time'] for data in member_counts_data]
            counts = [data['count'] for data in member_counts_data]
        elif granularity in ('day', 'month', 'year'):  # Only plot the date and the average value to align with the tick
            counts_by_time = {}
            for data in member_counts_data:
                counts_by_time.setdefault(data['time'].date(), []).append(data['count'])
            times = list(counts_by_time.keys())
            counts = [round(sum(time_counts) / len(time_counts)) for time_counts in counts_by_time.values()]

        # Plot the graph
        plt.clf()  # Clear the figure to remove any previous graph
        count_name = "Nombre de membres"
        if granularity == 'hour':
            plt.title(f"{count_name} sur les {days_number * 24} dernières heures")
        elif granularity == 'day':
            plt.title(f"{count_name} sur les {days_number} derniers jours")
        elif granularity == 'month':
            plt.title(f"{count_name} sur les {months_number} derniers mois")
        elif granularity == 'year':
            plt.title(f"{count_name} sur les {years_number} dernières années")
        plt.xlabel("Temps")
        plt.ylabel(count_name)
        plt.plot(times, counts, linestyle='-', marker='.', alpha=0.75)
        # Format time axis to comply with granularity
        plt.xlim(left=time_limit, right=today)
        if granularity == 'hour':
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %H:%M'))
            plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(nbins=5))
        elif granularity == 'day':
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
            plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(nbins=min(10, days_number)))
        elif granularity == 'month':
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%y'))
            plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(nbins=min(10, days_number)))
        elif granularity == 'year':
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%y'))
            plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(nbins=min(10, days_number)))
        # Format count axis to show integers only, on 5 to 10 ticks
        counts_range = max(counts) - min(counts) + 1
        if counts_range < 10:  # Force the positioning of counts in the middle of the range
            half_gap = (10 - counts_range) / 2
            plt.ylim(bottom=min(counts)-math.floor(half_gap), top=max(counts) + math.ceil(half_gap))
        plt.gca().yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _pos: str(int(y))))
        plt.gca().yaxis.set_major_locator(ticker.MaxNLocator(nbins=10))

        # Upload on Discord
        buffer = io.BytesIO()  # Instantiate I/O buffer
        plt.gcf().savefig(buffer, format='png')  # Plot the graph and save it in the buffer
        buffer.seek(0)  # Rewind the buffer to 0th byte
        await context.send(file=discord.File(buffer, 'graph.png'))


def setup(bot):
    bot.add_cog(Server(bot))
