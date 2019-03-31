import asyncio
import http
import random
import sys
import traceback

import discord
from discord.ext import commands

from zbot import converters
from zbot import exceptions
from zbot import utils


class Lottery(commands.Cog):

    MAIN_COMMAND_NAME = 'lottery'
    MOD_ROLE_NAMES = ['Administrateur', 'Modérateur', 'Annonceur']
    USER_ROLE_NAME = 'Joueur'
    ANNOUNCE_ROLE_NAME = 'Abonné Annonces'
    EMBED_COLOR = 0xFAA61A

    def __init__(self, bot):
        self.bot = bot
        self.user = self.bot.user

    @commands.group(
        name=MAIN_COMMAND_NAME,
        invoke_without_command=True
    )
    @commands.guild_only()
    async def lottery(self, context):
        if context.invoked_subcommand is None:
            await context.send("Commande manquante.")
            # TODO display help

    @lottery.command(
        name='setup',
        aliases=['s', 'set', 'plan'],
        usage="<annonce> <emoji> <nb_winners> <#dest_channel> <timestamp>",
        ignore_extra=False
    )
    @commands.check(utils.has_any_mod_role)  # TODO check that player authorize PMs
    async def setup(self, context, announce: str, emoji: str, nb_winners: int, dest_channel: discord.TextChannel, timestamp: converters.to_datetime):
        if not context.author.permissions_in(dest_channel).send_messages:
            raise commands.MissingPermissions([f"`send_messages` in {dest_channel.mention}"])
        if nb_winners < 1:
            raise exceptions.UndersizedArgument(nb_winners, 1)
        if (timestamp - await utils.get_current_time()).total_seconds() <= 0:
            argument_size = converters.humanize_datetime(timestamp)
            min_argument_size = converters.humanize_datetime(await utils.get_current_time())
            raise exceptions.UndersizedArgument(argument_size, min_argument_size)

        organizer = context.author  # TODO  set author avatar and name
        embed = discord.Embed(
            title=f"Tirage au sort programmé pour le {converters.humanize_datetime(timestamp)} :alarm_clock:",
            color=self.EMBED_COLOR
        )
        message = await utils.make_announce(context, dest_channel, self.ANNOUNCE_ROLE_NAME, announce, embed)
        message_id = message.id
        sleep_duration = timestamp - await utils.get_current_time()
        # TODO add reaction

        await asyncio.sleep(sleep_duration.total_seconds())

        # TODO remove itself from reactions
        await Lottery.prepare_seed()
        message, players, winners = await Lottery.pick_winners(context, dest_channel, message_id, emoji, nb_winners)
        await Lottery.announce_winners(winners, players, organizer, message)

    @lottery.command(
        name='pick',
        aliases=['p'],
        usage="<#src_channel> <message_id> <emoji> <nb_winners> <#dest_channel> [<organiser>]",
        ignore_extra=False
    )
    @commands.check(utils.has_any_mod_role)
    async def pick(self,
                   context,
                   src_channel: discord.TextChannel,
                   message_id: int,
                   emoji: str,
                   nb_winners: int,
                   dest_channel: discord.TextChannel,
                   organizer: discord.User = None):

        if not context.author.permissions_in(dest_channel).send_messages:
            raise commands.MissingPermissions([f"`send_messages` in {dest_channel.mention}"])
        if nb_winners < 1:
            raise exceptions.UndersizedArgument(nb_winners, 1)

        await Lottery.prepare_seed()
        message, players, winners = await Lottery.pick_winners(context, src_channel, message_id, emoji, nb_winners)
        await Lottery.announce_winners(winners, players, organizer, message)

    @staticmethod
    async def prepare_seed():
        seed = random.randrange(10 ** 6)  # 6 digits seed
        random.seed(seed)
        current_time = await utils.get_current_time()
        print(f"Picking winner using seed = {seed} ({current_time})")

    @staticmethod
    async def pick_winners(context, channel, message_id, emoji, nb_winners):
        message = await utils.try_get_message(exceptions.MissingMessage(message_id), channel, message_id)
        reaction = await utils.try_get(exceptions.ForbiddenEmoji(emoji), message.reactions, emoji=emoji)
        players = [player async for player in reaction.users() if await utils.has_role(context.guild, player, Lottery.USER_ROLE_NAME)]
        nb_winners = min(nb_winners, len(players))
        winners = random.sample(players, nb_winners)
        return message, players, winners

    @staticmethod
    async def announce_winners(winners, players, organizer, message):
        embed = discord.Embed(
            title="Résultat du tirage au sort :tada:",
            description=f"Gagnant(s) parmi {len(players)} participants:\n" + await utils.list_users(winners, "\n"),
            color=Lottery.EMBED_COLOR
        )
        if organizer:
            embed.set_author(name=f"Organisateur : @{organizer.display_name}", icon_url=organizer.avatar_url)
        await message.edit(embed=embed)

        if organizer:
            unreachable_winners = []
            for winner in winners:
                try:
                    await winner.send(
                        f"Félicitations ! Tu as été tiré au sort lors de la loterie organisée par {organizer.mention} !\n"
                        f"Contacte cette personne par MP pour obtenir ta récompense :wink:")
                except discord.errors.HTTPException as error:
                    if error.status != http.HTTPStatus.FORBIDDEN:  # DMs blocked by user
                        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
                    unreachable_winners.append(winner)
            winner_list = await utils.list_users(winners)
            await organizer.send(f"Les gagnants de la loterie sont: {winner_list}")
            if unreachable_winners:
                unreachable_winner_list = await utils.list_users(unreachable_winners)
                await organizer.send(f"Les gagnants suivants ont bloqué les MPs et n'ont pas pu être contactés: {unreachable_winner_list}")


def setup(bot):
    bot.add_cog(Lottery(bot))
