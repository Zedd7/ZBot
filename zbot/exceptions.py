from discord.ext import commands


class ForbiddenEmoji(commands.CommandError):
    def __init__(self, forbidden_emoji):
        self.forbidden_emoji = forbidden_emoji


class MissingClan(commands.CommandError):
    def __init__(self, player_name):
        self.player_name = player_name


class MissingEmoji(commands.CommandError):
    def __init__(self, missing_emoji):
        self.missing_emoji = missing_emoji


class MissingMessage(commands.CommandError):
    def __init__(self, missing_message_id):
        self.missing_message_id = missing_message_id


class MissingRoles(commands.CommandError):
    def __init__(self, missing_roles):
        self.missing_roles = missing_roles


class MissingUser(commands.CommandError):
    def __init__(self, missing_user_name):
        self.missing_user_name = missing_user_name


class OversizedArgument(commands.CommandError):
    def __init__(self, argument_size: int, max_size: int):
        self.argument_size = argument_size
        self.max_size = max_size


class UndersizedArgument(commands.CommandError):
    def __init__(self, argument_size: int, min_size: int):
        self.argument_size = argument_size
        self.min_size = min_size


class UnknowClan(commands.CommandError):
    def __init__(self, unknown_clan_name):
        self.unknown_clan_name = unknown_clan_name


class UnknowPlayer(commands.CommandError):
    def __init__(self, unknown_player_name):
        self.unknown_player_name = unknown_player_name
