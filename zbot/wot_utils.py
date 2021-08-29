import json

import discord
import requests

from . import logger
from . import utils


class WargammingAPIError(Exception):
    pass


def get_players_info(member_names: list, app_id) -> dict:
    """Retrieve the exact player name and account id of a list of players.

    Only matching names will have their information included in the returned dict.
    """

    def _fetch_players_data(_player_names):
        """Recursively fetch players data in batch.

        If a batch contains an invalid (non-ascii, > 25 chars, ...) player name that is making the request fail, the
        batch is split in two and recursively processed. When the faulty player name is found, it is discarded.
        """
        _players_data = []
        for _name_batch in batch(_player_names, 100):
            _payload = {
                'application_id': app_id,
                'search': ','.join(_name_batch),
                'fields': ','.join([
                    'nickname',
                    'account_id',
                ]),
                'type': 'exact',
            }
            _response = requests.post('https://api.worldoftanks.eu/wot/account/list/', data=_payload)
            _response_content = _response.json()
            if _response_content['status'] == 'ok':
                _players_data += _response_content['data']
            elif _response_content['error']['message'] == 'INVALID_SEARCH':  # 'search' param invalid
                if len(_name_batch) > 1:  # At least one invalid player name in the batch, split it
                    _split_at = len(_name_batch) // 2
                    _players_data += _fetch_players_data(_name_batch[:_split_at])
                    _players_data += _fetch_players_data(_name_batch[_split_at:])
                else:  # Found the invalid player name of the batch
                    pass  # Don't return anything to discard it
            elif _response_content['error']['message'] == 'SOURCE_NOT_AVAILABLE':  # The API can't return the data.
                raise WargammingAPIError()
        return _players_data

    # Remove malformed nicknames
    sanitized_player_names = utils.sanitize_player_names(member_names)

    # Gather information for matching names
    players_info = {}
    for player_data in _fetch_players_data(sanitized_player_names):
        player_name = player_data['nickname']
        account_id = str(player_data['account_id'])
        players_info[player_name] = account_id
    return players_info


def get_exact_player_info(player_name, app_id) -> (str, int or None):
    """Retrieve the exact player name and account id of a player."""

    if len(players_info := get_players_info([player_name], app_id)) == 1:
        return (exact_player_name := list(players_info.keys())[0]), players_info[exact_player_name]
    return player_name, None


def get_players_details(player_ids: list, app_id) -> dict:
    """Retrieve the personal information of a list of players."""
    players_details = {}
    for player_ids_batch in batch(player_ids, 100):
        payload = {
            'application_id': app_id,
            'account_id': ','.join(player_ids_batch),
            'fields': ','.join([
                'created_at',
                'last_battle_time',
                'logout_at',
                'clan_id',
            ]),
        }
        response = requests.post('https://api.worldoftanks.eu/wot/account/info/', data=payload)
        response_content = response.json()

        if response_content['status'] == 'ok':
            for account_id, player_data in response_content['data'].items():
                players_details[account_id] = (
                    player_data['created_at'],
                    player_data['last_battle_time'],
                    player_data['logout_at'],
                    str(player_data['clan_id']) if player_data['clan_id'] else None
                )
    return players_details


def get_player_details(player_id, app_id) -> (int, int, int, str):
    """Retrieve the personal information of a player."""
    if len(players_details := get_players_details([player_id], app_id)) == 1:
        return players_details[player_id]
    return (None,) * 4


def get_player_stats_totals(player_id, app_id) -> dict or None:
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
    response = requests.post('https://api.worldoftanks.eu/wot/account/info/', data=payload)
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
            stats_totals['win_rate'] = (stats_totals['wins'] / stats_totals['battles']) \
                if stats_totals['battles'] > 0 else 0
            return stats_totals


def get_player_tank_stats(player_id, exp_values, app_id) -> (dict, dict, list) or (None,) * 3:
    """Retrieve the tank specific stats and expected stats totals of a player."""
    payload = {
        'application_id': app_id,
        'account_id': player_id,
        'fields': ','.join([
            'tank_id',
            'statistics.battles',
        ]),
    }
    response = requests.post('https://api.worldoftanks.eu/wot/account/tanks/', data=payload)
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


def get_clan_id(clan_search_field, app_id) -> str or None:
    """Retrieve the clan id of a clan."""
    payload = {
        'application_id': app_id,
        'search': clan_search_field,
        'fields': ','.join(['clan_id']),
    }
    response = requests.post('https://api.worldoftanks.eu/wot/clans/list/', data=payload)
    response_content = response.json()

    if response_content['status'] == 'ok':
        clan_data = response_content['data']
        if clan_data:
            return str(clan_data[0]['clan_id'])


def get_clan_infos(clan_id, app_id) -> dict or None:
    """Retrieve information of a clan."""
    payload = {
        'application_id': app_id,
        'clan_id': clan_id,
        'fields': ','.join([
            'name',
            'tag',
            'created_at',
            'motto',
            'color',
            'emblems',
            'accepts_join_requests',
            'leader_id',
            'leader_name',
            'members_count',
        ]),
    }
    response = requests.post('https://api.worldoftanks.eu/wot/clans/info/', data=payload)
    response_content = response.json()

    if response_content['status'] == 'ok':
        clan_data = response_content['data'][clan_id]
        if clan_data:
            filtered_emblems = {resolution: data for resolution, data in clan_data['emblems'].items() if 'wot' in data}
            largest_emblem_data = sorted(filtered_emblems.items(), reverse=True, key=lambda x: int(x[0][1:]))[0]
            clan_infos = {
                'name': clan_data['name'],
                'tag': clan_data['tag'],
                'creation_timestamp': clan_data['created_at'],
                'motto': clan_data['motto'],
                'color': int(clan_data['color'].replace('#', ''), 16) if clan_data['color'] else None,
                'emblem_url': largest_emblem_data[1]['wot'],
                'recruiting': bool(clan_data['accepts_join_requests']),
                'leader_id': str(clan_data['leader_id']),
                'leader_name': clan_data['leader_name'],
                'members_count': clan_data['members_count'],
            }
            return clan_infos


