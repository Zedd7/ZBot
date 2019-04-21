# -*- coding: utf-8 -*-

from discord.ext import commands


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
