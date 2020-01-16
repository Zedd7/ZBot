import datetime
import os
import re
import sys

import requests
from discord.ext import commands

from zbot import checker
from zbot import converter
from zbot import exceptions
from zbot import logger
from zbot import utils
from zbot import zbot
from . import command
from .stats import Stats


class Admin(command.Command):

    DISPLAY_NAME = "Administration"
    DISPLAY_SEQUENCE = 10
    MAIN_COMMAND_NAME = 'admin'
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
        super(Admin, self).__init__(bot)
        self.app_id = os.getenv('WG_API_APPLICATION_ID') or 'demo'
        recruitment_channel = bot.get_channel(self.RECRUITMENT_CHANNEL_ID)
        bot.loop.create_task(zbot.db.update_recruitment_announces(recruitment_channel))

    @commands.group(
        name=MAIN_COMMAND_NAME,
        invoke_without_command=True
    )
    @commands.guild_only()
    async def admin(self, context):
        if context.invoked_subcommand is None:
            raise exceptions.MissingSubCommand(context.command.name)

    @admin.group(
        name='check',
        invoke_without_command=True
    )
    @commands.guild_only()
    async def check(self, context):
        if context.invoked_subcommand is None:
            raise exceptions.MissingSubCommand(f'{self.MAIN_COMMAND_NAME} {context.command.name}')

    @check.command(
        name='everyone',
        aliases=['tous'],
        brief="Effectue une batterie de tests sur les membres du serveur",
        help="Pour chaque membre du serveur, il est vérifié que :\n"
             "• Le joueur possède au moins un rôle.\n"
             "• Le surnom ne comporte aucun tag de clan si le joueur n'est pas contact de clan.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def check_everyone(self, context):
        await context.message.add_reaction(self.WORK_IN_PROGRESS_EMOJI)

        await self.check_everyone_role(context, context.guild.members)
        await self.check_everyone_clan_tag(context, context.guild.members)

        await context.message.remove_reaction(self.WORK_IN_PROGRESS_EMOJI, self.user)
        await context.message.add_reaction(self.WORK_DONE_EMOJI)

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

    @staticmethod
    async def check_everyone_clan_tag(context, members):
        """Check that no member has an unauthorized clan tag."""
        unauthorized_clan_tag_members = []
        for member in members:
            if re.search(r' *[\[{].{2,5}[\]}] *', member.display_name) and \
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

    @check.command(
        name='player',
        aliases=['players', 'joueur'],
        brief="Effectue une batterie de tests sur les joueurs",
        help="Pour chaque joueur, il est vérifié que :\n"
             "• Le surnom corresponde a un pseudo WoT.\n"
             "• Il n'y a pas deux joueurs ayant le même surnom vérifié.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def check_players(self, context):
        await context.message.add_reaction(self.WORK_IN_PROGRESS_EMOJI)

        members = []
        for member in context.guild.members:
            if checker.has_role(member, self.PLAYER_ROLE_NAME):
                members.append(member)

        await self.check_players_matching_name(context, members, self.app_id)
        await self.check_players_unique_name(context, members)

        await context.message.remove_reaction(self.WORK_IN_PROGRESS_EMOJI, self.user)
        await context.message.add_reaction(self.WORK_DONE_EMOJI)

    @staticmethod
    async def check_players_matching_name(context, members, app_id):
        """Check that all players have a matching player name on WoT."""

        def _batch(_array, _batch_size):
            """ Split an array into an iterable of constant-size batches. """
            for _i in range(0, len(_array), _batch_size):
                yield _array[_i:_i+_batch_size]

        unmatched_name_members = []
        for member_batch in _batch(members, Admin.BATCH_SIZE):
            # Replace forbidden characters in player names
            member_names = [re.sub(r'[^0-9a-zA-Z_]', r'', member.display_name.split(' ')[0]) for member in member_batch]
            # Exclude fully non-matching (empty) names
            member_names = filter(lambda name: name != '', member_names)
            payload = {
                'application_id': app_id,
                'search': ','.join(member_names),
                'type': 'exact',
            }
            response = requests.get('https://api.worldoftanks.eu/wot/account/list/', params=payload)
            response_content = response.json()
            matched_names = [
                player_data['nickname'] for player_data in response_content['data']
            ] if response_content['status'] == 'ok' else []
            unmatched_name_members += list(filter(
                lambda m: m.display_name.split(' ')[0].lower() not in [
                    matched_name.lower() for matched_name in matched_names
                ], member_batch))
        if unmatched_name_members:
            for block in utils.make_message_blocks([
                f"Le joueur {member.mention} n'a pas de correspondance de pseudo sur WoT."
                for member in unmatched_name_members
            ]):
                await context.send(block)
        else:
            await context.send("Tous les joueurs ont une correspondance de pseudo sur WoT. :ok_hand: ")

    @staticmethod
    async def check_players_unique_name(context, members):
        """Check that all players have a unique verified nickname."""
        members_by_name = {}
        for member in members:
            member_name = member.display_name.split(' ')[0]
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

    @check.command(
        name='contact',
        aliases=['contacts'],
        brief="Effectue une batterie de tests sur les contacts de clan",
        help="Pour chaque clan, il est vérifié que :\n"
             "• Le surnom du contact du clan contient le tag de celui-ci\n"
             "• Pas plus d'un contact ne représente le clan\n"
             "• Le contact du clan est toujours membre de celui-ci\n"
             "• Le contact du clan a toujours les permissions de recrutement au sein de celui-ci",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def check_contacts(self, context):
        await context.message.add_reaction(self.WORK_IN_PROGRESS_EMOJI)

        contacts_by_clan = {}
        for member in context.guild.members:
            if checker.has_role(member, Stats.CLAN_CONTACT_ROLE_NAME):
                clan_tag = member.display_name.split(' ')[-1]
                # Remove clan tag delimiters
                replacements = {(re.escape(char)): '' for char in ['[', ']']}
                pattern = re.compile('|'.join(replacements.keys()))
                clan_tag = pattern.sub(lambda m: replacements[re.escape(m.group(0))], clan_tag)
                contacts_by_clan.setdefault(clan_tag, []).append(member)
        contacts = set([contact for contacts in contacts_by_clan.values() for contact in contacts])

        await self.check_contacts_clan_tag(context, contacts)
        await self.check_clans_single_contact(context, contacts_by_clan)
        await self.check_contacts_recruiting_permissions(context, contacts_by_clan, self.app_id)

        await context.message.remove_reaction(self.WORK_IN_PROGRESS_EMOJI, self.user)
        await context.message.add_reaction(self.WORK_DONE_EMOJI)

    @staticmethod
    async def check_contacts_clan_tag(context, contacts):
        """Check that all contacts have a clan tag."""
        if missing_clan_tag_members := list(filter(lambda c: ' ' not in c.display_name, contacts)):
            for block in utils.make_message_blocks([
                f"Le joueur {member.mention} n'arbore pas de tag de clan."
                for member in missing_clan_tag_members
            ]):
                await context.send(block)
        else:
            await context.send("Tous les contacts de clan arborent un tag de clan. :ok_hand: ")

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

    @staticmethod
    async def check_contacts_recruiting_permissions(context, contacts_by_clan, app_id):
        """Check that all clan contacts still have recruiting permissions."""
        disbanded_members, demoted_members = [], []
        for clan_tag, contacts in contacts_by_clan.items():
            for member in contacts:
                if ' ' in member.display_name:  # Missing clan tag handled by Admin.check_contacts_clan_tag
                    player_name = member.display_name.split(' ')[0]
                    player_id, _ = await Stats.get_player_id(player_name, app_id)
                    if player_id:  # Non-matching name handled by Admin.check_players_matching_name
                        clan_member_infos = await Stats.get_clan_member_infos(player_id, app_id)
                        real_clan_tag = clan_member_infos and clan_member_infos['tag']
                        clan_position = clan_member_infos and clan_member_infos['position']
                        if not clan_member_infos or real_clan_tag != clan_tag.upper():
                            disbanded_members.append((member, clan_tag))
                        elif clan_position not in ["Commandant", "Commandant en second", "Officier du personnel", "Recruteur"]:
                            demoted_members.append((member, real_clan_tag))
                            await context.send(f"Le joueur {member.mention} n'a plus les permissions "
                                               f"de recrutement au sein du clan [{real_clan_tag}].")
        if disbanded_members:
            for block in utils.make_message_blocks([
                f"Le joueur {member.mention} a quitté le clan [{clan_tag}]."
                for member, clan_tag in disbanded_members
            ]):
                await context.send(block)
        if demoted_members:
            for block in utils.make_message_blocks([
                f"Le joueur {member.mention} n'a plus les permissions de recrutement au sein du clan [{real_clan_tag}]."
                for member, real_clan_tag in demoted_members
            ]):
                await context.send(block)
        if not disbanded_members and not demoted_members:
            await context.send("Tous les contacts de clan ont encore leurs permissions de recrutement. :ok_hand: ")

    @check.command(
        name='recruitment',
        aliases=['recruitments', 'recrutement', 'recrut'],
        usage="[\"after\"] [limit]",
        brief="Vérifie la conformité des annonces de recrutement",
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
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def check_recruitments(
            self, context,
            after: converter.to_datetime = converter.to_datetime('1970-01-01'),
            limit: int = 100):
        if limit < 1:
            raise exceptions.UndersizedArgument(limit, 1)
        if (utils.get_current_time() - after).total_seconds() <= 0:
            argument_size = converter.humanize_datetime(after)
            max_argument_size = converter.humanize_datetime(utils.get_current_time())
            raise exceptions.OversizedArgument(argument_size, max_argument_size)

        await context.message.add_reaction(self.WORK_IN_PROGRESS_EMOJI)

        recruitment_channel = context.guild.get_channel(self.RECRUITMENT_CHANNEL_ID)
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

        await context.message.remove_reaction(self.WORK_IN_PROGRESS_EMOJI, self.user)
        await context.message.add_reaction(self.WORK_DONE_EMOJI)

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

    @staticmethod
    async def check_recruitment_announces_timespan(context, channel, announces):
        """Check that no announce is re-posted before a given timespan."""
        await zbot.db.update_recruitment_announces(channel)

        # Get records of all deleted announces.
        # Still existing announce handled by Admin.check_recruitment_announces_uniqueness
        announces_data_by_author = {}
        for announce_data in zbot.db.load_recruitment_announces_data(
            query={'_id': {'$nin': list(map(lambda a: a.id, announces))}},
            order=[('time', -1)],
        ):
            announces_data_by_author.setdefault(announce_data['author'], []).append(
                {'time': announce_data['time'], 'message_id': announce_data['_id']}
            )

        # Find all existing announces that have the same author as a recent but deleted announce
        min_timespan = datetime.timedelta(
            # Apply a tolerance of 2 days as some players will interpret the 30 days range as "one month".
            days=Admin.MIN_RECRUITMENT_ANNOUNCE_TIMESPAN - Admin.RECRUITMENT_ANNOUNCE_TIMESPAN_TOLERANCE
        )
        before_timespan_announces = []
        for announce in announces:
            for announce_data in announces_data_by_author.get(announce.author.id, []):
                previous_announce_time = announce_data['time']
                if previous_announce_time + min_timespan > announce.created_at:
                    before_timespan_announces.append((announce, previous_announce_time))
        if before_timespan_announces:
            for block in utils.make_message_blocks([
                f"L'annonce de {announce.author.mention} a été postée avant le délai minimum de "
                f"{Admin.MIN_RECRUITMENT_ANNOUNCE_TIMESPAN} jours (dernière publication le "
                f"{converter.humanize_datetime(previous_announce_time)}). : {announce.jump_url}"
                for announce, previous_announce_time in before_timespan_announces
            ]):
                await context.send(block)
        else:
            await context.send(f"Aucune annonce n'a été publiée avant le délai minimum de "
                               f"{Admin.MIN_RECRUITMENT_ANNOUNCE_TIMESPAN} jours. :ok_hand: ")

    @admin.command(
        name='logout',
        aliases=['stop', 'disconnect'],
        brief="Déconnecte le bot",
        help="Force le bot à se déconnecter du serveur sans arrêter le processus.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def logout(self, context):
        logger.info("Logging out...")
        await context.send(f"Déconnexion.")
        await self.bot.logout()
        sys.exit()


def setup(bot):
    bot.add_cog(Admin(bot))