def get_clan_contact(clan_id, guild_members, role_name, app_id) -> discord.Member or None:
    """Retrieve the clan contact of a clan."""
    payload = {
        'application_id': app_id,
        'clan_id': clan_id,
        'fields': ','.join([
            'members.account_name',
        ]),
    }
    response = requests.post('https://api.worldoftanks.eu/wot/clans/info/', data=payload)
    response_content = response.json()

    if response_content['status'] == 'ok':
        clan_data = response_content['data'][clan_id]
        if clan_data:
            for clan_member_name in [player_data['account_name'] for player_data in clan_data['members']]:
                for guild_member in guild_members:
                    guild_member_name = (guild_member.nick if guild_member.nick else guild_member.display_name).split(' ')[0]
                    if clan_member_name == guild_member_name and discord.utils.get(guild_member.roles, name=role_name):
                        return guild_member


def get_clan_member_infos(player_id, app_id) -> str or None:
    """Retrieve clan-specific information of a clan member."""
    payload = {
        'application_id': app_id,
        'account_id': player_id,
        'language': 'fr',
        'fields': ','.join([
            'role_i18n',
            'clan.tag'
        ]),
    }
    response = requests.post('https://api.worldoftanks.eu/wot/clans/accountinfo/', data=payload)
    response_content = response.json()

    if response_content['status'] == 'ok':
        player_data = response_content['data'][player_id]
        if player_data:
            clan_member_infos = {
                'position': player_data['role_i18n'],
                'tag': player_data['clan']['tag'],
            }
            return clan_member_infos


def deduct_missing_tanks(player_id, stats_totals, missing_tanks, app_id) -> dict or None:
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
        response = requests.post('https://api.worldoftanks.eu/wot/tanks/stats/', data=payload)
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


def load_exp_values(exp_values_file_path, exp_values_file_url) -> dict or None:
    """
    Download or load the last version of expected WN8 values.
    On Heroku, the file storing expected WN8 values gets deleted when the bot shuts down.
    """
    exp_values_json = None
    exp_values_file_path.parent.mkdir(parents=True, exist_ok=True)
    if not exp_values_file_path.exists():
        response = requests.get(exp_values_file_url)
        if response.ok:
            with exp_values_file_path.open(mode='w') as exp_values_file:
                exp_values_file.write(response.text)
                exp_values_json = response.json()
            logger.debug(f"Could not find {exp_values_file_path.name}, created it.")
        else:
            logger.warning(f"Could not reach {exp_values_file_url} - "
                           f"Skipped loading of expected WN8 values.")
    else:
        with exp_values_file_path.open(mode='r') as exp_values_file:
            exp_values_json = json.load(exp_values_file)
        logger.debug(f"Loaded expected WN8 values from {exp_values_file_path.name}.")

    if exp_values_json:
        exp_values = {}
        for tank_data in exp_values_json['data']:
            exp_values[tank_data['IDNum']] = {
                'damage_ratio': tank_data['expDamage'],
                'spot_ratio': tank_data['expSpot'],
                'kill_ratio': tank_data['expFrag'],
                'defense_ratio': tank_data['expDef'],
                'win_ratio': tank_data['expWinRate'],
            }
        return exp_values


def load_tank_tiers(app_id) -> dict or None:
    """Retrieve all tanks' tier."""
    payload = {
        'application_id': app_id,
        'fields': ','.join(['tier']),
    }
    response = requests.post('https://api.worldoftanks.eu/wot/encyclopedia/vehicles/', data=payload)
    response_content = response.json()

    if response_content['status'] == 'ok':
        tank_data = response_content['data']
        if tank_data:
            tank_tiers = {tank_id: tank_data[tank_id]['tier'] for tank_id in tank_data}
            logger.debug("Loaded all tank tiers.")
            return tank_tiers
    logger.warning("Could not load all tank tiers - Skipped.")
    return None


def compute_average_tier(tank_stats, tank_tiers) -> float:
    """Compute the average tier of a player."""
    average_tier = 0
    if tank_stats:
        total_battles, weighted_sum = 0, 0
        for tank_id in tank_stats:
            tier = tank_tiers.get(tank_id, 0)
            battles = tank_stats[tank_id]['battles']
            total_battles += battles
            weighted_sum += tier * battles
        average_tier = weighted_sum / total_battles
    return average_tier


def compute_wn8(stats_totals, exp_stat_totals) -> float:
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


def batch(iterable, batch_size):
    """ Split an iterable into constant-size batches. """
    for index in range(0, len(iterable), batch_size):
        if isinstance(iterable, dict):
            yield {k: iterable[k] for k in list(iterable.keys())[index:index + batch_size]}
        else:
            yield iterable[index:index + batch_size]
