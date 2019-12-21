import os
import re
import sys

import requests
from discord.ext import commands

from zbot import checker
from zbot import exceptions
from zbot import logger
from zbot import utils
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
    WORK_IN_PROGRESS_EMOJI = '👀'
    WORK_DONE_EMOJI = '✅'

    def __init__(self, bot):
        super(Admin, self).__init__(bot)
        self.app_id = os.getenv('WG_API_APPLICATION_ID') or 'demo'

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
            raise exceptions.MissingSubCommand(context.command.name)

    @check.command(
        name='everyone',
        brief="Effectue une batterie de tests sur les membres du serveur",
        help="Pour chaque membre du serveur, il est vérifié que :\n"
             "• Le joueur possède au moins un rôle.\n"
             "• Le surnom ne comporte aucun tag de clan si le joueur n'est pas contact de clan.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def everyone(self, context):
        await context.message.add_reaction(self.WORK_IN_PROGRESS_EMOJI)

        await self.have_members_any_role(context, context.guild.members)
        await self.have_members_unauthorized_clan_tags(context, context.guild.members)

        await context.message.remove_reaction(self.WORK_IN_PROGRESS_EMOJI, self.user)
        await context.message.add_reaction(self.WORK_DONE_EMOJI)

    @staticmethod
    async def have_members_any_role(context, members):
        """Check that all members have at least one role."""
        # Ignore first role as it is @everyone
        missing_role_members = list(filter(lambda m: len(m.roles) == 1, members))  # TODO use Python 3.8's walrus operator
        if missing_role_members:
            for block in await utils.make_message_blocks([
                f"Le joueur {member.mention} ne possède aucun rôle."
                for member in missing_role_members
            ]):
                await context.send(block)
        else:
            await context.send("Tous les joueurs ont au moins un rôle. :ok_hand: ")

    @staticmethod
    async def have_members_unauthorized_clan_tags(context, members):
        """Check whether any member has an unauthorized clan tag."""
        unauthorized_clan_tag_members = []
        for member in members:
            if re.search(r' *[\[{].{2,5}[\]}] *', member.display_name) and \
                    not await checker.has_role(member, Stats.CLAN_CONTACT_ROLE_NAME):
                unauthorized_clan_tag_members.append(member)
        if unauthorized_clan_tag_members:
            for block in await utils.make_message_blocks([
                f"Le joueur {member.mention} arbore un tag de clan sans être contact de clan."
                for member in unauthorized_clan_tag_members
            ]):
                await context.send(block)
        else:
            await context.send("Aucun joueur n'arbore de tag de clan sans être contact de clan. :ok_hand: ")

    @check.command(
        name='joueur',
        brief="Effectue une batterie de tests sur les joueurs",
        help="Pour chaque joueur, il est vérifié que :\n"
             "• Le surnom corresponde a un pseudo WoT.\n"
             "• Il n'y a pas deux joueurs ayant le même surnom vérifié.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def joueur(self, context):
        await context.message.add_reaction(self.WORK_IN_PROGRESS_EMOJI)

        members = []
        for member in context.guild.members:
            if await checker.has_role(member, self.PLAYER_ROLE_NAME):
                members.append(member)
        await self.have_players_matching_names(context, members, self.app_id)
        await self.have_players_unique_names(context, members)

        await context.message.remove_reaction(self.WORK_IN_PROGRESS_EMOJI, self.user)
        await context.message.add_reaction(self.WORK_DONE_EMOJI)

    @staticmethod
    async def have_players_matching_names(context, members, app_id):
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
            for block in await utils.make_message_blocks([
                f"Le joueur {member.mention} n'a pas de correspondance de pseudo sur WoT."
                for member in unmatched_name_members
            ]):
                await context.send(block)
        else:
            await context.send("Tous les joueurs ont une correspondance de pseudo sur WoT. :ok_hand: ")

    @staticmethod
    async def have_players_unique_names(context, members):
        """Check that all players have a unique verified nickname."""
        members_by_name = {}
        for member in members:
            member_name = member.display_name.split(' ')[0]
            members_by_name.setdefault(member_name, []).append(member)
        duplicate_name_members = dict(filter(lambda i: len(i[1]) > 1, members_by_name.items()))  # TODO use Python 3.8's walrus operator
        if duplicate_name_members:
            for block in await utils.make_message_blocks([
                f"Le pseudo vérifié **{member_name}** est utilisé par : "
                f"{', '.join([member.mention for member in colliding_members])}"
                for member_name, colliding_members in duplicate_name_members.items()
            ]):
                await context.send(block)
        else:
            await context.send("Aucun pseudo vérifié n'est utilisé par plus d'un joueur. :ok_hand: ")

    @check.command(
        name='contact',
        brief="Effectue une batterie de tests sur les contacts de clan",
        help="Pour chaque clan, il est vérifié que :\n"
             "• Le surnom du contact du clan contient le tag de celui-ci\n"
             "• Pas plus d'un contact ne représente le clan\n"
             "• Le contact du clan est toujours membre de celui-ci\n"
             "• Le contact du clan a toujours les permissions de recrutement au sein de celui-ci",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def contact(self, context):
        await context.message.add_reaction(self.WORK_IN_PROGRESS_EMOJI)

        contacts_by_clan = {}
        for member in context.guild.members:
            if await checker.has_role(member, Stats.CLAN_CONTACT_ROLE_NAME):
                clan_tag = member.display_name.split(' ')[-1]
                # Remove clan tag delimiters
                replacements = {(re.escape(char)): '' for char in ['[', ']']}
                pattern = re.compile('|'.join(replacements.keys()))
                clan_tag = pattern.sub(lambda m: replacements[re.escape(m.group(0))], clan_tag)
                contacts_by_clan.setdefault(clan_tag, []).append(member)
        contacts = set([contact for contacts in contacts_by_clan.values() for contact in contacts])
        await self.have_contacts_clan_tag(context, contacts)
        await self.has_clan_multiple_contacts(context, contacts_by_clan)
        await self.have_contacts_recruiting_permissions(context, contacts_by_clan, self.app_id)

        await context.message.remove_reaction(self.WORK_IN_PROGRESS_EMOJI, self.user)
        await context.message.add_reaction(self.WORK_DONE_EMOJI)

    @staticmethod
    async def have_contacts_clan_tag(context, contacts):
        """Check that all contacts have a clan tag."""
        missing_clan_tag_members = list(filter(lambda c: ' ' not in c.display_name, contacts))  # TODO use Python 3.8's walrus operator
        if missing_clan_tag_members:
            for block in await utils.make_message_blocks([
                f"Le joueur {member.mention} n'arbore pas de tag de clan."
                for member in missing_clan_tag_members
            ]):
                await context.send(block)
        else:
            await context.send("Tous les contacts de clan arborent un tag de clan. :ok_hand: ")

    @staticmethod
    async def has_clan_multiple_contacts(context, contacts_by_clan):
        """Check whether a clan has more than one contact."""
        multiple_contact_clans = dict(filter(lambda i: len(i[1]) > 1, contacts_by_clan.items()))  # TODO use Python 3.8's walrus operator
        if multiple_contact_clans:
            for block in await utils.make_message_blocks([
                f"Le clan [{clan_tag}] est représenté par {len(contacts)} membres : "
                f"{', '.join([contact.mention for contact in contacts])}"
                for clan_tag, contacts in multiple_contact_clans.items()
            ]):
                await context.send(block)
        else:
            await context.send("Tous les clans représentés le sont par exactement un membre. :ok_hand: ")

    @staticmethod
    async def have_contacts_recruiting_permissions(context, contacts_by_clan, app_id):
        """Check that clan contacts still have the required clan position."""
        disbanded_members, demoted_members = [], []
        for clan_tag, contacts in contacts_by_clan.items():
            for member in contacts:
                if ' ' in member.display_name:  # Missing clan tag handled by Admin.have_contacts_clan_tag
                    player_name = member.display_name.split(' ')[0]
                    player_id, _ = await Stats.get_player_id(player_name, app_id)
                    if player_id:  # Non-matching name handled by Admin.have_players_matching_names
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
                f"Le joueur {member.mention} n'a plus les permissions "
                f"de recrutement au sein du clan [{real_clan_tag}]."
                for member, real_clan_tag in demoted_members
            ]):
                await context.send(block)
        if not disbanded_members and not demoted_members:
            await context.send("Tous les contacts de clan ont encore leur permissions de recrutement. :ok_hand: ")

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
