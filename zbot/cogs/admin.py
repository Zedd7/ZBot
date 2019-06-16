import os
import re
import sys

import requests
from discord.ext import commands

from zbot import checker
from zbot import exceptions
from zbot import logger
from . import command
from .stats import Stats


class Admin(command.Command):

    DISPLAY_NAME = "Administration"
    DISPLAY_SEQUENCE = 10
    MAIN_COMMAND_NAME = 'admin'
    MOD_ROLE_NAMES = ['Administrateur', 'Modérateur']
    USER_ROLE_NAMES = []
    PLAYER_ROLE_NAME = 'Joueur'
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
             "• Le surnom ne comporte aucun tag de clan si le joueur n'est pas contact de clan.",
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    async def everyone(self, context):
        await context.message.add_reaction(self.WORK_IN_PROGRESS_EMOJI)

        await self.have_members_unhautorized_clan_tags(context, context.guild.members)

        await context.message.remove_reaction(self.WORK_IN_PROGRESS_EMOJI, self.user)
        await context.message.add_reaction(self.WORK_DONE_EMOJI)

    @staticmethod
    async def have_members_unhautorized_clan_tags(context, members):
        """Check whether any member has an unauthorized clan tag."""
        unhautorized_clan_tags = False
        for member in members:
            if re.search(r" *[\[{].{2,5}[\]}] *", member.display_name) and \
                    not await checker.has_role(member, Stats.CLAN_CONTACT_ROLE_NAME):
                unhautorized_clan_tags = True
                await context.send(f"Le joueur {member.mention} arbore un tag de clan sans être contact de clan.")
        if not unhautorized_clan_tags:
            await context.send("Aucun membre du serveur n'arbore de tag de clan sans être contact de clan. :ok_hand: ")

    @check.command(
        name='joueur',
        brief="Effectue une batterie de tests sur les joueurs",
        help="Pour chaque joueur, il est vérifié que :\n"
             "• Le surnom corresponde a un pseudo WoT.",
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

        await context.message.remove_reaction(self.WORK_IN_PROGRESS_EMOJI, self.user)
        await context.message.add_reaction(self.WORK_DONE_EMOJI)

    @staticmethod
    async def have_players_matching_names(context, members, app_id):
        """Check whether all players have a matching player name on WoT."""

        def _batch(_array, _batch_size):
            """ Split an array into an iterable of constant-size batches. """
            for _i in range(0, len(_array), _batch_size):
                yield _array[_i:_i+_batch_size]

        unmatched_names_mentions = []
        for member_batch in _batch(members, 24):
            member_names = [re.sub(r'[^\x00-\x7f]', r'', member.display_name.split(' ')[0])
                            for member in member_batch]  # Replace characters forbidden in player names
            member_names = filter(lambda name: name != '', member_names)
            payload = {
                'application_id': app_id,
                'search': ','.join(member_names),
                'type': 'exact',
            }
            response = requests.get('https://api.worldoftanks.eu/wot/account/list/', params=payload)
            response_content = response.json()
            matched_names = [player_data['nickname'] for player_data in response_content['data']] \
                             if response_content['status'] == 'ok' else []
            unmatched_names_mentions += [member.mention for member in member_batch
                                         if member.display_name.split(' ')[0].lower() not in
                                         [matched_name.lower() for matched_name in matched_names]]
        if unmatched_names_mentions:
            await context.send('\n'.join([f"Le joueur {mention} n'a pas de correspondance de pseudo sur WoT."
                                          for mention in unmatched_names_mentions]))
        else:
            await context.send("Tous les joueurs ont une correspondance de pseudo sur WoT. :ok_hand: ")

    @check.command(
        name='contact',
        brief="Effectue une batterie de tests sur les contacts de clan",
        help="Pour chaque clan, il est vérifié que :\n"
             "• Pas plus d'un contact ne représente le clan\n"
             "• Le surnom du contact du clan arbore le tag de celui-ci\n"
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
        await self.has_clan_mutliple_contacts(context, contacts_by_clan)
        await self.have_contacts_recruiting_permissions(context, contacts_by_clan, self.app_id)

        await context.message.remove_reaction(self.WORK_IN_PROGRESS_EMOJI, self.user)
        await context.message.add_reaction(self.WORK_DONE_EMOJI)

    @staticmethod
    async def have_contacts_clan_tag(context, contacts):
        """Check whether all contacts have a clan tag."""
        missing_clan_tag = False
        for member in contacts:
            if ' ' not in member.display_name:
                missing_clan_tag = True
                await context.send(f"Le joueur {member.mention} n'arbore pas de tag de clan.")
        if not missing_clan_tag:
            await context.send("Tous les contacts de clan arborent un tag de clan. :ok_hand: ")

    @staticmethod
    async def has_clan_mutliple_contacts(context, contacts_by_clan):
        """Check whether a clan has more than one contact."""
        multiple_contacts = False
        for clan_tag, contacts in contacts_by_clan.items():
            if len(contacts) > 1:
                multiple_contacts = True
                await context.send(f"Le clan [{clan_tag}] est représenté par {len(contacts)} membres : "
                                   f"{', '.join([contact.mention for contact in contacts])}")
        if not multiple_contacts:
            await context.send("Tous les clans représentés le sont par exactement un membre. :ok_hand: ")

    @staticmethod
    async def have_contacts_recruiting_permissions(context, contacts_by_clan, app_id):
        """Check whether a clan contact has still the required clan position."""
        missing_permissions = False
        for clan_tag, contacts in contacts_by_clan.items():
            for member in contacts:
                if ' ' in member.display_name:  # Already handled in Admin.have_contacts_clan_tag
                    player_name = member.display_name.split(' ')[0]
                    player_id, _ = await Stats.get_player_id(player_name, app_id)
                    # if not player_id:  # Handle exception but don't raise to avoid breaking the loop  # TODO move in other fct
                    #     await error_handler.handle(context, exceptions.UnknownPlayer(player_name))
                    if player_id:  # Already handled in TODO
                        clan_member_infos = await Stats.get_clan_member_infos(player_id, app_id)
                        real_clan_tag = clan_member_infos and clan_member_infos['tag']
                        clan_position = clan_member_infos and clan_member_infos['position']
                        if not clan_member_infos or real_clan_tag != clan_tag.upper():
                            missing_permissions = True
                            await context.send(f"Le joueur {member.mention} a quitté le clan [{clan_tag}].")
                        elif clan_position not in ["Commandant", "Commandant en second", "Officier du personnel", "Recruteur"]:
                            missing_permissions = True
                            await context.send(f"Le joueur {member.mention} n'a plus les permissions "
                                               f"de recrutement au sein du clan [{real_clan_tag}].")
        if not missing_permissions:
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
