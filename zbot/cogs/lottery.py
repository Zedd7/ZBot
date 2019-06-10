import http
import random
import typing

import discord
import emojis
from discord.ext import commands

from zbot import checker
from zbot import converter
from zbot import error_handler
from zbot import exceptions
from zbot import logger
from zbot import scheduler
from zbot import utils
from zbot import zbot
from . import command


class Lottery(command.Command):

    DISPLAY_NAME = "Loterie et sondages"
    DISPLAY_SEQUENCE = 3
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
            raise exceptions.MissingSubCommand(context.command.name)

    @lottery.command(
        name='setup',
        aliases=['s', 'set', 'plan'],
        usage="<\"announce\"> <emoji> <nb_winners> <#dest_channel> <timestamp> [--no-announce]",
        brief="Programme un tirage au sort",
        help="Le bot publie une annonce correspondant au message entouré de guillemets dans le canal de destination. "
             "Les joueurs participent en cliquant sur l'émoji de réaction. À la date correspondant au timestamp "
             "(au format `\"YYYY-MM-DD HH:MM:SS\"`), les gagnants sont tirés au sort et contactés par MP par le bot. "
             "L'organisateur reçoit par MP une copie du résultat et la liste des participants injoignables."
             "\nPar défaut, l'annonce mentionne automatiquement le rôle `@Abonné Annonces`. "
             "Pour éviter cela, il faut ajouter l'argument `--no-announce`.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def setup(self, context,
                    announce: str,
                    emoji: typing.Union[discord.Emoji, str],
                    nb_winners: int,
                    dest_channel: discord.TextChannel,
                    timestamp: converter.to_datetime,
                    *, options=None):
        if isinstance(emoji, str) and emojis.emojis.count(emoji) != 1:
            raise exceptions.ForbiddenEmoji(emoji)
        if nb_winners < 1:
            raise exceptions.UndersizedArgument(nb_winners, 1)
        if not context.author.permissions_in(dest_channel).send_messages:
            raise commands.MissingPermissions([f"`send_messages` in {dest_channel.mention}"])
        if (timestamp - await utils.get_current_time()).total_seconds() <= 0:
            argument_size = converter.humanize_datetime(timestamp)
            min_argument_size = converter.humanize_datetime(await utils.get_current_time())
            raise exceptions.UndersizedArgument(argument_size, min_argument_size)

        organizer = context.author
        embed = discord.Embed(
            title=f"Tirage au sort programmé pour le {converter.humanize_datetime(timestamp)} :alarm_clock:",
            color=self.EMBED_COLOR
        )
        embed.set_author(name=f"Organisateur : @{organizer.display_name}", icon_url=organizer.avatar_url)
        do_announce = '--no-announce' not in options if options else True
        message = await utils.make_announce(context, dest_channel, self.ANNOUNCE_ROLE_NAME, announce, embed, do_announce)
        await message.add_reaction(emoji)

        args = [dest_channel.id, message.id, emoji if isinstance(emoji, str) else emoji.id, nb_winners, organizer.id]
        job_id = scheduler.schedule_lottery(timestamp, self.setup_callback, args).id
        lottery_data = {
            'lottery_id': self.get_next_lottery_id(),
            'message_id': message.id,
            'channel_id': dest_channel.id,
            'emoji': emoji if isinstance(emoji, str) else emoji.id,
            'organizer_id': organizer.id,
        }
        zbot.db.update_lottery(job_id, lottery_data)
        lottery_data['_id'] = job_id
        self.pending_lotteries[message.id] = lottery_data

    def get_next_lottery_id(self):
        next_lottery_id = 1
        for lottery_data in self.pending_lotteries.values():
            lottery_id = lottery_data['lottery_id']
            if lottery_id >= next_lottery_id:
                next_lottery_id = lottery_id + 1
        return next_lottery_id

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        message = reaction.message
        message_id = message.id
        emoji = reaction.emoji
        if message_id in Lottery.pending_lotteries:
            lottery_emoji = Lottery.pending_lotteries[message_id]['emoji']
            same_emoji = emoji == lottery_emoji if isinstance(emoji, str) else emoji.id == lottery_emoji
            if same_emoji and \
                    not user.bot and \
                    not await checker.has_any_role(message.channel.guild, user, Lottery.USER_ROLE_NAMES):
                try:
                    await user.send(
                        f"Vous devez avoir le rôle @{Lottery.USER_ROLE_NAMES[0]} pour participer à cette loterie.")
                    await message.remove_reaction(emoji, user)
                except (discord.errors.HTTPException, discord.errors.NotFound, discord.errors.Forbidden):
                    pass

    @staticmethod
    async def setup_callback(channel_id, message_id, emoji_code, nb_winners, organizer_id):
        Lottery.remove_pending_lottery(message_id)
        channel = zbot.bot.get_channel(channel_id)
        message = None
        if isinstance(emoji_code, str):  # Emoji is a unicode string
            emoji = emoji_code
        else:  # Emoji is a custom one (discord.Emoji) and emoji_code is its id
            emoji = discord.utils.find(lambda e: e.id == emoji_code, zbot.bot.emojis)
        organizer = zbot.bot.get_user(organizer_id)
        try:
            message, players, reaction, winners = await Lottery.draw(channel, emoji, message_id, nb_winners)
            await reaction.remove(zbot.bot.user)
            await Lottery.announce_winners(winners, players, organizer, message)
        except commands.CommandError as error:
            context = commands.Context(
                bot=zbot.bot,
                cog=Lottery,
                prefix=zbot.bot.command_prefix,
                channel=channel,
                message=message,
            )
            await error_handler.handle(context, error)

    @lottery.command(
        name='cancel',
        aliases=['c', 'r', 'remove'],
        usage="<lottery_id>",
        brief="Annule un tirage au sort",
        help="Le numéro de loterie est affiché entre crochets par la commande `+lottery list`.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def cancel(self, context: commands.Context, lottery_id: int):
        message_ids = {lottery_data['lottery_id']: message_id for message_id, lottery_data in self.pending_lotteries.items()}
        if lottery_id not in message_ids:
            raise exceptions.UnknownLottery(lottery_id)
        self.remove_pending_lottery(message_ids[lottery_id], cancel_job=True)
        await context.send(f"Tirage au sort d'identifiant `{lottery_id}` annulé.")

    @staticmethod
    def remove_pending_lottery(message_id, cancel_job=False):
        for lottery_data in Lottery.pending_lotteries.values():
            if lottery_data['lottery_id'] > Lottery.pending_lotteries[message_id]['lottery_id']:
                lottery_data['lottery_id'] -= 1
                zbot.db.update_lottery(lottery_data['_id'], {'lottery_id': lottery_data['lottery_id']})
        if cancel_job:
            scheduler.cancel_lottery(Lottery.pending_lotteries[message_id]['_id'])
        del Lottery.pending_lotteries[message_id]

    @lottery.command(
        name='list',
        aliases=['l', 'ls'],
        brief="Affiche la liste des tirages au sort en cours",
        ignore_extra=False
    )
    @commands.check(checker.has_any_user_role)
    async def list(self, context: commands.Context):
        lottery_descriptions, guild_id = {}, context.guild.id
        for message_id, lottery_data in self.pending_lotteries.items():
            lottery_id = lottery_data['lottery_id']
            channel_id = lottery_data['channel_id']
            organizer = context.guild.get_member(lottery_data['organizer_id'])
            timestamp = scheduler.get_job_run_date(lottery_data['_id'])
            message_link = f"https://discordapp.com/channels/{guild_id}/{channel_id}/{message_id}"
            lottery_descriptions[lottery_id] = f" • `[{lottery_id}]` - Programmé par {organizer.mention} pour le " \
                f"[__{converter.humanize_datetime(timestamp)}__]({message_link})"
        embed_description = "Aucune" if not lottery_descriptions \
            else "\n".join([lottery_descriptions[lottery_id] for lottery_id in sorted(lottery_descriptions.keys())])
        embed = discord.Embed(
            title="Tirages au sort en cours",
            description=embed_description,
            color=self.EMBED_COLOR
        )
        await context.send(embed=embed)

    @lottery.command(
        name='pick',
        aliases=['p'],
        usage="<#src_channel> <message_id> <emoji> <nb_winners> <#dest_channel> [organiser] [seed]",
        brief="Effectue un tirage au sort",
        help="Le bot tire au sort les gagnants parmi les joueurs ayant réagi au message source avec l'émoji fourni "
             "et publie le résultat dans le canal de destination. Si un organisateur est indiqué, les gagnants sont "
             "contactés par MP par le bot et l'organisateur reçoit par MP une copie du résultat et la liste des "
             "participants injoignables. Si un seed est fourni, le tirage au sort se basera sur celui-ci.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
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
        logger.info(f"Picking winners using seed = {seed} ({current_time})")

    @staticmethod
    async def pick_winners(channel, reaction, nb_winners):
        players = [
            player async for player in reaction.users()
            if await checker.has_any_role(channel.guild, player, Lottery.USER_ROLE_NAMES)
            and player != zbot.bot.user
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
                        logger.error(error, exc_info=True)
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
            logger.info(f"Players : {player_list}")
            logger.info(f"Winners : {winner_list}")


def setup(bot):
    bot.add_cog(Lottery(bot))
