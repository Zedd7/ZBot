import typing

from discord.ext import commands

# TODO rename relevant 'missing' to 'unknown'


class ForbiddenEmoji(commands.CommandError):
    def __init__(self, forbidden_emoji):
        self.forbidden_emoji = forbidden_emoji


class MissingClan(commands.CommandError):
    def __init__(self, player_name):
        self.player_name = player_name


class MissingConditionalArgument(commands.CommandError):
    def __init__(self, message):
        self.message = message


class MissingEmoji(commands.CommandError):
    def __init__(self, missing_emoji):
        self.missing_emoji = missing_emoji


class MissingMessage(commands.CommandError):
    def __init__(self, missing_message_id):
        self.missing_message_id = missing_message_id


class MissingRoles(commands.CommandError):
    def __init__(self, missing_roles):
        self.missing_roles = missing_roles


class MissingSubCommand(commands.CommandError):
    def __init__(self, group_command_name):
        self.group_command_name = group_command_name


class MissingUser(commands.CommandError):
    def __init__(self, missing_user_name):
        self.missing_user_name = missing_user_name


class OversizedArgument(commands.CommandError):
    def __init__(self, argument_size: typing.Union[int, str], max_size: typing.Union[int, str]):
        self.argument_size = argument_size
        self.max_size = max_size


class UndersizedArgument(commands.CommandError):
    def __init__(self, argument_size: typing.Union[int, str], min_size: typing.Union[int, str]):
        self.argument_size = argument_size
        self.min_size = min_size


class UnknownClan(commands.CommandError):
    def __init__(self, unknown_clan_name):
        self.unknown_clan_name = unknown_clan_name


class UnknownCommand(commands.CommandError):
    def __init__(self, unknown_command_name):
        self.unknown_command_name = unknown_command_name


class UnknownLottery(commands.CommandError):
    def __init__(self, unknown_lottery_id):
        self.unknown_lottery_id = unknown_lottery_id


class UnknownPlayer(commands.CommandError):
    def __init__(self, unknown_player_name):
        self.unknown_player_name = unknown_player_name


class UnknownRole(commands.CommandError):
    def __init__(self, unknown_role_name):
        self.unknown_role_name = unknown_role_name
