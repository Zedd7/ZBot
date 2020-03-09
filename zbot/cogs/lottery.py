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

    DISPLAY_NAME = "Loteries & Tirages au sort"
    DISPLAY_SEQUENCE = 3
    MOD_ROLE_NAMES = ['Administrateur', 'Modérateur', 'Annonceur']
    USER_ROLE_NAMES = ['Joueur']

    ANNOUNCE_ROLE_NAME = 'Abonné Annonces'
    EMBED_COLOR = 0xFAA61A

    pending_lotteries = {}

    def __init__(self, bot):
        super(Lottery, self).__init__(bot)
        zbot.db.load_pending_lotteries(self.pending_lotteries)

    @commands.group(
        name='lottery',
        invoke_without_command=True
    )
    @commands.guild_only()
    async def lottery(self, context):
        if context.invoked_subcommand is None:
            raise exceptions.MissingSubCommand(context.command.name)

    @lottery.command(
        name='setup',
        aliases=['s', 'set', 'plan'],
        usage="<\"announce\"> <#dest_channel> <:émoji:> <nb_winners> <\"time\"> [--no-announce]",
        brief="Programme un tirage au sort",
        help="Le bot publie une annonce correspondant au message entouré de guillemets dans le canal de destination. "
             "Les joueurs participent en cliquant sur l'émoji de réaction. À la date et à l'heure indiquées "
             "(au format `\"YYYY-MM-DD HH:MM:SS\"`), les gagnants sont tirés au sort et contactés par MP par le bot. "
             "L'organisateur reçoit par MP une copie du résultat et de la liste des participants injoignables. "
             "Par défaut, l'annonce mentionne automatiquement le rôle `@Abonné Annonces`. "
             "Pour éviter cela, il faut ajouter l'argument `--no-announce`.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def setup(self, context: commands.Context,
                    announce: str,
                    dest_channel: discord.TextChannel,
                    emoji: typing.Union[discord.Emoji, str],
                    nb_winners: int,
                    time: converter.to_datetime,
                    *, options=None):
        if not context.author.permissions_in(dest_channel).send_messages:
            raise commands.MissingPermissions([f"`send_messages` in {dest_channel.mention}"])
        if isinstance(emoji, str) and emojis.emojis.count(emoji) != 1:
            raise exceptions.ForbiddenEmoji(emoji)
        if nb_winners < 1:
            raise exceptions.UndersizedArgument(nb_winners, 1)
        if (time - utils.get_current_time()).total_seconds() <= 0:
            argument_size = converter.humanize_datetime(time)
            min_argument_size = converter.humanize_datetime(utils.get_current_time())
            raise exceptions.UndersizedArgument(argument_size, min_argument_size)

        organizer = context.author
        do_announce = not options or '--no-announce' not in options
        prefixed_announce = utils.make_announce(context, announce, do_announce and self.ANNOUNCE_ROLE_NAME)
        embed = self.build_announce_embed(emoji, nb_winners, organizer, time, context.guild.roles)
        message = await dest_channel.send(prefixed_announce, embed=embed)
        await message.add_reaction(emoji)

        job_id = scheduler.schedule_lottery(time, self.run_lottery, message.id).id
        lottery_data = {
            'lottery_id': self.get_next_lottery_id(),
            'message_id': message.id,
            'channel_id': dest_channel.id,
            'emoji_code': emoji if isinstance(emoji, str) else emoji.id,
            'nb_winners': nb_winners,
            'organizer_id': organizer.id,
        }
        zbot.db.update_lottery(job_id, lottery_data)
        # Add data managed by scheduler later to avoid updating the database with them
        lottery_data.update({'_id': job_id, 'next_run_time': converter.to_timestamp(time)})
        self.pending_lotteries[message.id] = lottery_data
        await context.send(f"Tirage au sort d'identifiant `{lottery_data['lottery_id']}` programmé : <{message.jump_url}>.")

    @staticmethod
    def build_announce_embed(emoji, nb_winners, organizer, time, guild_roles):
        embed = discord.Embed(
            title=f"Tirage au sort programmé pour le {converter.humanize_datetime(time)} :alarm_clock:",
            color=Lottery.EMBED_COLOR
        )
        embed.add_field(
            name="Nombre de gagnants",
            value=f"**{nb_winners}** joueur{('s' if nb_winners > 1 else '')}",
            inline=True
        )
        embed.add_field(
            name="Inscription",
            value=f"Réagissez avec {emoji}",
            inline=True
        )
        embed.add_field(
            name="Rôle requis",
            value=utils.try_get(
                guild_roles,
                error=exceptions.UnknownRole(Lottery.USER_ROLE_NAMES[0]),
                name=Lottery.USER_ROLE_NAMES[0]
            ).mention,
            inline=True
        )
        embed.set_author(
            name=f"Organisateur : @{organizer.display_name}",
            icon_url=organizer.avatar_url
        )
        return embed

    def get_next_lottery_id(self) -> int:
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
            lottery_emoji_code = Lottery.pending_lotteries[message_id]['emoji_code']
            same_emoji = emoji == lottery_emoji_code if isinstance(emoji, str) else emoji.id == lottery_emoji_code
            if same_emoji and \
                    not user.bot and \
                    not checker.has_any_role(message.channel.guild, user, Lottery.USER_ROLE_NAMES):
                try:
                    await utils.try_dm(user, f"Vous devez avoir le rôle @{Lottery.USER_ROLE_NAMES[0]} pour participer à cette loterie.")
                    await message.remove_reaction(emoji, user)
                except (discord.errors.HTTPException, discord.errors.NotFound, discord.errors.Forbidden):
                    pass

    @lottery.command(
        name='pick',
        aliases=['p', 'run', 'r'],
        usage="<#src_channel> <message_id> [:émoji:] [nb_winners] [#dest_channel] [@organizer] [seed]",
        brief="Effectue un tirage au sort",
        help="Le bot tire au sort les gagnants parmi les joueurs ayant réagi au message source avec l'émoji fourni. "
             "Si le message est une loterie gérée par le bot, elle se déroule à l'avance dans le message source indiqué "
             "en donnant la priorité aux paramètres fournis sur les paramètres originaux. Sinon, le canal de destination "
             "doit être fourni et est utilisé pour y publier les résultats du tirage au sort. Si un organisateur est "
             "indiqué, les gagnants sont contactés par MP par le bot et l'organisateur reçoit par MP une copie du "
             "résultat et de la liste des participants injoignables. Si un seed est fourni, le tirage au sort se base "
             "dessus pour le choix des gagnants.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def pick(self, context: commands.Context,
                   src_channel: discord.TextChannel,
                   message_id: int,
                   emoji: typing.Union[discord.Emoji, str] = None,
                   nb_winners: int = None,
                   dest_channel: discord.TextChannel = None,
                   organizer: discord.User = None,
                   seed: int = None):

        if emoji and isinstance(emoji, str) and emojis.emojis.count(emoji) != 1:
            raise exceptions.ForbiddenEmoji(emoji)
        if nb_winners and nb_winners < 1:
            raise exceptions.UndersizedArgument(nb_winners, 1)
        if dest_channel and not context.author.permissions_in(dest_channel).send_messages:
            raise commands.MissingPermissions([f"`send_messages` in {dest_channel.mention}"])

        message = await utils.try_get_message(src_channel, message_id, error=exceptions.MissingMessage(message_id))
        if message.author == self.user:  # Target message is a lottery, run it now
            # Backup values before they get deleted
            job_id, lottery_id = (self.pending_lotteries[message_id][key] for key in ('_id', 'lottery_id'))

            await Lottery.run_lottery(
                message_id,
                emoji_code=emoji if not emoji or isinstance(emoji, str) else emoji.id,
                nb_winners=nb_winners,
                organizer_id=organizer and organizer.id,
                seed=seed,
                manual_run=True,
            )
            await context.send(f"Tirage au sort d'identifiant `{lottery_id}` exécuté : <{message.jump_url}>")
        else:  # Target message is not a lottery, pick winners from reactions
            if not emoji:
                raise exceptions.MissingConditionalArgument(
                    "Un émoji doit être fourni si le message ciblé n'est pas une loterie.")
            if not nb_winners:
                raise exceptions.MissingConditionalArgument(
                    "Un nombre de gagnants doit être fourni si le message ciblé n'est pas une loterie.")
            if not dest_channel:
                raise exceptions.MissingConditionalArgument(
                    "Un canal de destination doit être fourni si le message ciblé n'est pas une loterie.")
            _, players, reaction, winners = await Lottery.draw(src_channel, message_id, emoji, nb_winners, seed)
            announce = f"Tirage au sort sur base de la réaction {emoji} {f'et du seed `{seed}` ' if seed else ''}" \
                       f"au message \"`{message.clean_content}`\""
            await Lottery.announce_winners(winners, players, organizer=organizer, message=await context.send(announce))

    @staticmethod
    async def run_lottery(message_id, emoji_code=None, nb_winners=None, organizer_id=None, seed=None, manual_run=False):
        lottery_data = Lottery.pending_lotteries[message_id]
        channel = zbot.bot.get_channel(lottery_data['channel_id'])
        emoji = utils.get_emoji(emoji_code or lottery_data['emoji_code'], zbot.bot.emojis)
        organizer = zbot.bot.get_user(organizer_id or lottery_data['organizer_id'])
        message = None
        try:
            message, players, reaction, winners = await Lottery.draw(
                channel, message_id, emoji, nb_winners or lottery_data['nb_winners'], seed)
            await reaction.remove(zbot.bot.user)
            await Lottery.announce_winners(winners, players, organizer, message)
            Lottery.remove_pending_lottery(message_id, cancel_job=manual_run)
        except commands.CommandError as error:
            context = commands.Context(
                bot=zbot.bot,
                cog=Lottery,
                prefix=zbot.bot.command_prefix,
                channel=channel,
                message=message,
            )
            await error_handler.handle(context, error)

    @lottery.group(
        name='edit',
        invoke_without_command=True
    )
    @commands.check(checker.has_any_mod_role)
    async def edit(self, context):
        if context.invoked_subcommand is None:
            raise exceptions.MissingSubCommand(f'lottery {context.command.name}')

    @edit.command(
        name='announce',
        aliases=['annonce', 'a', 'description', 'desc', 'd', 'message', 'm'],
        usage="<lottery_id> <\"annonce\"> [--no-announce]",
        brief="Modifie l'annonce du tirage au sort",
        help="La précédente annonce associée au tirage au sort est remplacée par le message fourni. "
             "Par défaut, la nouvelle annonce mentionne automatiquement le rôle `@Abonné Annonces`. "
             "Pour éviter cela, il faut ajouter l'argument `--no-announce`.\n"
             "Dans tous les cas, les membres du serveur ne seront pas notifiés.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def announce(self, context: commands.Context,
                       lottery_id: int,
                       announce: str,
                       *, options=None):
        message, channel, _, _, _, _ = await self.get_message_env(lottery_id, raise_if_not_found=True)

        if not context.author.permissions_in(channel).send_messages:
            raise commands.MissingPermissions([f"`send_messages` in {channel.mention}"])

        do_announce = not options or '--no-announce' not in options
        prefixed_announce = utils.make_announce(context, announce, do_announce and self.ANNOUNCE_ROLE_NAME)
        await message.edit(content=prefixed_announce)
        await context.send(f"Annonce du tirage au sort d'identifiant `{lottery_id}` remplacée par "
                           f"\"`{message.clean_content}`\" : <{message.jump_url}>")

    @edit.command(
        name='emoji',
        aliases=['émoji', 'e'],
        usage="<lottery_id> <:emoji:>",
        brief="Modifie l'émoji du tirage au sort",
        help="Le précédent émoji associé au tirage au sort est remplacé par l'émoji fourni. Les réactions à l'ancien "
             "émoji ne sont pas prises en compte.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def emoji(self, context: commands.Context,
                    lottery_id: int,
                    emoji: typing.Union[discord.Emoji, str]):
        message, channel, previous_emoji, nb_winners, time, organizer = \
            await self.get_message_env(lottery_id, raise_if_not_found=True)

        if not context.author.permissions_in(channel).send_messages:
            raise commands.MissingPermissions([f"`send_messages` in {channel.mention}"])
        if isinstance(emoji, str) and emojis.emojis.count(emoji) != 1:
            raise exceptions.ForbiddenEmoji(emoji)

        previous_reaction = utils.try_get(message.reactions, error=exceptions.MissingEmoji(emoji), emoji=previous_emoji)
        await previous_reaction.remove(zbot.bot.user)
        await message.add_reaction(emoji)
        embed = self.build_announce_embed(emoji, nb_winners, organizer, time, context.guild.roles)
        await message.edit(embed=embed)

        job_id = self.pending_lotteries[message.id]['_id']
        lottery_data = {'emoji_code': emoji if isinstance(emoji, str) else emoji.id}
        zbot.db.update_lottery(job_id, lottery_data)
        self.pending_lotteries[message.id].update(lottery_data)
        await context.send(f"Émoji du tirage au sort d'identifiant `{lottery_id}` remplacé par "
                           f"\"{emoji}\" : <{message.jump_url}>")

    @edit.command(
        name='organizer',
        aliases=['organisateur', 'o'],
        usage="<lottery_id> <@organizer>",
        brief="Modifie l'organisateur du tirage au sort",
        help="Le précédent organisateur du tirage au sort est remplacé par l'organisateur fourni.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def organizer(self, context: commands.Context,
                        lottery_id: int,
                        organizer: discord.User):
        message, channel, emoji, nb_winners, time, _ = \
            await self.get_message_env(lottery_id, raise_if_not_found=True)

        if not context.author.permissions_in(channel).send_messages:
            raise commands.MissingPermissions([f"`send_messages` in {channel.mention}"])

        embed = self.build_announce_embed(emoji, nb_winners, organizer, time, context.guild.roles)
        await message.edit(embed=embed)

        job_id = self.pending_lotteries[message.id]['_id']
        lottery_data = {'organizer_id': organizer.id}
        zbot.db.update_lottery(job_id, lottery_data)
        self.pending_lotteries[message.id].update(lottery_data)
        await context.send(f"Organisateur du tirage au sort d'identifiant `{lottery_id}` remplacé par "
                           f"`@{organizer.display_name}` : <{message.jump_url}>")

    @edit.command(
        name='time',
        aliases=['date', 'heure', 't'],
        usage="<lottery_id> <\"time\">",
        brief="Modifie la date et l'heure du tirage au sort",
        help="Le précédente date et heure du tirage au sort sont changés pour celles fournies (au format \"YYYY-MM-DD "
             "HH:MM:SS\"`). ",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def time(self, context: commands.Context,
                   lottery_id: int,
                   time: converter.to_datetime):
        message, channel, emoji, nb_winners, _, organizer = \
            await self.get_message_env(lottery_id, raise_if_not_found=True)

        if not context.author.permissions_in(channel).send_messages:
            raise commands.MissingPermissions([f"`send_messages` in {channel.mention}"])
        if (time - utils.get_current_time()).total_seconds() <= 0:
            argument_size = converter.humanize_datetime(time)
            min_argument_size = converter.humanize_datetime(utils.get_current_time())
            raise exceptions.UndersizedArgument(argument_size, min_argument_size)

        embed = self.build_announce_embed(emoji, nb_winners, organizer, time, context.guild.roles)
        await message.edit(embed=embed)

        job_id = self.pending_lotteries[message.id]['_id']
        scheduler.reschedule_lottery(job_id, time)  # Also updates the next_run_time in db
        lottery_data = {'next_run_time': converter.to_timestamp(time)}
        self.pending_lotteries[message.id].update(lottery_data)
        await context.send(f"Date et heure du tirage au sort d'identifiant `{lottery_id}` changés pour le "
                           f"`{converter.humanize_datetime(time)}` : <{message.jump_url}>")

    @edit.command(
        name='winners',
        aliases=['gagnants', 'nb_winners', 'n'],
        usage="<lottery_id> <nb_winners>",
        brief="Modifie le nombre de gagnants du tirage au sort",
        help="Le précédent nombre de gagnants du tirage au sort est remplacé par le nombre de gagnants fourni.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def winners(self, context: commands.Context,
                      lottery_id: int,
                      nb_winners: int):
        message, channel, emoji, _, time, organizer = \
            await self.get_message_env(lottery_id, raise_if_not_found=True)

        if not context.author.permissions_in(channel).send_messages:
            raise commands.MissingPermissions([f"`send_messages` in {channel.mention}"])
        if nb_winners < 1:
            raise exceptions.UndersizedArgument(nb_winners, 1)

        embed = self.build_announce_embed(emoji, nb_winners, organizer, time, context.guild.roles)
        await message.edit(embed=embed)

        job_id = self.pending_lotteries[message.id]['_id']
        lottery_data = {'nb_winners': nb_winners}
        zbot.db.update_lottery(job_id, lottery_data)
        self.pending_lotteries[message.id].update(lottery_data)
        await context.send(f"Nombre de gagnants du tirage au sort d'identifiant `{lottery_id}` changé à "
                           f"`{nb_winners}` : <{message.jump_url}>")

    @lottery.command(
        name='cancel',
        aliases=['c'],
        usage="<lottery_id>",
        brief="Annule le tirage au sort",
        help="Le numéro de loterie est affiché entre crochets par la commande `+lottery list`.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def cancel(self, context: commands.Context, lottery_id: int):
        message, channel, emoji, _, _, organizer = await self.get_message_env(
            lottery_id, raise_if_not_found=False)
        if message:
            reaction = utils.try_get(message.reactions, error=exceptions.MissingEmoji(emoji), emoji=emoji)
            await reaction.remove(zbot.bot.user)
            embed = discord.Embed(
                title=f"Tirage au sort __annulé__ par {context.author.display_name}",
                color=Lottery.EMBED_COLOR
            )
            embed.set_author(name=f"Organisateur : @{organizer.display_name}", icon_url=organizer.avatar_url)
            await message.edit(embed=embed)
        self.remove_pending_lottery(message.id, cancel_job=True)
        await context.send(f"Tirage au sort d'identifiant `{lottery_id}` annulé.")

    @staticmethod
    async def get_message_env(lottery_id: int, raise_if_not_found=True) -> \
            (discord.Message, discord.TextChannel, str, int, str, discord.Member):
        if not (res := list(
                filter(lambda data: data['lottery_id'] == lottery_id, Lottery.pending_lotteries.values())
        )):
            raise exceptions.UnknownLottery(lottery_id)
        lottery_data = res[0]
        message_id = lottery_data['message_id']
        channel = zbot.bot.get_channel(lottery_data['channel_id'])
        emoji_code = lottery_data['emoji_code']
        nb_winners = lottery_data['nb_winners']
        next_run_timestamp = lottery_data['next_run_time']
        organizer = zbot.bot.get_user(lottery_data['organizer_id'])

        message = await utils.try_get_message(
            channel, message_id,
            error=exceptions.MissingMessage(message_id) if raise_if_not_found else None)
        emoji = utils.get_emoji(emoji_code, zbot.bot.emojis)
        time = converter.from_timestamp(next_run_timestamp)
        return message, channel, emoji, nb_winners, time, organizer

    @staticmethod
    def remove_pending_lottery(message_id, cancel_job=False):
        if message_id not in Lottery.pending_lotteries:
            return  # Callback of misfired lottery or manual run
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
            time = scheduler.get_job_run_date(lottery_data['_id'])
            message_link = f"https://discordapp.com/channels/{guild_id}/{channel_id}/{message_id}"
            lottery_descriptions[lottery_id] = f" • `[{lottery_id}]` - Programmé par {organizer.mention} pour le " \
                f"[__{converter.humanize_datetime(time)}__]({message_link})"
        embed_description = "Aucun" if not lottery_descriptions \
            else "\n".join([lottery_descriptions[lottery_id] for lottery_id in sorted(lottery_descriptions.keys())])
        embed = discord.Embed(
            title="Tirage(s) au sort en cours",
            description=embed_description,
            color=self.EMBED_COLOR
        )
        await context.send(embed=embed)

    @staticmethod
    async def draw(channel, message_id, emoji, nb_winners, seed=None):
        await Lottery.prepare_seed(seed)
        message = await utils.try_get_message(channel, message_id, error=exceptions.MissingMessage(message_id))
        reaction = utils.try_get(message.reactions, error=exceptions.MissingEmoji(emoji), emoji=emoji)
        players, winners = await Lottery.pick_winners(channel, reaction, nb_winners)
        return message, players, reaction, winners

    @staticmethod
    async def prepare_seed(default_seed=None):
        seed = default_seed if default_seed else random.randrange(10 ** 6)  # 6 digits seed
        random.seed(seed)
        logger.info(f"Picking winners using seed = {seed} ({utils.get_current_time()})")

    @staticmethod
    async def pick_winners(channel, reaction, nb_winners, ignore_roles=False):
        players = list(filter(
            lambda m: checker.has_any_role(channel.guild, m, Lottery.USER_ROLE_NAMES) or ignore_roles and m != zbot.bot.user,
            await reaction.users().flatten())
        )
        nb_winners = min(nb_winners, len(players))
        winners = random.sample(players, nb_winners)
        return players, winners

    @staticmethod
    async def announce_winners(winners: [discord.User], players: [discord.User],
                               organizer: discord.User = None, message=None):
        if message:
            embed = discord.Embed(
                title="Résultat du tirage au sort :tada:",
                description=f"Gagnant(s) parmi {len(players)} participant(s):\n" + utils.make_user_list(winners, "\n"),
                color=Lottery.EMBED_COLOR
            )
            if organizer:
                embed.set_author(name=f"Organisateur : @{organizer.display_name}", icon_url=organizer.avatar_url)
            await message.edit(embed=embed)

        if organizer:
            # DM winners
            unreachable_winners = []
            for winner in winners:
                if not await utils.try_dm(
                    winner, f"Félicitations ! Tu as été tiré au sort lors de la loterie organisée "
                            f"par {organizer.display_name} ({organizer.mention}) !\n"
                            f"Contacte cette personne par MP pour obtenir ta récompense :wink:" +
                            (f"\nLien : {message.jump_url}" if message else "")
                ):
                    unreachable_winners.append(winner)
            # DM organizer
            winner_list = utils.make_user_list(winners)
            await utils.try_dm(organizer, f"Les gagnants de la loterie sont: {winner_list}" +
                               (f"\nLien : {message.jump_url}" if message else ""))
            if unreachable_winners:
                unreachable_winner_list = utils.make_user_list(unreachable_winners)
                await utils.try_dm(organizer, f"Les gagnants suivants ont bloqué les MPs et n'ont "
                                              f"pas pu être contactés: {unreachable_winner_list}")
            # Log players and winners
            player_list = utils.make_user_list(players, mention=False)
            winner_list = utils.make_user_list(winners, mention=False)
            logger.info(f"Players : {player_list}")
            logger.info(f"Winners : {winner_list}")


def setup(bot):
    bot.add_cog(Lottery(bot))
