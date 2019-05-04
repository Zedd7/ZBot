# -*- coding: utf-8 -*-

import http
import random
import sys
import traceback
import typing

import discord
import emojis
from discord.ext import commands

from zbot import checks
from zbot import converters
from zbot import error_handler
from zbot import exceptions
from zbot import scheduler
from zbot import utils
from zbot import zbot
from . import command


class Lottery(command.Command):

    MAIN_COMMAND_NAME = 'lottery'
    MOD_ROLE_NAMES = ['Administrateur', 'Modérateur', 'Annonceur']
    USER_ROLE_NAMES = ['Joueur']
    ANNOUNCE_ROLE_NAME = 'Abonné Annonces'
    EMBED_COLOR = 0xFAA61A

    pending_lotteries = {}

    def __init__(self, bot):
        super(Lottery, self).__init__(bot)
        zbot.db.load_pending_lotteries(self.pending_lotteries)

    @commands.group(
        name=MAIN_COMMAND_NAME,
        invoke_without_command=True
    )
    @commands.guild_only()
    async def lottery(self, context):
        if context.invoked_subcommand is None:
            await context.send("Commande manquante ou inconnue.")

    @lottery.command(
        name='setup',
        aliases=['s', 'set', 'plan'],
        usage="<\"announce\"> <emoji> <nb_winners> <#dest_channel> <timestamp> [--no-announce]",
        ignore_extra=False
    )
    @commands.check(checks.has_any_mod_role)
    async def setup(self, context,
                    announce: str,
                    emoji: typing.Union[discord.Emoji, str],
                    nb_winners: int,
                    dest_channel: discord.TextChannel,
                    timestamp: converters.to_datetime,
                    *, options=None):
        if isinstance(emoji, str) and emojis.emojis.count(emoji) != 1:
            raise exceptions.ForbiddenEmoji(emoji)
        if nb_winners < 1:
            raise exceptions.UndersizedArgument(nb_winners, 1)
        if not context.author.permissions_in(dest_channel).send_messages:
            raise commands.MissingPermissions([f"`send_messages` in {dest_channel.mention}"])
        if (timestamp - await utils.get_current_time()).total_seconds() <= 0:
            argument_size = converters.humanize_datetime(timestamp)
            min_argument_size = converters.humanize_datetime(await utils.get_current_time())
            raise exceptions.UndersizedArgument(argument_size, min_argument_size)

        organizer = context.author
        embed = discord.Embed(
            title=f"Tirage au sort programmé pour le {converters.humanize_datetime(timestamp)} :alarm_clock:",
            color=self.EMBED_COLOR
        )
        embed.set_author(name=f"Organisateur : @{organizer.display_name}", icon_url=organizer.avatar_url)
        do_announce = '--no-announce' not in options if options else True
        message = await utils.make_announce(context, dest_channel, self.ANNOUNCE_ROLE_NAME, announce, embed, do_announce)
        await message.add_reaction(emoji)

        args = [dest_channel.id, message.id, emoji if isinstance(emoji, str) else emoji.id, nb_winners, organizer.id]
        job_id = scheduler.schedule_lottery(timestamp, self.setup_callback, args).id
        zbot.db.update_lottery(job_id, {'message_id': message.id, 'emoji': emoji if isinstance(emoji, str) else emoji.id})
        self.pending_lotteries[message.id] = {'emoji': emoji, 'job_id': job_id}

    @staticmethod
    async def setup_callback(channel_id, message_id, emoji_code, nb_winners, organizer_id):
        del Lottery.pending_lotteries[message_id]
        channel = command.bot().get_channel(channel_id)
        message = None
        if isinstance(emoji_code, str):  # Emoji is a unicode string
            emoji = emoji_code
        else:  # Emoji is a custom one (discord.Emoji) and emoji_code is its id
            emoji = discord.utils.find(lambda e: e.id == emoji_code, command.bot().emojis)
        organizer = command.bot().get_user(organizer_id)
        try:
            message, players, reaction, winners = await Lottery.draw(channel, emoji, message_id, nb_winners)
            await reaction.remove(command.bot().user)
            await Lottery.announce_winners(winners, players, organizer, message)
        except commands.CommandError as error:
            context = commands.Context(
                bot=command.bot(),
                cog=Lottery,
                prefix=command.bot().command_prefix,
                channel=channel,
                message=message,
            )
            await error_handler.handle(context, error)

    @lottery.command(
        name='pick',
        aliases=['p'],
        usage="<#src_channel> <message_id> <emoji> <nb_winners> <#dest_channel> [<organiser>]",
        ignore_extra=False
    )
    @commands.check(checks.has_any_mod_role)
    async def pick(self,
                   context: commands.Context,
                   src_channel: discord.TextChannel,
                   message_id: int,
                   emoji: typing.Union[discord.Emoji, str],
                   nb_winners: int,
                   dest_channel: discord.TextChannel,
                   organizer: discord.User = None,
                   seed: int = None):

        if isinstance(emoji, str) and emojis.emojis.count(emoji) != 1:
            raise exceptions.ForbiddenEmoji(emoji)
        if nb_winners < 1:
            raise exceptions.UndersizedArgument(nb_winners, 1)
        if not context.author.permissions_in(dest_channel).send_messages:
            raise commands.MissingPermissions([f"`send_messages` in {dest_channel.mention}"])

        message, players, reaction, winners = await Lottery.draw(src_channel, emoji, message_id, nb_winners, seed)
        announce_message = await context.send(f"Tirage au sort sur base de la réaction {emoji} au message \"`{message.content}`\"")
        await Lottery.announce_winners(winners, players, organizer, announce_message)

    @staticmethod
    async def draw(channel, emoji, message_id, nb_winners, seed=None):
        await Lottery.prepare_seed(seed)
        message = await utils.try_get_message(exceptions.MissingMessage(message_id), channel, message_id)
        reaction = await utils.try_get(exceptions.MissingEmoji(emoji), message.reactions, emoji=emoji)
        players, winners = await Lottery.pick_winners(channel, reaction, nb_winners)
        return message, players, reaction, winners

    @staticmethod
    async def prepare_seed(default_seed=None):
        seed = default_seed if default_seed else random.randrange(10 ** 6)  # 6 digits seed
        random.seed(seed)
        current_time = await utils.get_current_time()
        print(f"Picking winners using seed = {seed} ({current_time})")

    @staticmethod
    async def pick_winners(channel, reaction, nb_winners):
        players = [
            player async for player in reaction.users()
            if await checks.has_any_role(channel.guild, player, Lottery.USER_ROLE_NAMES)
            and player != command.bot().user
        ]
        nb_winners = min(nb_winners, len(players))
        winners = random.sample(players, nb_winners)
        return players, winners

    @staticmethod
    async def announce_winners(winners, players, organizer=None, message=None):
        embed = discord.Embed(
            title="Résultat du tirage au sort :tada:",
            description=f"Gagnant(s) parmi {len(players)} participant(s):\n" + await utils.make_user_list(winners, "\n"),
            color=Lottery.EMBED_COLOR
        )
        if organizer:
            embed.set_author(name=f"Organisateur : @{organizer.display_name}", icon_url=organizer.avatar_url)
        await message.edit(embed=embed)

        if organizer:
            # DM winners
            unreachable_winners = []
            for winner in winners:
                try:
                    await winner.send(
                        f"Félicitations ! Tu as été tiré au sort lors de la loterie organisée par {organizer.display_name} ({organizer.mention}) !\n"
                        f"Contacte cette personne par MP pour obtenir ta récompense :wink:")
                except discord.errors.HTTPException as error:
                    if error.status != http.HTTPStatus.FORBIDDEN:  # DMs blocked by user
                        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
                    unreachable_winners.append(winner)
            # DM organizer
            winner_list = await utils.make_user_list(winners)
            await organizer.send(f"Les gagnants de la loterie sont: {winner_list}")
            if unreachable_winners:
                unreachable_winner_list = await utils.make_user_list(unreachable_winners)
                await organizer.send(f"Les gagnants suivants ont bloqué les MPs et n'ont pas pu être contactés: {unreachable_winner_list}")
            # Log players
            player_list = await utils.make_user_list(players, mention=False)
            winner_list = await utils.make_user_list(winners, mention=False)
            print(f"Players : {player_list}")
            print(f"Winners : {winner_list}")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        message = reaction.message
        message_id = message.id
        emoji = reaction.emoji
        if message_id in Lottery.pending_lotteries \
                and emoji == Lottery.pending_lotteries[message_id]['emoji'] \
                and not await checks.has_any_role(message.channel.guild, user, Lottery.USER_ROLE_NAMES):
            try:
                await user.send(f"Vous devez avoir le rôle @{Lottery.USER_ROLE_NAMES[0]} pour participer à cette loterie.")
                await message.remove_reaction(emoji, user)
            except (discord.errors.HTTPException, discord.errors.NotFound):
                pass


def setup(bot):
    bot.add_cog(Lottery(bot))
    command.setup(bot)
