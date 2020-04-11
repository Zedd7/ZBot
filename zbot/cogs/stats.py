import datetime
import os
import pathlib
import re
import typing
from time import perf_counter

import discord
import dotenv
from discord.ext import commands

from zbot import checker
from zbot import converter
from zbot import exceptions
from zbot import utils
from zbot import wot_utils
from . import _command


class Stats(_command.Command):

    """Commands for display of players' statistics."""

    DISPLAY_NAME = "Profils et statistiques"
    DISPLAY_SEQUENCE = 2
    MOD_ROLE_NAMES = ['Administrateur']
    USER_ROLE_NAMES = ['Joueur']

    CLAN_CONTACT_ROLE_NAME = 'Contact de clan'
    EXP_VALUES_FILE_PATH = pathlib.Path('./res/wn8_exp_values.json')
    EXP_VALUES_FILE_URL = 'https://static.modxvm.com/wn8-data-exp/json/wn8exp.json'
    WN8_COLORS = {  # Following color chart of https://en.wot-life.com/
        0: 0x000000,        # black
        300: 0xE62929,      # red
        600: 0xEC8500,      # orange
        900: 0xF7D30F,      # yellow
        1250: 0x8BBB30,     # light green
        1600: 0x4B8423,     # dark green
        1900: 0x4A92B7,     # blue
        2350: 0x9C72B5,     # light purple
        2900: 0x5A3175,     # dark purple
    }

    def __init__(self, bot):
        super().__init__(bot)
        dotenv.load_dotenv()
        self.exp_values, self.tank_tiers = None, None
        bot.loop.create_task(self.load_required_data())

    async def load_required_data(self):
        self.exp_values = wot_utils.load_exp_values(
            self.EXP_VALUES_FILE_PATH, self.EXP_VALUES_FILE_URL
        )
        self.tank_tiers = wot_utils.load_tank_tiers(self.app_id)

    @commands.command(
        name='stats',
        aliases=['stat'],
        usage="[joueur]",
        brief="Affiche le résumé des statistiques d'un joueur",
        help="Les statistiques du joueur sont calculées à chaque appel. Elles seront donc toujours à jour mais "
             "nécessiteront quelques secondes pour s'afficher. La couleur de l'embed correspond à celle du WN8."
             "\n\nLe nom du joueur fourni en argument peut être :\n"
             "• Une mention d'un utilisateur Discord membre du serveur\n"
             "• Le nom d'utilisateur Discord d'un membre du serveur\n"
             "• Le surnom d'utilisateur Discord d'un membre du serveur\n"
             "• Le pseudo WoT de n'importe quel joueur du cluster EU\n"
             "Si aucun nom n'est fourni, le surnom du membre du serveur appellant la commande sera utilisé.",
        ignore_extra=False,
    )
    @commands.guild_only()
    @commands.check(checker.has_any_user_role)
    async def stats(self, context, player: typing.Union[discord.Member, str] = None):
        if not self.exp_values:
            self.exp_values = wot_utils.load_exp_values(
                Stats.EXP_VALUES_FILE_PATH, Stats.EXP_VALUES_FILE_URL
            )
        if not self.tank_tiers:
            self.tank_tiers = wot_utils.load_tank_tiers(self.app_id)
        compute_start = perf_counter()
        player, player_name = utils.parse_player(context.guild, player, context.author)
        player_name, player_id = wot_utils.get_exact_player_info(player_name, self.app_id)
        if not player_id:
            raise exceptions.UnknownPlayer(player_name)
        stats_totals = wot_utils.get_player_stats_totals(player_id, self.app_id)
        tank_stats, exp_stat_totals, missing_tanks = wot_utils.get_player_tank_stats(player_id, self.exp_values, self.app_id)
        adjusted_stats_totals = wot_utils.deduct_missing_tanks(player_id, stats_totals, missing_tanks, self.app_id)
        average_tier = wot_utils.compute_average_tier(tank_stats, self.tank_tiers)
        wn8 = wot_utils.compute_wn8(adjusted_stats_totals, exp_stat_totals)
        compute_end = perf_counter()
        elapsed_time = compute_end - compute_start

        player_details = {
            'name': player_name,
            'battles': stats_totals['battles'],
            'average_xp': stats_totals['average_xp'],
            'rating': stats_totals['rating'],
            'win_ratio': stats_totals['win_rate'] * 100,
            'average_tier': average_tier,
            'wn8': wn8,
        }
        await self.display_stats(context, player, player_details, elapsed_time)

    async def display_stats(
            self, context, player: typing.Union[discord.Member, str], player_details, elapsed_time
    ):
        embed_color = [color for wn8, color in sorted(self.WN8_COLORS.items()) if player_details['wn8'] >= wn8][-1]
        embed = discord.Embed(color=embed_color)
        embed.set_author(
            name=player_details['name'],
            url=f"https://fr.wot-life.com/eu/player/{player_details['name']}/",
            icon_url=player.avatar_url if isinstance(player, discord.Member) else ''
        )
        embed.add_field(name="Batailles", value=f"{player_details['battles']: .0f}")
        embed.add_field(name="Tier moyen", value=f"{player_details['average_tier']: .2f}")
        embed.add_field(name="Expérience moyenne", value=f"{player_details['average_xp']: .1f}")
        embed.add_field(name="Taux de victoires", value=f"{player_details['win_ratio']: .2f} %")
        embed.add_field(name="WN8", value=f"{player_details['wn8']: .0f}")
        embed.add_field(name="Cote personnelle", value=f"{player_details['rating']: .0f}")
        embed.set_footer(text=f"Calculé en {elapsed_time:.2f} sec")
        await context.send(embed=embed)

    @commands.command(
        name='profile',
        aliases=['profil'],
        usage="[joueur]",
        brief="Affiche le résumé du profil WoT d'un joueur",
        help="Le nom du joueur fourni en argument peut être :\n"
             "• Une mention d'un utilisateur Discord membre du serveur\n"
             "• Le nom d'utilisateur Discord d'un membre du serveur\n"
             "• Le surnom d'utilisateur Discord d'un membre du serveur\n"
             "• Le pseudo WoT de n'importe quel joueur du cluster EU\n"
             "Si aucun nom n'est fourni, le surnom du membre du serveur appellant la commande sera utilisé.",
        ignore_extra=False,
    )
    @commands.guild_only()
    @commands.check(checker.has_any_user_role)
    async def profile(self, context, player: typing.Union[discord.Member, str] = None):
        player, player_name = utils.parse_player(context.guild, player, context.author)
        player_name, player_id = wot_utils.get_exact_player_info(player_name, self.app_id)
        if not player_id:
            raise exceptions.UnknownPlayer(player_name)
        creation_timestamp, last_battle_timestamp, logout_timestamp, clan_id = \
            wot_utils.get_player_details(player_id, self.app_id)
        clan_member_infos = wot_utils.get_clan_member_infos(player_id, self.app_id)
        clan_infos = wot_utils.get_clan_infos(clan_id, self.app_id)

        player_details = {
            'name': player_name,
            'id': player_id,
            'creation_timestamp': creation_timestamp,
            'last_battle_timestamp': last_battle_timestamp,
            'logout_timestamp': logout_timestamp,
            'clan': False,
        }
        if clan_infos:
            player_details.update({
                'clan': True,
                'clan_id': clan_id,
                'clan_position': clan_member_infos['position'],
                'clan_name': clan_infos['name'],
                'clan_tag': clan_infos['tag'],
                'clan_emblem_url': clan_infos['emblem_url'],
            })
        await self.display_profile(context, player, player_details)

    async def display_profile(self, context, player: typing.Union[discord.Member, str], player_details):
        embed = discord.Embed(color=self.EMBED_COLOR)
        embed.set_author(
            name=player_details['name'] + (f" [{player_details['clan_tag']}]" if player_details['clan'] else ""),
            url=f"https://worldoftanks.eu/fr/community/accounts/{player_details['id']}/",
            icon_url=player.avatar_url if isinstance(player, discord.Member) else '')
        embed.add_field(name="Identifiant", value=player_details['id'])
        embed.add_field(
            name="Création du compte",
            value=converter.humanize_datetime(datetime.datetime.fromtimestamp(player_details['creation_timestamp']))
        )
        embed.add_field(
            name="Dernière bataille",
            value=converter.humanize_datetime(datetime.datetime.fromtimestamp(player_details['last_battle_timestamp']))
        )
        embed.add_field(
            name="Dernière connexion",
            value=converter.humanize_datetime(datetime.datetime.fromtimestamp(player_details['logout_timestamp']))
        )
        if player_details['clan']:
            embed.add_field(name="Clan", value=f"[{player_details['clan_name']}](https://eu.wargaming.net/clans/wot/{player_details['clan_id']}/)", inline=False)
            embed.add_field(name="Position", value=player_details['clan_position'], inline=False)
            embed.set_thumbnail(url=player_details['clan_emblem_url'])
        await context.send(embed=embed)

    @commands.command(
        name='clan',
        aliases=[],
        usage="[clan_tag|clan_name|player_name]",
        brief="Affiche le résumé de la présentation d'un clan WoT",
        help="La couleur de l'embed correspond à celle renseignée dans la description du clan sur le portail."
             "\n\nLes paramètres de recherche fournis en argument peuvent être :\n"
             "• Une mention d'un utilisateur Discord membre du serveur\n"
             "• Le nom d'utilisateur Discord d'un membre du serveur\n"
             "• Le surnom d'utilisateur Discord d'un membre du serveur\n"
             "• Le tag de n'importe quel clan WoT du cluster EU\n"
             "• Un extrait du nom (entre guillemets) de n'importe quel clan WoT du cluster EU\n"
             "Si aucun paramètre de recherche n'est fourni, le surnom du membre du serveur appellant la commande "
             "sera utilisé pour chercher le clan correspondant.",
        ignore_extra=False,
    )
    @commands.guild_only()
    @commands.check(checker.has_any_user_role)
    async def clan(self, context, clan_search_field: typing.Union[discord.Member, str] = None):
        clan_id = None
        if not clan_search_field or isinstance(clan_search_field, discord.Member):
            _, player_name = utils.parse_player(context.guild, clan_search_field, context.author)
            _, player_id = wot_utils.get_exact_player_info(player_name, self.app_id)
            if not player_id:
                raise exceptions.UnknownPlayer(player_name)
            _, _, _, clan_id = wot_utils.get_player_details(player_id, self.app_id)
            if not clan_id:
                raise exceptions.MissingClan(player_name)
        elif isinstance(clan_search_field, str):
            # Remove clan tag delimiters if any
            replacements = {(re.escape(char)): '' for char in ['[', ']', '(', ')']}
            pattern = re.compile('|'.join(replacements.keys()))
            clan_search_field = pattern.sub(lambda m: replacements[re.escape(m.group(0))], clan_search_field)
            clan_id = wot_utils.get_clan_id(clan_search_field, self.app_id)
            if not clan_id:
                raise exceptions.UnknownClan(clan_search_field)

        clan_infos = wot_utils.get_clan_infos(clan_id, self.app_id)
        clan_contact = wot_utils.get_clan_contact(clan_id, self.guild.members, self.CLAN_CONTACT_ROLE_NAME, self.app_id)

        clan_details = {'id': clan_id}
        clan_details.update(clan_infos)
        clan_details['contact'] = clan_contact
        await self.display_clan(context, clan_details)

    async def display_clan(self, context, clan_details):
        embed = discord.Embed(
            color=clan_details['color'] if clan_details['color'] else self.EMBED_COLOR
        )
        embed.set_author(
            name=f"[{clan_details['tag']}] {clan_details['name']}",
            url=f"https://eu.wargaming.net/clans/wot/{clan_details['id']}/",
            icon_url=clan_details['emblem_url'] if clan_details['emblem_url'] else None
        )
        embed.add_field(name="Identifiant", value=clan_details['id'])
        embed.add_field(
            name="Commandant",
            value=f"[{clan_details['leader_name']}](https://worldoftanks.eu/fr/community/accounts/{clan_details['leader_id']}/)"
        )
        embed.add_field(
            name="Création du clan",
            value=converter.humanize_datetime(datetime.datetime.fromtimestamp(clan_details['creation_timestamp']))
        )
        embed.add_field(name="Personnel", value=f"{clan_details['members_count']} membres")
        embed.add_field(name="Postulations", value="Autorisées" if clan_details['recruiting'] else "Refusées")
        embed.add_field(name="Contact de clan", value=clan_details['contact'].mention if clan_details['contact'] else "Aucun")
        embed.set_thumbnail(url=clan_details['emblem_url'])
        await context.send(embed=embed)


def setup(bot):
    bot.add_cog(Stats(bot))
