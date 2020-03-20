import datetime
import typing

import discord
import emojis
from discord.ext import commands

from zbot import checker
from zbot import converter
from zbot import database
from zbot import error_handler
from zbot import exceptions
from zbot import logger
from zbot import scheduler
from zbot import utils
from zbot import zbot
from . import command


class Poll(command.Command):

    """Commands for management of polls."""

    DISPLAY_NAME = "Sondages"
    DISPLAY_SEQUENCE = 4
    MOD_ROLE_NAMES = ['Administrateur', 'Modérateur']
    USER_ROLE_NAMES = ['Joueur']

    ANNOUNCE_ROLE_NAME = 'Abonné Annonces'
    EMBED_COLOR = 0x9D71DC  # Pastel purple
    JOBSTORE = database.MongoDBConnector.PENDING_POLLS_COLLECTION

    pending_polls = {}

    def __init__(self, bot):
        super().__init__(bot)
        zbot.db.load_pending_jobs_data(
            self.JOBSTORE,
            self.pending_polls,
            data_keys=(
                '_id', 'poll_id', 'message_id', 'channel_id', 'emoji_codes', 'next_run_time',
                'organizer_id', 'is_exclusive', 'required_role_name'
            )
        )
        for poll_data in self.pending_polls.values():
            logger.debug(f"Loaded pending poll data: {poll_data}")

    @commands.group(
        name='poll',
        invoke_without_command=True
    )
    @commands.guild_only()
    async def poll(self, context):
        if context.invoked_subcommand is None:
            raise exceptions.MissingSubCommand(context.command.name)

    @poll.command(
        name='start',
        aliases=['s'],
        usage="<\"announce\"> <\"description\"> <#dest_channel> <\":emoji1: :emoji2: ...\"> <\"time\"> "
              "[--exclusive] [--role=\"name\"] [--do-announce] [--pin]",
        brief="Démarre un sondage",
        help="Le bot publie un sondage sous forme d'un message correspondant à l'annonce et d'un "
             "embed contenant la description (qui peut être sur plusieurs lignes) dans le canal de "
             "destination. Les joueurs participent en cliquant sur le ou les émoji(s) de réaction. "
             "À la date et à l'heure indiquées (au format `\"YYYY-MM-DD HH:MM:SS\"`), les "
             "résultats sont affichés dans un second message. Par défaut, le sondage est à choix "
             "multiple et il n'y a aucune restriction de rôle. Pour changer cela, il faut "
             "respectivement ajouter les arguments `--exclusive` et `--role=\"Nom de rôle\"`. Pour "
             "automatiquement mentionner le rôle `@Abonné Annonces`, ajoutez l'argument "
             "`--do-announce`. Pour épingler automatiquement l'annonce, ajoutez l'argument `--pin`.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_user_role)
    async def start(
            self, context: commands.Context,
            announce: str,
            description: str,
            dest_channel: discord.TextChannel,
            emoji_list: converter.to_emoji_list,
            time: converter.to_datetime,
            *, options=None
    ):
        # Check arguments
        if not context.author.permissions_in(dest_channel).send_messages:
            raise commands.MissingPermissions([f"`send_messages` in {dest_channel.mention}"])
        if not emoji_list:
            raise commands.MissingRequiredArgument(context.command.params['emoji_list'])
        for emoji in emoji_list:
            if isinstance(emoji, str) and emojis.emojis.count(emoji) != 1:
                raise exceptions.ForbiddenEmoji(emoji)
        if (time - utils.get_current_time()).total_seconds() <= 0:
            argument_size = converter.humanize_datetime(time)
            min_argument_size = converter.humanize_datetime(utils.get_current_time())
            raise exceptions.UndersizedArgument(argument_size, min_argument_size)
        do_announce = utils.is_option_enabled(options, 'do-announce')
        do_pin = utils.is_option_enabled(options, 'pin')
        if do_announce or do_pin:
            checker.has_any_mod_role(context, print_error=True)
        required_role_name = utils.get_option_value(options, 'role')
        if required_role_name:
            utils.try_get(  # Raise if role does not exist
                context.guild.roles, error=exceptions.UnknownRole(required_role_name),
                name=required_role_name
            )

        # Run command
        is_exclusive = utils.is_option_enabled(options, 'exclusive')
        organizer = context.author
        prefixed_announce = utils.make_announce(
            context, announce, do_announce and self.ANNOUNCE_ROLE_NAME)
        embed = self.build_announce_embed(
            description, is_exclusive, required_role_name, organizer, time, context.guild.roles)
        message = await dest_channel.send(prefixed_announce, embed=embed)
        for emoji in emoji_list:
            await message.add_reaction(emoji)
        if do_pin:
            await message.pin()

        # Register data
        job_id = scheduler.schedule_job(self.JOBSTORE, time, self.run_poll, message.id).id
        poll_data = {
            'poll_id': self.get_next_poll_id(),
            'message_id': message.id,
            'channel_id': dest_channel.id,
            'emoji_codes': list(map(lambda e: e if isinstance(e, str) else e.id, emoji_list)),
            'organizer_id': organizer.id,
            'is_exclusive': is_exclusive,
            'required_role_name': required_role_name,
        }
        zbot.db.update_job_data(self.JOBSTORE, job_id, poll_data)
        # Add data managed by scheduler later to avoid updating the database with them
        poll_data.update({'_id': job_id, 'next_run_time': converter.to_timestamp(time)})
        self.pending_polls[message.id] = poll_data

        # Confirm command
        await context.send(f"Sondage d'identifiant `{poll_data['poll_id']}` programmé : <{message.jump_url}>.")
        await context.send(f"Sondage démarré.")

    @staticmethod
    def build_announce_embed(
            description, is_exclusive, required_role_name, organizer, time, guild_roles
    ):
        embed = discord.Embed(
            title=f"Clôture du sondage le {converter.humanize_datetime(time)} :alarm_clock:",
            description=description,
            color=Poll.EMBED_COLOR,
        )
        embed.add_field(
            name="Participation",
            value="Réagissez avec un émoji ci-dessous." if is_exclusive
            else "Réagissez avec les émojis ci-dessous."
        )
        embed.add_field(
            name="Choix multiple",
            value="✅" if not is_exclusive else "❌"
        )
        embed.add_field(
            name="Rôle requis",
            value=utils.try_get(
                guild_roles,
                error=exceptions.UnknownRole(required_role_name),
                name=required_role_name
            ).mention if required_role_name else "Aucun"
        )
        embed.set_author(
            name=f"Organisateur : @{organizer.display_name}",
            icon_url=organizer.avatar_url
        )
        return embed

    def get_next_poll_id(self) -> int:
        next_poll_id = 1
        for poll_data in self.pending_polls.values():
            poll_id = poll_data['poll_id']
            if poll_id >= next_poll_id:
                next_poll_id = poll_id + 1
        return next_poll_id

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        message = reaction.message
        message_id = message.id
        emoji = reaction.emoji
        if message_id in Poll.pending_polls:
            poll_emoji_codes = Poll.pending_polls[message_id]['emoji_codes']
            same_emoji = any([
                emoji == poll_emoji_code if isinstance(emoji, str) else emoji.id == poll_emoji_code
                for poll_emoji_code in poll_emoji_codes
            ])
            if same_emoji and not user.bot:
                if required_role_name := Poll.pending_polls[message_id]['required_role_name']:
                    if not checker.has_guild_role(message.channel.guild, user, required_role_name):
                        try:
                            await utils.try_dm(
                                user, f"Vous devez avoir le rôle @{required_role_name} pour "
                                      f"participer à ce sondage."
                            )
                            await message.remove_reaction(emoji, user)
                            return  # Don't enter other check blocks
                        except (
                                discord.errors.HTTPException,
                                discord.errors.NotFound,
                                discord.errors.Forbidden
                        ):
                            pass
                if Poll.pending_polls[message_id]['is_exclusive']:
                    for existing_reaction in list(filter(
                        lambda r: r.emoji != emoji and
                        (r.emoji if isinstance(r.emoji, str) else r.emoji.id) in poll_emoji_codes,
                        message.reactions
                    )):
                        existing_reaction_users = await existing_reaction.users().flatten()
                        if discord.utils.get(existing_reaction_users, id=user.id):
                            try:
                                await utils.try_dm(
                                    user, f"Vous ne pouvez voter que pour une seule option."
                                )
                                await message.remove_reaction(emoji, user)
                                return  # Don't enter other check blocks
                            except (discord.errors.HTTPException, discord.errors.NotFound, discord.errors.Forbidden):
                                pass
                            break

    @staticmethod
    async def run_poll(
            message_id, emoji_codes=(), organizer_id=None, is_exclusive_=None,
            required_role_name_=None, manual_run=False):
        poll_data = Poll.pending_polls[message_id]
        channel = zbot.bot.get_channel(poll_data['channel_id'])
        emoji_list = list(map(
            lambda c: utils.get_emoji(c, zbot.bot.emojis),
            emoji_codes or poll_data['emoji_codes']
        ))
        organizer = zbot.bot.get_user(organizer_id or poll_data['organizer_id'])
        is_exclusive = (is_exclusive_ is not None and is_exclusive_) or poll_data['is_exclusive']
        required_role_name = (required_role_name_ is not None and required_role_name_) \
            or poll_data['required_role_name']
        message = None
        try:
            message, reactions, results = await Poll.assess(
                channel, message_id, emoji_list, is_exclusive, required_role_name)
            for reaction in reactions:
                await reaction.remove(zbot.bot.user)
            await message.unpin()
            await Poll.announce_results(results, message, organizer, is_exclusive, required_role_name)
            Poll.remove_pending_poll(message_id, cancel_job=manual_run)
        except commands.CommandError as error:
            context = commands.Context(
                bot=zbot.bot,
                cog=Poll,
                prefix=zbot.bot.command_prefix,
                channel=channel,
                message=message,
            )
            await error_handler.handle(context, error)

    @poll.command(
        name='cancel',
        aliases=['c'],
        usage="<poll_id>",
        brief="Annule le sondage",
        help="Le numéro de sondage est affiché entre crochets par la commande `+poll list`.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_user_role)
    async def cancel(self, context: commands.Context, poll_id: int):
        message, _, emoji_list, _, _, _, organizer = await self.get_message_env(
            poll_id, raise_if_not_found=False)
        if organizer != context.author:
            checker.has_any_mod_role(context, print_error=True)
        if message:
            for emoji in emoji_list:
                reaction = utils.try_get(
                    message.reactions, error=exceptions.MissingEmoji(emoji), emoji=emoji
                )
                await reaction.remove(zbot.bot.user)
            embed = discord.Embed(
                title=f"Sondage __annulé__ par {context.author.display_name}",
                description=message.embeds[0].description if message.embeds[0].description else "",
                color=Poll.EMBED_COLOR
            )
            embed.set_author(name=f"Organisateur : @{organizer.display_name}", icon_url=organizer.avatar_url)
            await message.edit(embed=embed)
            await message.unpin()
        self.remove_pending_poll(message.id, cancel_job=True)
        await context.send(f"Sondage d'identifiant `{poll_id}` annulé.")

    @staticmethod
    async def get_message_env(poll_id: int, raise_if_not_found=True) -> \
            (discord.Message, discord.TextChannel, typing.List[typing.Union[str, discord.Emoji]],
             bool, bool, datetime.datetime, discord.Member):
        if not (res := list(
            filter(lambda data: data['poll_id'] == poll_id, Poll.pending_polls.values())
        )):
            raise exceptions.UnknownPoll(poll_id)
        poll_data = res[0]
        message_id = poll_data['message_id']
        channel = zbot.bot.get_channel(poll_data['channel_id'])
        emoji_codes = poll_data['emoji_codes']
        is_exclusive = poll_data['is_exclusive']
        required_role_name = poll_data['required_role_name']
        next_run_timestamp = poll_data['next_run_time']
        organizer = zbot.bot.get_user(poll_data['organizer_id'])

        message = await utils.try_get_message(
            channel, message_id,
            error=exceptions.MissingMessage(message_id) if raise_if_not_found else None
        )
        emoji_list = [utils.get_emoji(emoji_code, zbot.bot.emojis) for emoji_code in emoji_codes]
        time = converter.from_timestamp(next_run_timestamp)
        return message, channel, emoji_list, is_exclusive, required_role_name, time, organizer

    @staticmethod
    def remove_pending_poll(message_id, cancel_job=False):
        if message_id not in Poll.pending_polls:
            return  # Callback of misfired poll or manual run
        for poll_data in Poll.pending_polls.values():
            if poll_data['poll_id'] > Poll.pending_polls[message_id]['poll_id']:
                poll_data['poll_id'] -= 1
                zbot.db.update_job_data(
                    Poll.JOBSTORE,
                    poll_data['_id'],
                    {'poll_id': poll_data['poll_id']}
                )
        if cancel_job:
            scheduler.cancel_job(Poll.pending_polls[message_id]['_id'])
        del Poll.pending_polls[message_id]

    @poll.command(
        name='list',
        aliases=['l', 'ls'],
        brief="Affiche la liste des sondages en cours",
        ignore_extra=False
    )
    @commands.check(checker.has_any_user_role)
    async def list(self, context: commands.Context):
        poll_descriptions, guild_id = {}, context.guild.id
        for message_id, poll_data in self.pending_polls.items():
            poll_id = poll_data['poll_id']
            channel_id = poll_data['channel_id']
            organizer = context.guild.get_member(poll_data['organizer_id'])
            time = scheduler.get_job_run_date(poll_data['_id'])
            message_link = f"https://discordapp.com/channels/{guild_id}/{channel_id}/{message_id}"
            poll_descriptions[poll_id] = f" • `[{poll_id}]` - Démarré par {organizer.mention} " \
                f"jusqu'au [__{converter.humanize_datetime(time)}__]({message_link})"
        embed_description = "Aucun" if not poll_descriptions \
            else "\n".join([poll_descriptions[poll_id] for poll_id in sorted(poll_descriptions.keys())])
        embed = discord.Embed(
            title="Sondage(s) en cours",
            description=embed_description,
            color=self.EMBED_COLOR
        )
        await context.send(embed=embed)

    @staticmethod
    async def assess(channel, message_id, emoji_list, is_exclusive, required_role_name):
        message = await utils.try_get_message(
            channel, message_id, error=exceptions.MissingMessage(message_id))
        reactions = [
            utils.try_get(message.reactions, error=exceptions.MissingEmoji(emoji), emoji=emoji)
            for emoji in emoji_list
        ]
        results = await Poll.compute_results(channel, reactions, is_exclusive, required_role_name)
        return message, reactions, results

    @staticmethod
    async def compute_results(channel, reactions, is_exclusive, required_role_name) -> dict:
        votes = {reaction.emoji: await reaction.users().flatten() for reaction in reactions}
        results = {}
        for emoji, voters in votes.items():
            valid_votes_count = 0
            for voter in voters:
                if voter.bot:
                    continue  # Exclude bot votes
                if is_exclusive and any([voter in votes[other_emoji] for other_emoji in votes
                                         if other_emoji != emoji]):
                    continue  # Only count vote of voters having voted once in exclusive mode
                if required_role_name and not checker.has_guild_role(
                        channel.guild, voter, required_role_name
                ):
                    continue  # Only count vote of voters having the required role, if set
                valid_votes_count += 1
            results[emoji] = valid_votes_count
        return results

    @staticmethod
    async def announce_results(
            results: dict, message: discord.Message, organizer: discord.User, is_exclusive,
            required_role_name
    ):
        announcement_embed = discord.Embed(
            title="Résultats du sondage",
            description=f"[Cliquez ici pour accéder au sondage 🗳️]({message.jump_url})",
            color=Poll.EMBED_COLOR
        )
        # Compute ranking of votes count: {votes_count: position, votes_count: position, ...}
        votes_ranking = {k: v for v, k in enumerate(sorted(set(results.values()), reverse=True), start=1)}
        # Compute ranking of emojis: {emoji: position, emoji: position, ...}
        emoji_ranking = {emoji: votes_ranking[vote_count] for emoji, vote_count in results.items()}
        ranking_medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        for emoji, vote_count in results.items():
            rank = emoji_ranking[emoji]
            medal_message = f" {ranking_medals.get(rank, '')}" if vote_count > 0 else ""
            announcement_embed.add_field(
                name=f"{emoji}\u2000**# {rank}**",
                value=f"Votes: **{vote_count}**{medal_message}"
            )
        announcement_embed.set_author(
            name=f"Organisateur : @{organizer.display_name}", icon_url=organizer.avatar_url)
        announcement = await message.channel.send(embed=announcement_embed)

        embed = discord.Embed(
            title="Sondage clôturé",
            description=f"[Cliquez ici pour accéder aux résultats 📊]({announcement.jump_url})"
                        + (f"\n\n{message.embeds[0].description}"
                           if message.embeds[0].description else ""),
            color=Poll.EMBED_COLOR
        )
        embed.add_field(name="Choix multiple", value="✅" if not is_exclusive else "❌")
        embed.add_field(
            name="Rôle requis",
            value=utils.try_get(
                message.guild.roles,
                error=exceptions.UnknownRole(required_role_name),
                name=required_role_name
            ).mention if required_role_name else "Aucun"
        )
        embed.set_author(
            name=f"Organisateur : @{organizer.display_name}", icon_url=organizer.avatar_url)
        await message.edit(embed=embed)

        logger.debug(f"Poll results: {results}")


def setup(bot):
    bot.add_cog(Poll(bot))
