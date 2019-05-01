# -*- coding: utf-8 -*-

import datetime
import os
import typing
from pathlib import Path

import discord
import dotenv
import requests
from discord.ext import commands

from zbot import checks
from zbot import converters
from zbot import exceptions
from zbot import utils
from . import command


class Stats(command.Command):

    MOD_ROLE_NAMES = ['Administrateur']
    USER_ROLE_NAMES = ['Joueur']
    EXP_VALUES_FILE_PATH = Path('./res/wn8_exp_values.json')
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
        super(Stats, self).__init__(bot)
        dotenv.load_dotenv()
        self.app_id = os.getenv('WG_API_APPLICATION_ID') or 'demo'
        self.exp_values = utils.get_exp_values(Stats.EXP_VALUES_FILE_PATH, Stats.EXP_VALUES_FILE_URL)

    @commands.command(
        name='stats',
        aliases=['stat'],
        usage="<joueur>",
        ignore_extra=False,
    )
    @commands.guild_only()
    @commands.check(checks.has_any_user_role)
    async def stats(self, context, player: typing.Union[discord.Member, str] = None):
        player, player_name = await utils.parse_player(context, player)
        player_id, player_name = await Stats.get_player_id(player_name, self.app_id)
        if not player_id:
            raise exceptions.UnknowPlayer(player_name)
        stats_totals = await Stats.get_player_stats_totals(player_id, self.app_id)
        tank_stats, exp_stat_totals, missing_tanks = await Stats.get_player_tank_stats(player_id, self.exp_values, self.app_id)
        adjusted_stats_totals = await Stats.deduct_missing_tanks(player_id, stats_totals, missing_tanks, self.app_id)
        average_tier = await Stats.compute_average_tier(tank_stats, self.app_id)
        wn8 = await Stats.compute_wn8(adjusted_stats_totals, exp_stat_totals)

        player_details = {
            'player_name': player_name,
            'battles': stats_totals['battles'],
            'average_xp': stats_totals['average_xp'],
            'rating': stats_totals['rating'],
            'win_ratio': (stats_totals['wins'] / stats_totals['battles']) * 100,
            'average_tier': average_tier,
            'wn8': wn8,
        }
        await self.display_stats(context, player, player_details)

    async def display_stats(self, context, player: typing.Union[discord.Member, str], player_details):
        embed_color = [color for wn8, color in sorted(self.WN8_COLORS.items()) if player_details['wn8'] >= wn8][-1]
        embed = discord.Embed(color=embed_color)
        embed.set_author(
            name=player_details['player_name'],
            url=f"https://fr.wot-life.com/eu/player/{player_details['player_name']}/",
            icon_url=player.avatar_url if isinstance(player, discord.Member) else ''
        )
        embed.add_field(name="Batailles", value=f"{player_details['battles']: .0f}", inline=True)
        embed.add_field(name="Tier moyen", value=f"{player_details['average_tier']: .2f}", inline=True)
        embed.add_field(name="Expérience moyenne", value=f"{player_details['average_xp']: .1f}", inline=True)
        embed.add_field(name="Taux de victoires", value=f"{player_details['win_ratio']: .2f} %", inline=True)
        embed.add_field(name="WN8", value=f"{player_details['wn8']: .0f}", inline=True)
        embed.add_field(name="Cote personnelle", value=f"{player_details['rating']: .0f}", inline=True)
        await context.send(embed=embed)

    @staticmethod
    async def get_player_id(player_name, app_id) -> (str, str) or (None, None):
        """Retrieve account id and nickname of player."""
        payload = {
            'application_id': app_id,
            'search': player_name,
            'type': 'exact',
        }
        response = requests.get('https://api.worldoftanks.eu/wot/account/list/', params=payload)
        response_content = response.json()

        player_id, player_name = (None,) * 2
        if response_content['status'] == 'ok':
            player_data = response_content['data']
            if player_data:
                player_id = str(player_data[0]['account_id'])
                player_name = player_data[0]['nickname']  # Fix player name case
        return player_id, player_name

    @staticmethod
    async def get_player_stats_totals(player_id, app_id) -> dict or None:
        """Retrieve the stats totals of a player."""
        payload = {
            'application_id': app_id,
            'account_id': player_id,
            'fields': ','.join([
                'global_rating',
                'statistics.all.battles',
                'statistics.all.battle_avg_xp',
                'statistics.all.damage_dealt',
                'statistics.all.spotted',
                'statistics.all.frags',
                'statistics.all.dropped_capture_points',
                'statistics.all.wins',
            ]),
        }
        response = requests.get('https://api.worldoftanks.eu/wot/account/info/', params=payload)
        response_content = response.json()

        if response_content['status'] == 'ok':
            player_data = response_content['data'][player_id]
            if player_data:
                stats_totals = {
                    'rating': player_data['global_rating'],
                    'battles': player_data['statistics']['all']['battles'],
                    'average_xp': player_data['statistics']['all']['battle_avg_xp'],
                    'dmgs': player_data['statistics']['all']['damage_dealt'],
                    'spots': player_data['statistics']['all']['spotted'],
                    'kills': player_data['statistics']['all']['frags'],
                    'defs': player_data['statistics']['all']['dropped_capture_points'],
                    'wins': player_data['statistics']['all']['wins'],
                }
                return stats_totals

    @staticmethod
    async def get_player_tank_stats(player_id, exp_values, app_id) -> (dict, dict, list) or (None,) * 3:
        """Retrieve the tank specific stats and expected stats totals of a player."""
        payload = {
            'application_id': app_id,
            'account_id': player_id,
            'fields': ','.join([
                'tank_id',
                'statistics.battles',
            ]),
        }
        response = requests.get('https://api.worldoftanks.eu/wot/account/tanks/', params=payload)
        response_content = response.json()

        if response_content['status'] == 'ok':
            tank_stats, exp_stats_totals, missing_tanks = {}, {}, []
            player_data = response_content['data'][player_id]
            if player_data:
                exp_stats_totals = {'dmgs': 0, 'spots': 0, 'kills': 0, 'defs': 0, 'wins': 0}
                for tank_data in player_data:
                    tank_id = tank_data['tank_id']
                    battles = tank_data['statistics']['battles']
                    tank_stats[str(tank_id)] = {'battles': battles}
                    if tank_id in exp_values:
                        tank_exp_values = exp_values[tank_id]
                        exp_stats_totals['dmgs'] += tank_exp_values['damage_ratio'] * battles
                        exp_stats_totals['spots'] += tank_exp_values['spot_ratio'] * battles
                        exp_stats_totals['kills'] += tank_exp_values['kill_ratio'] * battles
                        exp_stats_totals['defs'] += tank_exp_values['defense_ratio'] * battles
                        exp_stats_totals['wins'] += (tank_exp_values['win_ratio'] / 100) * battles
                    else:
                        missing_tanks.append(str(tank_id))
            return tank_stats, exp_stats_totals, missing_tanks

    @staticmethod
    async def deduct_missing_tanks(player_id, stats_totals, missing_tanks, app_id) -> dict or None:
        """Adjust player stats totals with stats of missing tanks."""
        if missing_tanks and stats_totals:
            adjusted_stats_totals = dict(stats_totals)
            payload = {
                'application_id': app_id,
                'account_id': player_id,
                'fields': ','.join([
                    'all.damage_dealt',
                    'all.spotted',
                    'all.frags',
                    'all.dropped_capture_points',
                    'all.wins',
                ]),
                'tank_id': ','.join(missing_tanks),
            }
            response = requests.get('https://api.worldoftanks.eu/wot/tanks/stats/', params=payload)
            response_content = response.json()

            if response_content['status'] == 'ok':
                player_data = response_content['data'][player_id]
                if player_data:
                    for tank_stats in player_data:
                        adjusted_stats_totals['dmgs'] -= tank_stats['all']['damage_dealt']
                        adjusted_stats_totals['spots'] -= tank_stats['all']['spotted']
                        adjusted_stats_totals['kills'] -= tank_stats['all']['frags']
                        adjusted_stats_totals['defs'] -= tank_stats['all']['dropped_capture_points']
                        adjusted_stats_totals['wins'] -= tank_stats['all']['wins']
            return adjusted_stats_totals
        return stats_totals

    @staticmethod
    async def compute_average_tier(tank_stats, app_id) -> float:
        """Compute the average tier of a player."""
        if tank_stats:
            payload = {
                'application_id': app_id,
                'fields': ','.join(['tier']),
            }
            response = requests.get('https://api.worldoftanks.eu/wot/encyclopedia/vehicles/', params=payload)
            response_content = response.json()

            if response_content['status'] == 'ok':
                tank_data = response_content['data']
                if tank_data:
                    total_battles, weighted_sum = 0, 0
                    for tank_id in tank_stats:
                        if tank_id in tank_data:
                            tier = tank_data[tank_id]['tier']
                            battles = tank_stats[tank_id]['battles']
                            total_battles += battles
                            weighted_sum += tier * battles
                    average_tier = weighted_sum / total_battles
                    return average_tier
        return 0

    @staticmethod
    async def compute_wn8(stats_totals, exp_stat_totals) -> float:
        """Compute the WN8 of a player."""
        wn8 = 0
        if stats_totals and exp_stat_totals:
            stat_keys = ('dmgs', 'spots', 'kills', 'defs', 'wins')
            dmgs, spots, kills, defs, wins = (stats_totals[stat] for stat in stat_keys)
            exp_dmgs, exp_spots, exp_kills, exp_defs, exp_wins = (exp_stat_totals[stat] for stat in stat_keys)

            r_dmg = dmgs / exp_dmgs if exp_dmgs > 0 else 0
            r_spot = spots / exp_spots if exp_spots > 0 else 0
            r_kill = kills / exp_kills if exp_kills > 0 else 0
            r_def = defs / exp_defs if exp_defs > 0 else 0
            r_win = wins / exp_wins if exp_wins > 0 else 0

            r_dmg_c = max(0., (r_dmg - 0.22) / 0.78)
            r_spot_c = max(0., min(r_dmg_c + 0.1, (r_spot - 0.38) / 0.62))
            r_kill_c = max(0., min(r_dmg_c + 0.2, (r_kill - 0.12) / 0.88))
            r_def_c = max(0., min(r_dmg_c + 0.1, (r_def - 0.10) / 0.90))
            r_win_c = max(0., (r_win - 0.71) / 0.29)

            wn8 += 980 * r_dmg_c
            wn8 += 210 * r_dmg_c * r_kill_c
            wn8 += 155 * r_kill_c * r_spot_c
            wn8 += 75 * r_def_c * r_kill_c
            wn8 += 145 * min(1.8, r_win_c)
        return wn8

    @commands.command(
        name='profile',
        aliases=['profil'],
        usage="<joueur>",
        ignore_extra=False,
    )
    @commands.guild_only()
    @commands.check(checks.has_any_user_role)
    async def profile(self, context, player: typing.Union[discord.Member, str] = None):
        player, player_name = await utils.parse_player(context, player)
        player_id, player_name = await Stats.get_player_id(player_name, self.app_id)
        if not player_id:
            raise exceptions.UnknowPlayer(player_name)
        creation_timestamp, last_battle_timestamp, logout_timestamp, clan_id = await Stats.get_player_info(player_id, self.app_id)
        clan_position = await Stats.get_clan_member_infos(player_id, self.app_id)
        clan_infos = await Stats.get_clan_infos(clan_id, self.app_id)

        player_details = {
            'player_name': player_name,
            'player_id': player_id,
            'creation_timestamp': creation_timestamp,
            'last_battle_timestamp': last_battle_timestamp,
            'logout_timestamp': logout_timestamp,
            'clan': False,
        }
        if clan_infos:
            player_details.update({
                'clan': True,
                'clan_id': clan_id,
                'clan_position': clan_position,
                'clan_name': clan_infos['name'],
                'clan_tag': clan_infos['tag'],
                'clan_emblem_url': clan_infos['emblem_url'],
            })
        await self.display_profile(context, player, player_details)

    async def display_profile(self, context, player: typing.Union[discord.Member, str], player_details):
        clan_tag = ""
        embed = discord.Embed()
        embed.set_author(
            name=player_details['player_name'] + (f" [{player_details['clan_tag']}]" if player_details['clan'] else ""),
            url=f"https://worldoftanks.eu/fr/community/accounts/{player_details['player_id']}/",
            icon_url=player.avatar_url if isinstance(player, discord.Member) else '')
        embed.add_field(name="Identifiant", value=player_details['player_id'])
        embed.add_field(
            name="Création du compte",
            value=converters.humanize_datetime(datetime.datetime.fromtimestamp(player_details['creation_timestamp']))
        )
        embed.add_field(
            name="Dernière bataille",
            value=converters.humanize_datetime(datetime.datetime.fromtimestamp(player_details['last_battle_timestamp']))
        )
        embed.add_field(
            name="Dernière connexion",
            value=converters.humanize_datetime(datetime.datetime.fromtimestamp(player_details['logout_timestamp']))
        )
        if player_details['clan']:
            embed.add_field(name="Clan", value=f"[{player_details['clan_name']}](https://eu.wargaming.net/clans/wot/{player_details['clan_id']}/)", inline=False)
            embed.add_field(name="Position", value=player_details['clan_position'], inline=False)
            embed.set_thumbnail(url=player_details['clan_emblem_url'])
        await context.send(embed=embed)

    @staticmethod
    async def get_player_info(player_id, app_id) -> (int, int, int, str) or None:
        """Retrieve the stats totals of a player."""
        payload = {
            'application_id': app_id,
            'account_id': player_id,
            'fields': ','.join([
                'created_at',
                'last_battle_time',
                'logout_at',
                'clan_id',
            ]),
        }
        response = requests.get('https://api.worldoftanks.eu/wot/account/info/', params=payload)
        response_content = response.json()

        if response_content['status'] == 'ok':
            player_data = response_content['data'][player_id]
            if player_data:
                return (
                    player_data['created_at'],
                    player_data['last_battle_time'],
                    player_data['logout_at'],
                    str(player_data['clan_id'])
                )

    @staticmethod
    async def get_clan_member_infos(player_id, app_id) -> (str or None):
        """Retrieve clan-specific infos of a clan member."""
        payload = {
            'application_id': app_id,
            'account_id': player_id,
            'language': 'fr',
            'fields': ','.join(['role_i18n']),
        }
        response = requests.get('https://api.worldoftanks.eu/wot/clans/accountinfo/', params=payload)
        response_content = response.json()

        if response_content['status'] == 'ok':
            player_data = response_content['data'][player_id]
            if player_data:
                return player_data['role_i18n']

    @staticmethod
    async def get_clan_infos(clan_id, app_id) -> dict:
        """Retrieve the stats totals of a player."""
        payload = {
            'application_id': app_id,
            'clan_id': clan_id,
            'fields': ','.join([
                'tag',
                'name',
                'emblems',
            ]),
        }
        response = requests.get('https://api.worldoftanks.eu/wot/clans/info/', params=payload)
        response_content = response.json()

        clan_infos = {}
        if response_content['status'] == 'ok':
            clan_data = response_content['data'][clan_id]
            if clan_data:
                clan_infos['name'] = clan_data['name']
                clan_infos['tag'] = clan_data['tag']
                filtered_emblems = {resolution: data for resolution, data in clan_data['emblems'].items() if 'wot' in data}
                largest_emblem_data = sorted(filtered_emblems.items(), reverse=True, key=lambda x: int(x[0][1:]))[0]
                clan_infos['emblem_url'] = largest_emblem_data[1]['wot']
        return clan_infos


def setup(bot):
    bot.add_cog(Stats(bot))
    command.setup(bot)
