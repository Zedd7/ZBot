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

    SERVER_STATS_RECORD_FREQUENCY = datetime.timedelta(hours=1)  # How often server stats are recorded
    HOURS_GRANULARITY_LIMIT = 3  # In days, the maximum time-frame (excl.) to display records on a datetime axis
    DAYS_GRANULARITY_LIMIT = 365  # In days, the maximum time-frame (excl.) to display records on a day-to-day date axis
    MONTHS_GRANULARITY_LIMIT = 365*2  # In days, the maximum time-frame (excl.) to display records on a month axis
    DISCUSSION_CHANNELS = [
        'général', 'gameplay', 'mentorat', 'actualités', 'promotion', 'recrutement', 'suggestions', 'memes']
    PRIMARY_ROLES = [
        'Administrateur', 'Modérateur', 'Wargaming', 'Contributeur', 'Mentor', 'Contact de clan', 'Joueur', 'Visiteur',
    ]

    def __init__(self, bot):
        super().__init__(bot)
        self.record_server_stats.start()

    @tasks.loop(seconds=SERVER_STATS_RECORD_FREQUENCY.seconds)
    async def record_server_stats(self):
        now = utils.bot_tz_now()
        last_server_stats_record_date = zbot.db.get_metadata('last_server_stats_record')
        if last_server_stats_record_date:
            last_server_stats_record_date_localized = converter.to_utc(last_server_stats_record_date)
            if not utils.is_time_almost_elapsed(
                last_server_stats_record_date_localized,
                now,
                self.SERVER_STATS_RECORD_FREQUENCY,
                tolerance=datetime.timedelta(minutes=5)
            ):
                logger.debug(f"Prevented recording server stats because running above define frequency.")
                return

        await self.record_member_count(now)
        await self.record_message_count(now)
        zbot.db.update_metadata('last_server_stats_record', now)

    async def record_member_count(self, time):
        zbot.db.insert_timed_member_count(time, self.guild.member_count)

    async def record_message_count(self, time):
        message_counts = []
        for channel_name in self.DISCUSSION_CHANNELS:
            channel = utils.try_get(self.guild.channels, name=channel_name)
            channel_message_count = len(await channel.history(
                after=converter.to_utc(time - datetime.timedelta(hours=1)).replace(tzinfo=None),
                limit=999
            ).flatten())
            message_counts.append({'count': channel_message_count, 'channel_id': channel.id})
        zbot.db.insert_timed_message_counts(time, message_counts)

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
        aliases=['membres'],
        usage="[--time=days] [--hour|--day|--month|--year]",
        brief="Affiche le total des membres du serveur au cours du temps",
        help="Par défaut, une période de 30 jours est utilisée. Pour changer cela il faut fournir l'argument "
             "`--time=days` où `days` est le nombre de jours à considérer. L'axe du temps est automatiquement ajusté "
             "au nombre de jours : Jusqu'à une période de 3 jours, 12 mois et 2 ans (exclus), l'axe affiche "
             "respectivement des heures, des jours et des mois. Pour forcer un type d'affichage, il faut fournir l'un "
             "des arguments suivants : `--hour`, `--day`, `--month`, `--year`. Il est également possible de scinder "
             "l'affichage par rôle en fournissant l'argument `--split`.",
        ignore_extra=True,
    )
    @commands.check(checker.has_any_user_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def graph_members(self, context, *, options=""):
        days_number, granularity = await self.parse_time_arguments(options)

        # Load, compute and reshape data
        today = utils.community_tz_now()
        time_limit = today - datetime.timedelta(days=days_number)
        member_counts_data = zbot.db.load_member_counts(
            {'time': {'$gt': converter.to_utc(time_limit)}}, ['time', 'count']
        )
        times, counts = [], []
        if granularity == 'hour':  # Plot the time and exact value to place the dot accurately
            for data in member_counts_data:
                localized_time = converter.to_community_tz(converter.to_utc(data['time'])).replace(tzinfo=None)
                times.append(localized_time)
                counts.append(data['count'])
        elif granularity in ('day', 'month', 'year'):  # Only plot the date and the average value to align with the tick
            counts_by_date = {}
            for data in member_counts_data:
                localized_time = converter.to_community_tz(converter.to_utc(data['time']))
                counts_by_date.setdefault(localized_time.date(), []).append(data['count'])
            times.extend(counts_by_date.keys())
            counts.extend([round(sum(date_counts) / len(date_counts)) for date_counts in counts_by_date.values()])

        plt.plot(times, counts, linestyle='-', marker='.', alpha=0.75)

        self.configure_plot(days_number, time_limit, today, min(counts), max(counts), "Nombre de membres", granularity)
        await context.send(file=self.render_graph())

    @graph.command(
        name='messages',
        aliases=['message'],
        usage="[--time=days] [--hour|--day|--month|--year] [--split]",
        brief="Affiche le nombre de messages postés lors de la dernière heure au cours du temps",
        help="Par défaut, une période de 3 jours est utilisée. Pour changer cela il faut fournir l'argument "
             "`--time=days` où `days` est le nombre de jours à considérer. L'axe du temps est automatiquement ajusté "
             "au nombre de jours : Jusqu'à une période de 3 jours, 12 mois et 2 ans (exclus), l'axe affiche "
             "respectivement des heures, des jours et des mois. Pour forcer un type d'affichage, il faut fournir l'un "
             "des arguments suivants : `--hour`, `--day`, `--month`, `--year`. Il est également possible de scinder "
             "l'affichage par canal en fournissant l'argument `--split`.",
        ignore_extra=True,
    )
    @commands.check(checker.has_any_user_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def graph_messages(self, context, *, options=""):
        days_number, granularity = await self.parse_time_arguments(options, default_days_number=2)
        do_split = utils.is_option_enabled(options, 'split')

        # Load, compute and reshape data
        today = utils.community_tz_now()
        time_limit = today - datetime.timedelta(days=days_number)
        message_counts_data = zbot.db.load_message_counts(
            {'time': {'$gt': converter.to_utc(time_limit)}}, ['time', 'count', 'channel_id']
        )
        times_by_channel, counts_by_channel = {}, {}
        if granularity == 'hour':  # Plot the time and exact value to place the dot accurately
            for data in message_counts_data:
                localized_time = converter.to_community_tz(converter.to_utc(data['time'])).replace(tzinfo=None)
                times_by_channel.setdefault(data['channel_id'], []).append(localized_time)
                counts_by_channel.setdefault(data['channel_id'], []).append(data['count'])
        elif granularity in ('day', 'month', 'year'):  # Only plot the date and the average value to align with the tick
            counts_by_channel_and_time = {}
            for data in message_counts_data:
                localized_time = converter.to_community_tz(converter.to_utc(data['time']))
                counts_by_channel_and_time.setdefault(data['channel_id'], {}) \
                    .setdefault(localized_time.date(), []).append(data['count'])
            for channel, counts_by_date in counts_by_channel_and_time.items():
                times_by_channel[channel] = list(counts_by_date.keys())
                counts_by_channel[channel] = [
                    round(sum(date_counts) / len(date_counts)) for date_counts in counts_by_date.values()
                ]

        min_count, max_count = float('inf'), -float('inf')
        if do_split:
            for channel_id, times, channel_counts in zip(
                    times_by_channel.keys(), times_by_channel.values(), counts_by_channel.values()
            ):
                channel_name = self.guild.get_channel(channel_id).name
                plt.plot(times, channel_counts, label=f"#{channel_name}", linestyle='-', marker='.', alpha=0.75)
                plt.legend()
                if min(channel_counts) < min_count:
                    min_count = min(channel_counts)
                if max(channel_counts) > max_count:
                    max_count = max(channel_counts)
        else:
            times = list(times_by_channel.values())[0]
            counts = [0] * len(times)
            for channel_counts in counts_by_channel.values():
                for time_index, channel_count in enumerate(channel_counts):
                    counts[time_index] += channel_count
            plt.plot(times, counts, linestyle='-', marker='.', alpha=0.75)
            min_count, max_count = min(counts), max(counts)

        self.configure_plot(
            days_number, time_limit, today, min_count, max_count, "Nombre de messages horaires", granularity
        )
        await context.send(file=self.render_graph())

    @staticmethod
    async def parse_time_arguments(options, default_days_number=30):
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
            days_number = default_days_number

        # Determine granularity
        granularity = None
        for granularity_option in ('hour', 'day', 'month', 'year'):
            if utils.is_option_enabled(options, granularity_option):
                granularity = granularity_option
                break
        if not granularity:
            granularity = 'hour' if days_number < Server.HOURS_GRANULARITY_LIMIT \
                else 'day' if days_number < Server.DAYS_GRANULARITY_LIMIT \
                else 'month' if days_number < Server.MONTHS_GRANULARITY_LIMIT \
                else 'year'
        return days_number, granularity

    @staticmethod
    def configure_plot(days_number, time_limit, today, min_count, max_count, count_name, granularity):
        # Set labels
        plt.xlabel("Temps")
        plt.ylabel(count_name)
        years_number = today.year - time_limit.year
        months_number = years_number * 12 + (today.month - time_limit.month)
        if granularity == 'hour':
            plt.title(f"{count_name} sur les {days_number * 24} dernières heures")
        elif granularity == 'day':
            plt.title(f"{count_name} sur les {days_number} derniers jours")
        elif granularity == 'month':
            plt.title(f"{count_name} sur les {months_number} derniers mois")
        elif granularity == 'year':
            plt.title(f"{count_name} sur les {years_number} dernières années")

        # Format time axis to comply with granularity
        if granularity == 'hour':
            plt.xlim(left=time_limit.replace(tzinfo=None), right=today.replace(tzinfo=None))  # Make tz agnostic
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %H:%M'))
            plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(nbins=5))
        else:
            plt.xlim(left=time_limit, right=today)
            if granularity == 'day':
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
                plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(nbins=min(10, days_number)))
            elif granularity == 'month':
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%y'))
                plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(nbins=min(10, days_number)))
            elif granularity == 'year':
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%y'))
                plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(nbins=min(10, days_number)))

        # Format count axis to show integers only, on 5 to 10 ticks
        counts_range = max_count - min_count + 1
        if counts_range < 10:  # Force the positioning of counts in the middle of the range
            half_gap = (10 - counts_range) / 2
            plt.ylim(bottom=min_count - math.floor(half_gap), top=max_count + math.ceil(half_gap))
        plt.gca().yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _pos: str(int(y))))
        plt.gca().yaxis.set_major_locator(ticker.MaxNLocator(nbins=10))

    @staticmethod
    def render_graph():
        buffer = io.BytesIO()  # Instantiate I/O buffer
        plt.gcf().savefig(buffer, format='png')  # Plot the graph and save it in the buffer
        plt.clf()  # Clear the figure to avoid it being drawn over by following graphes
        buffer.seek(0)  # Rewind the buffer to 0th byte
        return discord.File(buffer, 'graph.png')


def setup(bot):
    bot.add_cog(Server(bot))
