import datetime
import re
from copy import copy

import discord
import typing
from discord.ext import commands

from zbot import checker
from zbot import converter
from zbot import exceptions
from zbot import utils
from zbot import wot_utils
from zbot import zbot
from . import _command
from .bot import Bot
from .stats import Stats


class Admin(_command.Command):

    """Commands for administration and moderation of the server."""

    DISPLAY_NAME = "Administration"
    DISPLAY_SEQUENCE = 10
    MOD_ROLE_NAMES = ['Administrateur', 'Modérateur']
    USER_ROLE_NAMES = []

    PLAYER_ROLE_NAME = 'Joueur'
    BATCH_SIZE = 24
    RECRUITMENT_CHANNEL_ID = 427027398341558272
    MAX_RECRUITMENT_ANNOUNCE_LENGTH = 1200  # In characters
    MIN_RECRUITMENT_LINE_LENGTH = 100  # In characters
    MIN_RECRUITMENT_ANNOUNCE_TIMESPAN = 30  # In days
    RECRUITMENT_ANNOUNCE_TIMESPAN_TOLERANCE = 2  # In days
    WORK_IN_PROGRESS_EMOJI = '👀'
    WORK_DONE_EMOJI = '✅'

    def __init__(self, bot):
        super().__init__(bot)
        bot.loop.create_task(self.record_recruitment_announces())

    async def record_recruitment_announces(self):
        recruitment_channel = self.guild.get_channel(self.RECRUITMENT_CHANNEL_ID)
        recruitment_announces = await recruitment_channel.history().flatten()
        zbot.db.update_recruitment_announces(recruitment_announces)

    @commands.group(
        name='check',
        brief="Gère les checklists de modération",
        hidden=True,
        invoke_without_command=True
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def check(self, context):
        if not context.subcommand_passed:
            await Bot.display_group_help(context, context.command)
        else:
            raise exceptions.MissingSubCommand(context.command.name)

    @check.command(
        name='all',
        aliases=[],
        brief="Passe en revue toutes les checklists de modération",
        hidden=True,
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def check_all(self, context):
        await context.message.add_reaction(self.WORK_IN_PROGRESS_EMOJI)

        await self.check_everyone(context, add_reaction=False)
        await self.check_players(context, add_reaction=False)
        await self.check_contacts(context, add_reaction=False)
        await self.check_recruitments(context, add_reaction=False)

        await context.message.remove_reaction(self.WORK_IN_PROGRESS_EMOJI, self.user)
        await context.message.add_reaction(self.WORK_DONE_EMOJI)

    @check.command(
        name='everyone',
        aliases=[],
        brief="Passe en revue la checklist sur les membres du serveur",
        help="Pour chaque membre du serveur, il est vérifié que :\n"
             "• Le joueur possède au moins un rôle.\n"
             "• Le surnom ne comporte aucun tag de clan si le joueur n'est pas contact de clan.",
        hidden=True,
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def check_everyone(self, context, add_reaction=True):
        add_reaction and await context.message.add_reaction(self.WORK_IN_PROGRESS_EMOJI)

        await self.check_everyone_role(context, self.guild.members)
        await self.check_everyone_clan_tag(context, self.guild.members)

        add_reaction and await context.message.remove_reaction(self.WORK_IN_PROGRESS_EMOJI, self.user)
        add_reaction and await context.message.add_reaction(self.WORK_DONE_EMOJI)

    @staticmethod
    async def check_everyone_role(context, members):
        """Check that all members have at least one role."""
        # Ignore first role as it is @everyone
        if missing_role_members := list(filter(lambda m: len(m.roles) == 1, members)):
            for block in utils.make_message_blocks([
                f"Le joueur {member.mention} ne possède aucun rôle."
                for member in missing_role_members
            ]):
                await context.send(block)
        else:
            await context.send("Tous les joueurs ont au moins un rôle. :ok_hand: ")
        return missing_role_members

    @staticmethod
    async def check_everyone_clan_tag(context, members):
        """Check that no member has an unauthorized clan tag."""
        unauthorized_clan_tag_members = []
        for member in members:
            if re.search(r'[ ]*[\[{].{2,5}[]}][ ]*', member.display_name) and \
                    not checker.has_role(member, Stats.CLAN_CONTACT_ROLE_NAME):
                unauthorized_clan_tag_members.append(member)
        if unauthorized_clan_tag_members:
            for block in utils.make_message_blocks([
                f"Le joueur {member.mention} arbore un tag de clan sans être contact de clan."
                for member in unauthorized_clan_tag_members
            ]):
                await context.send(block)
        else:
            await context.send("Aucun joueur n'arbore de tag de clan sans être contact de clan. :ok_hand: ")
        return unauthorized_clan_tag_members

    @check.command(
        name='player',
        aliases=['players', 'joueur'],
        brief="Passe en revue la checklist sur les joueurs",
        help="Pour chaque joueur, il est vérifié que :\n"
             "• Le surnom corresponde a un pseudo WoT.\n"
             "• Il n'y a pas deux joueurs ayant le même surnom vérifié.",
        hidden=True,
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def check_players(self, context, add_reaction=True):
        add_reaction and await context.message.add_reaction(self.WORK_IN_PROGRESS_EMOJI)

        members = []
        for member in self.guild.members:
            if checker.has_role(member, self.PLAYER_ROLE_NAME):
                members.append(member)

        await self.check_players_matching_name(context, members, self.app_id)
        await self.check_players_unique_name(context, members)

        add_reaction and await context.message.remove_reaction(self.WORK_IN_PROGRESS_EMOJI, self.user)
        add_reaction and await context.message.add_reaction(self.WORK_DONE_EMOJI)

    @staticmethod
    async def check_players_matching_name(context, members, app_id):
        """Check that all players have a name matching with a player in WoT."""
        lower_case_matching_names = [
            name.lower() for name in wot_utils.get_players_info(
                [member.display_name for member in members], app_id
            ).keys()
        ]

        nonmatching_members = []
        for member in members:
            # Parse member name as player name with optional clan tag
            result = utils.PLAYER_NAME_PATTERN.match(member.display_name)
            if result:  # Member name fits, check if it has a match
                player_name = result.group(1)
                if player_name.lower() not in lower_case_matching_names:
                    nonmatching_members.append(member)
            else:  # Member name malformed, reject
                nonmatching_members.append(member)

        if nonmatching_members:
            for block in utils.make_message_blocks([
                f"Le joueur {member.mention} n'a pas de correspondance de pseudo sur WoT."
                for member in nonmatching_members
            ]):
                await context.send(block)
        else:
            await context.send("Tous les joueurs ont une correspondance de pseudo sur WoT. :ok_hand: ")
        return nonmatching_members

    @staticmethod
    async def check_players_unique_name(context, members):
        """Check that all players have a unique verified nickname."""
        members_by_name = {}
        for member in members:
            result = utils.PLAYER_NAME_PATTERN.match(member.display_name)
            if result:  # Malformed member names handled by check_players_matching_name
                member_name = result.group(1)
                members_by_name.setdefault(member_name, []).append(member)
        if duplicate_name_members := dict(filter(lambda i: len(i[1]) > 1, members_by_name.items())):
            for block in utils.make_message_blocks([
                f"Le pseudo vérifié **{member_name}** est utilisé par : "
                f"{', '.join([member.mention for member in colliding_members])}"
                for member_name, colliding_members in duplicate_name_members.items()
            ]):
                await context.send(block)
        else:
            await context.send("Aucun pseudo vérifié n'est utilisé par plus d'un joueur. :ok_hand: ")
        return duplicate_name_members

    @check.command(
        name='contact',
        aliases=['contacts'],
        brief="Passe en revue la checklist sur les contacts de clan",
        help="Pour chaque clan, il est vérifié que :\n"
             "• Le surnom du contact du clan contient le tag de celui-ci\n"
             "• Pas plus d'un contact ne représente le clan\n"
             "• Le contact du clan est toujours membre de celui-ci\n"
             "• Le contact du clan a toujours les permissions de recrutement au sein de celui-ci",
        hidden=True,
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def check_contacts(self, context, add_reaction=True):
        add_reaction and await context.message.add_reaction(self.WORK_IN_PROGRESS_EMOJI)

        contacts, contacts_by_clan = [], {}
        for member in self.guild.members:
            if checker.has_role(member, Stats.CLAN_CONTACT_ROLE_NAME):
                contacts.append(member)
                result = utils.PLAYER_NAME_PATTERN.match(member.display_name)
                if result:  # Malformed member names handled by check_players_matching_name
                    clan_tag = result.group(3)
                    if clan_tag:  # Missing clan tag handled by check_contacts_clan_tag
                        contacts_by_clan.setdefault(clan_tag, []).append(member)

        await self.check_contacts_clan_tag(context, contacts)
        await self.check_clans_single_contact(context, contacts_by_clan)
        await self.check_contacts_recruiting_permissions(context, contacts_by_clan, self.app_id)

        add_reaction and await context.message.remove_reaction(self.WORK_IN_PROGRESS_EMOJI, self.user)
        add_reaction and await context.message.add_reaction(self.WORK_DONE_EMOJI)

    @staticmethod
    async def check_contacts_clan_tag(context, contacts):
        """Check that all contacts have a clan tag."""
        missing_clan_tag_members = []
        for contact in contacts:
            result = utils.PLAYER_NAME_PATTERN.match(contact.display_name)
            if not result or not result.group(3):
                missing_clan_tag_members.append(contact)
        if missing_clan_tag_members:
            for block in utils.make_message_blocks([
                f"Le joueur {member.mention} n'arbore pas de tag de clan."
                for member in missing_clan_tag_members
            ]):
                await context.send(block)
        else:
            await context.send("Tous les contacts de clan arborent un tag de clan. :ok_hand: ")
        return missing_clan_tag_members

    @staticmethod
    async def check_clans_single_contact(context, contacts_by_clan):
        """Check that no clan has more than one contact."""
        if multiple_contact_clans := dict(filter(lambda i: len(i[1]) > 1, contacts_by_clan.items())):
            for block in utils.make_message_blocks([
                f"Le clan [{clan_tag}] est représenté par {len(contacts)} membres : "
                f"{', '.join([contact.mention for contact in contacts])}"
                for clan_tag, contacts in multiple_contact_clans.items()
            ]):
                await context.send(block)
        else:
            await context.send("Tous les clans représentés le sont par exactement un membre. :ok_hand: ")
        return multiple_contact_clans

    @staticmethod
    async def check_contacts_recruiting_permissions(context, contacts_by_clan, app_id):
        """Check that all clan contacts still have recruiting permissions."""
        disbanded_members, demoted_members = [], []
        for clan_tag, contacts in contacts_by_clan.items():
            for member in contacts:
                result = utils.PLAYER_NAME_PATTERN.match(member.display_name)
                if result:  # Malformed member names handled by check_players_matching_name
                    player_name = result.group(1)
                    _, player_id = wot_utils.get_exact_player_info(player_name, app_id)
                    if player_id:  # Non-matching name handled by Admin.check_players_matching_name
                        clan_member_infos = wot_utils.get_clan_member_infos(player_id, app_id)
                        real_clan_tag = clan_member_infos and clan_member_infos['tag']
                        clan_position = clan_member_infos and clan_member_infos['position']
                        if not clan_member_infos or real_clan_tag != clan_tag.upper():
                            disbanded_members.append((member, clan_tag))
                        elif clan_position not in [
                            "Commandant", "Commandant en second",
                            "Officier du personnel", "Recruteur"
                        ]:
                            demoted_members.append((member, real_clan_tag))
        if disbanded_members:
            for block in utils.make_message_blocks([
                f"Le joueur {member.mention} a quitté le clan [{clan_tag}]."
                for member, clan_tag in disbanded_members
            ]):
                await context.send(block)
        if demoted_members:
            for block in utils.make_message_blocks([
                f"Le joueur {member.mention} n'a pas les permissions de recrutement au sein du "
                f"clan [{real_clan_tag}]." for member, real_clan_tag in demoted_members
            ]):
                await context.send(block)
        if not disbanded_members and not demoted_members:
            await context.send(
                "Tous les contacts de clan ont encore leurs permissions de recrutement. :ok_hand: "
            )
        return disbanded_members, demoted_members

    @check.command(
        name='recruitment',
        aliases=['recruitments', 'recrutement', 'recrut'],
        usage="[\"after\"] [limit]",
        brief="Passe en revue la checklist sur les annonces de recrutement",
        help="Pour chaque annonce dans le canal #recrutement, il est vérifié que :\n"
             "• L'auteur de l'annonce possède le rôle @Contact de clan\n"
             "• L'auteur de l'annonce n'a pas publié d'autres annonces\n"
             "• La longueur de l'annonce est inférieure à 1200 caractères (min 100/ligne)\n"
             "• L'annonce ne contient aucun embed\n"
             "• L'annonce précédente du même auteur est antérieure à 30 jours\n"
             "La date `after` filtre les messages dans le temps et doit être au format "
             "`\"YYYY-MM-DD HH:MM:SS\"`\n"
             "Le nombre `limit` filtre les anciens messages pour ne garder que le nombre de "
             "messages plus récents spécifié (par défaut: 100).",
        hidden=True,
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def check_recruitments(
            self, context,
            after: converter.to_past_datetime = converter.to_datetime('1970-01-01'),
            limit: converter.to_positive_int = 100,
            add_reaction=True
    ):
        add_reaction and await context.message.add_reaction(self.WORK_IN_PROGRESS_EMOJI)

        recruitment_channel = self.guild.get_channel(self.RECRUITMENT_CHANNEL_ID)
        recruitment_announces = await recruitment_channel.history(
            after=after.replace(tzinfo=None),
            limit=limit,
            oldest_first=False  # Search in reverse in case the filters limit the results
        ).flatten()
        recruitment_announces.reverse()  # Reverse again to have oldest match in first place
        recruitment_announces = list(filter(
            lambda a: not checker.has_any_mod_role(context, a.author, print_error=False)  # Ignore moderation messages
            and not a.pinned  # Ignore pinned messages
            and not a.type.name == 'pins_add',  # Ignore pin notifications
            recruitment_announces
        ))

        await self.check_authors_clan_contact_role(context, recruitment_announces)
        await self.check_recruitment_announces_uniqueness(context, recruitment_announces)
        await self.check_recruitment_announces_length(context, recruitment_announces)
        await self.check_recruitment_announces_embeds(context, recruitment_announces)
        await self.check_recruitment_announces_timespan(context, recruitment_channel, recruitment_announces)

        add_reaction and await context.message.remove_reaction(self.WORK_IN_PROGRESS_EMOJI, self.user)
        add_reaction and await context.message.add_reaction(self.WORK_DONE_EMOJI)

    @staticmethod
    async def check_authors_clan_contact_role(context, announces):
        """Check that all announce authors have the clan contact role."""
        if missing_clan_contact_role_announces := list(filter(
                lambda a: not checker.has_guild_role(context.guild, a.author, Stats.CLAN_CONTACT_ROLE_NAME), announces
        )):
            for block in utils.make_message_blocks([
                f"{announce.author.mention} ne possède pas le rôle @{Stats.CLAN_CONTACT_ROLE_NAME} nécessaire à la "
                f"publication d'une annonce : {announce.jump_url}" for announce in missing_clan_contact_role_announces
            ]):
                await context.send(block)
        else:
            await context.send(
                f"Toutes les annonces de recrutement sont publiées par des @{Stats.CLAN_CONTACT_ROLE_NAME}. :ok_hand: "
            )
        return missing_clan_contact_role_announces

    @staticmethod
    async def check_recruitment_announces_uniqueness(context, announces):
        """Check that no two recruitment announces have the same author."""
        announces_by_author = {}
        for announce in announces:
            announces_by_author.setdefault(announce.author, []).append(announce)
        if duplicate_announces_by_author := dict(filter(lambda i: len(i[1]) > 1, announces_by_author.items())):
            message_link_separator = "\n"
            for block in utils.make_message_blocks([
                f"Le joueur {author.mention} a publié {len(announces)} annonces : \n"
                f"{message_link_separator.join([announce.jump_url for announce in announces])}"
                for author, announces in duplicate_announces_by_author.items()
            ]):
                await context.send(block)
        else:
            await context.send("Toutes les annonces de recrutement sont uniques. :ok_hand: ")
        return duplicate_announces_by_author

    @staticmethod
    async def check_recruitment_announces_length(context, announces):
        """Check that no recruitment announce is too long."""
        code_block_pattern = re.compile(r'^[^a-zA-Z0-9`]+```.*')
        too_long_announces = []
        for announce in announces:
            if (apparent_length := sum([
                max(len(line), Admin.MIN_RECRUITMENT_LINE_LENGTH)
                for line in announce.content.split('\n')
                if not code_block_pattern.match(line)  # Ignore line starting with code block statements
            ])) > Admin.MAX_RECRUITMENT_ANNOUNCE_LENGTH:
                too_long_announces.append((announce, apparent_length))
        if too_long_announces:
            await context.send(
                f"Les critères suivants sont utilisés :\n"
                f"• Chaque ligne compte comme ayant au moins **{Admin.MIN_RECRUITMENT_LINE_LENGTH}** caractères.\n"
                f"• La longueur apparente maximale est de **{Admin.MAX_RECRUITMENT_ANNOUNCE_LENGTH}** caractères.\n_ _")
            for block in utils.make_message_blocks([
                f"L'annonce de {announce.author.mention} est d'une longueur apparente de **{apparent_length}** "
                f"caractères (max {Admin.MAX_RECRUITMENT_ANNOUNCE_LENGTH}) : {announce.jump_url}"
                for announce, apparent_length in too_long_announces
            ]):
                await context.send(block)
        else:
            await context.send("Toutes les annonces de recrutement sont de longueur réglementaire. :ok_hand: ")
        return too_long_announces

    @staticmethod
    async def check_recruitment_announces_embeds(context, announces):
        """Check that no announce has an embed."""
        # Ignore line starting with code block statements
        discord_link_pattern = re.compile(r'discord(app)?\.(com|gg)')
        embedded_announces = []
        for announce in announces:
            # Include announces containing Discord links
            discord_link_count = len(discord_link_pattern.findall(announce.content))
            if announce.embeds or discord_link_count:
                embedded_announces.append((announce, len(announce.embeds) + discord_link_count))
        if embedded_announces:
            for block in utils.make_message_blocks([
                f"L'annonce de {announce.author.mention} contient {embed_count} embed(s) : {announce.jump_url}"
                for announce, embed_count in embedded_announces
            ]):
                await context.send(block)
        else:
            await context.send(
                f"Aucune annonce de recrutement ne contient d'embed. :ok_hand: "
            )
        return embedded_announces

    @staticmethod
    async def check_recruitment_announces_timespan(context, channel, announces):
        """Check that no announce is re-posted before a given timespan."""
        zbot.db.update_recruitment_announces(await channel.history().flatten())

        # Get records of all deleted announces
        # Still existing announces are handled by Admin.check_recruitment_announces_uniqueness
        author_last_announce_data = {}
        for announce_data in zbot.db.load_recruitment_announces_data(
            query={'_id': {'$nin': list(map(lambda a: a.id, announces))}},
            order=[('time', -1)],
        ):
            # Associate each author with his/her last delete announce data
            if announce_data['author'] not in author_last_announce_data:
                author_last_announce_data[announce_data['author']] = {
                    'time': announce_data['time'], 'message_id': announce_data['_id']
                }

        # Find all existing announces that have the same author as a recent (but deleted) announce
        min_timespan = datetime.timedelta(
            # Apply a tolerance of 2 days for players interpreting the 30 days range as "one month".
            # This is a subtraction because the resulting value is the number of days to wait before posting again.
            days=Admin.MIN_RECRUITMENT_ANNOUNCE_TIMESPAN - Admin.RECRUITMENT_ANNOUNCE_TIMESPAN_TOLERANCE
        )
        before_timespan_announces = []
        for announce in announces:
            if announce_data := author_last_announce_data.get(announce.author.id):
                previous_announce_time_localized = converter.to_utc(announce_data['time'])
                if previous_announce_time_localized \
                        <= converter.to_utc(announce.created_at) \
                        < previous_announce_time_localized + min_timespan:
                    before_timespan_announces.append((announce, previous_announce_time_localized))
        if before_timespan_announces:
            for block in utils.make_message_blocks([
                f"L'annonce de {announce.author.mention} a été postée avant le délai minimum de "
                f"{Admin.MIN_RECRUITMENT_ANNOUNCE_TIMESPAN} jours (dernière publication le "
                f"{converter.to_human_format(previous_announce_time)}). : {announce.jump_url}"
                for announce, previous_announce_time in before_timespan_announces
            ]):
                await context.send(block)
        else:
            await context.send(
                f"Aucune annonce n'a été publiée avant le délai minimum de {Admin.MIN_RECRUITMENT_ANNOUNCE_TIMESPAN} "
                f"jours. :ok_hand: "
            )
        return before_timespan_announces

    @commands.group(
        name='inspect',
        brief="Fourni le statut du suivi des aides à la modération",
        hidden=True,
        invoke_without_command=True
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def inspect(self, context):
        if not context.subcommand_passed:
            await Bot.display_group_help(context, context.command)
        else:
            raise exceptions.MissingSubCommand(context.command.name)

    @inspect.command(
        name='recruitment',
        aliases=['recruitments', 'recrutement', 'recrut'],
        usage="<@member>",
        brief="Fourni le statut du suivi des annonces de recrutement",
        help="Si un membre est fourni un argument, seul le suivi de ses annonces est fourni.",
        hidden=True,
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def inspect_recruitment(self, context, member: discord.Member = None):
        """Post the status of the recruitment announces monitoring."""
        recruitment_channel = self.guild.get_channel(self.RECRUITMENT_CHANNEL_ID)
        zbot.db.update_recruitment_announces(await recruitment_channel.history().flatten())

        # Get the record of each author's last announce (deleted or not)
        author_last_announce_data = {}
        for announce_data in zbot.db.load_recruitment_announces_data(
            query={'author': member.id} if member else {},
            order=[('time', -1)]
        ):
            # Associate each author with his/her last announce data
            if announce_data['author'] not in author_last_announce_data:
                author_last_announce_data[announce_data['author']] = {
                    'last_announce_time': announce_data['time'], 'message_id': announce_data['_id']
                }

        # Enhance announces data with additional information
        min_timespan = datetime.timedelta(
            # Apply a tolerance of 2 days for players interpreting the 30 days range as "one month".
            # This is a subtraction because the resulting value is the number of days to wait before posting again.
            days=self.MIN_RECRUITMENT_ANNOUNCE_TIMESPAN - self.RECRUITMENT_ANNOUNCE_TIMESPAN_TOLERANCE
        )
        today = utils.bot_tz_now()
        for author_id, announce_data in author_last_announce_data.items():
            last_announce_time_localized = converter.to_utc(announce_data['last_announce_time'])
            next_announce_time_localized = last_announce_time_localized + min_timespan
            author_last_announce_data[author_id] = {
                'last_announce_time': last_announce_time_localized,
                'next_announce_time': next_announce_time_localized,
                'is_time_elapsed': next_announce_time_localized <= today
            }

        # Bind the member to the announce data and order by date asc
        member_announce_data = {
            self.guild.get_member(author_id): _ for author_id, _ in author_last_announce_data.items()
        }
        filtered_member_announce_data = {
            author: _ for author, _ in member_announce_data.items() if author is not None  # Still member of the server
            and not checker.has_any_mod_role(context, author, print_error=False)  # Ignore moderation messages
        }
        ordered_member_announce_data = sorted(
            filtered_member_announce_data.items(), key=lambda elem: elem[1]['last_announce_time']
        )

        # Post the status of announces data
        await context.send("Statut du suivi des annonces de recrutement :")
        for block in utils.make_message_blocks([
            f"• {author.mention} : {converter.to_human_format(announce_data['last_announce_time'])} "
            + ("✅" if announce_data['is_time_elapsed']
                else f"⏳ (→ {converter.to_human_format(announce_data['next_announce_time'])})")
            for author, announce_data in ordered_member_announce_data
        ]):
            await context.send(block or "Aucun suivi enregistré.")

    @commands.group(
        name='report',
        brief="Gère les aides à la modération",
        hidden=True,
        invoke_without_command=True
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def report(self, context):
        if not context.subcommand_passed:
            await Bot.display_group_help(context, context.command)
        else:
            raise exceptions.MissingSubCommand(context.command.name)

    send_buffer = []  # Serves as a buffer for the message sent to the context

    @staticmethod
    async def mock_send(content=None, *_args, **_kwargs):
        """Catch all messages sent to the context whose `send` method has been matched with this."""
        Admin.send_buffer.append(content)

    @report.command(
        name='recruitment',
        aliases=['recruitments', 'recrutement', 'recrut'],
        usage="<@member|announce_id> [--clear]",
        brief="Modère une annonce de recrutement",
        help="Si un membre est fourni un argument, sa dernière annonce de recrutement est sélectionnée.\n"
             "Pour l'annonce de recrutement trouvée, si un problème est détecté :\n"
             "1. L'auteur de l'annonce reçoit le rapport d'analyse, le nom du modérateur et une "
             "copie du rendu de son annonce.\n"
             "2. Le modérateur reçoit une copie du rapport.\n"
             "3. L'annonce est supprimée.\n"
             "4. Si l'argument `--clear` est fourni, le suivi des annonces est remis à zéro.",
        hidden=True,
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def report_recruitment(self, context, target: typing.Union[discord.Member, int], *, options=""):
        recruitment_channel = self.guild.get_channel(self.RECRUITMENT_CHANNEL_ID)
        if isinstance(target, discord.Member):
            author = target
            all_recruitment_announces = await recruitment_channel.history().flatten()
            recruitment_announce = utils.try_get(all_recruitment_announces, author=author)
        else:
            announce_id = target
            recruitment_announce = await utils.try_get_message(
                recruitment_channel, announce_id, error=exceptions.MissingMessage(announce_id)
            )
            author = recruitment_announce.author
        clear = utils.is_option_enabled(options, 'clear')

        # Run checks

        patched_context = copy(context)
        patched_context.send = Admin.mock_send
        Admin.send_buffer.clear()
        await self.check_authors_clan_contact_role(patched_context, [recruitment_announce]) \
            or Admin.send_buffer.pop()
        await self.check_recruitment_announces_uniqueness(patched_context, [recruitment_announce]) \
            or Admin.send_buffer.pop()
        await self.check_recruitment_announces_length(patched_context, [recruitment_announce]) \
            or Admin.send_buffer.pop()
        await self.check_recruitment_announces_embeds(patched_context, [recruitment_announce]) \
            or Admin.send_buffer.pop()
        await self.check_recruitment_announces_timespan(patched_context, recruitment_channel, [recruitment_announce]) \
            or Admin.send_buffer.pop()

        if not Admin.send_buffer:
            await context.send(f"L'annonce ne présente aucun problème. :ok_hand: ")
        else:
            # DM author
            await utils.try_dm(
                author,
                f"Bonjour. Il a été détecté que ton annonce de recrutement ne respectait pas le "
                f"règlement du serveur. Voici un rapport de l'analyse effectuée: \n _ _"
            )
            await utils.try_dms(author, Admin.send_buffer, group_in_blocks=True)
            await utils.try_dm(
                author,
                f"_ _ \n"
                f"En attendant que le problème soit réglé, ton annonce a été supprimée.\n"
                f"En cas de besoin, tu peux contacter {context.author.mention} qui a reçu une copie du "
                f"rapport d'analyse.\n _ _"
            )
            await utils.try_dm(
                author,
                f"Copie du contenu de l'annonce:\n _ _ \n"
                f">>> {recruitment_announce.content}"
            )

            # DM moderator
            await utils.try_dm(context.author, f"Rapport d'analyse envoyé à {author.mention}: \n _ _")
            await utils.try_dms(context.author, Admin.send_buffer, group_in_blocks=True)
            await utils.try_dm(
                context.author,
                f"_ _ \n"
                f"Copie du contenu de l'annonce:\n _ _ \n"
                f">>> {recruitment_announce.content}"
            )

            # Delete announce
            await recruitment_announce.delete()
            await context.send(f"L'annonce a été supprimée et un rapport envoyé par MP. :ok_hand: ")

            # Clear announce tracking records
            if clear:
                await self.clear_recruitment(context, author)

    @commands.group(
        name='clear',
        brief="Remet à zéro le suivi des aides à la modération",
        hidden=True,
        invoke_without_command=True
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def clear(self, context):
        if not context.subcommand_passed:
            await Bot.display_group_help(context, context.command)
        else:
            raise exceptions.MissingSubCommand(context.command.name)

    @clear.command(
        name='recruitment',
        aliases=['recruitments', 'recrutement', 'recrut'],
        usage="<@member> [\"time\"]",
        brief="Remet à zéro le suivi des annonces de recrutement",
        help="L'historique des annonces de recrutement du membre fourni est remis à zéro. Si une date est fournie (au "
             "format `\"YYYY-MM-DD\"`), il ne sera possible au membre de ne poster une nouvelle annonce de "
             "recrutement qu'à partir de cette date.",
        hidden=True,
        ignore_extra=True
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def clear_recruitment(self, context, member: discord.Member, time: converter.to_datetime = None):
        zbot.db.delete_recruitment_announces({'author': member.id})
        if time:
            zbot.db.insert_recruitment_announce(
                member, time - datetime.timedelta(days=self.MIN_RECRUITMENT_ANNOUNCE_TIMESPAN)
            )
        await context.send(
            f"Le suivi des annonces de recrutement de {member.mention} a été remis à zéro."
            + ("" if not time else f"\nBlocage des nouvelles annonces jusqu'au {converter.to_human_format(time)}")
        )


def setup(bot):
    bot.add_cog(Admin(bot))
