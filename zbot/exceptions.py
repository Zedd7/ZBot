# -*- coding: utf-8 -*-

from discord.ext import commands


class MissingUser(commands.CommandError):
    def __init__(self, missing_user_name):
        self.missing_user_name = missing_user_name


class MissingRoles(commands.CommandError):
    def __init__(self, missing_roles):
        self.missing_roles = missing_roles


class MissingMessage(commands.CommandError):
    def __init__(self, missing_message_id):
        self.missing_message_id = missing_message_id


class MissingEmoji(commands.CommandError):
    def __init__(self, missing_emoji):
        self.missing_emoji = missing_emoji


class UndersizedArgument(commands.CommandError):
    def __init__(self, argument_size: int, min_size: int):
        self.argument_size = argument_size
        self.min_size = min_size


class OversizedArgument(commands.CommandError):
    def __init__(self, argument_size: int, max_size: int):
        self.argument_size = argument_size
        self.max_size = max_size


class UnknowPlayer(commands.CommandError):
    def __init__(self, unknown_player_name):
        self.unknown_player_name = unknown_player_name


class UnknowClan(commands.CommandError):
    def __init__(self, unknown_clan_name):
        self.unknown_clan_name = unknown_clan_name
