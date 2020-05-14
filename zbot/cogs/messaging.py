import datetime

import discord
from discord.ext import commands

from zbot import checker
from zbot import converter
from zbot import exceptions
from zbot import scheduler
from zbot import utils
from zbot import wot_utils
from zbot import zbot
from . import _command


class Messaging(_command.Command):

    """Commands for social interactions."""

    DISPLAY_NAME = "Communications"
    DISPLAY_SEQUENCE = 5
    MOD_ROLE_NAMES = ['Administrateur', 'Modérateur']
    USER_ROLE_NAMES = ['Joueur']

    PLAYER_ROLE_NAME = 'Joueur'
    TIMEZONE = converter.GUILD_TIMEZONE
    MIN_ACCOUNT_CREATION_DATE = TIMEZONE.localize(datetime.datetime(2011, 4, 11))
    CELEBRATION_CHANNEL_ID = 525037740690112527  # #général
    CELEBRATION_EMOJI = "🕯"

    def __init__(self, bot):
        super().__init__(bot)
        anniversary_celebration_time = self.TIMEZONE.localize(datetime.datetime.combine(
            converter.get_tz_aware_local_datetime(), datetime.time(9, 0, 0)
        ))
        scheduler.schedule_volatile_job(
            anniversary_celebration_time,
            self.celebrate_account_anniversaries,
            interval=datetime.timedelta(days=1)
        )

    @commands.command(
        name='switch',
        usage='[--number=N] [--ping] [--delete]',
        brief="Redirige une conversation",
        help="Suggère au participants d'une conversation dans le canal courant à la poursuivre "
             "ailleurs. Par défaut, les 3 derniers messages sont copiés dans le canal de "
             "destination. Pour modifier le nombre de messages à copier, ajoutez l'argument "
             "`--number=N` où `N` est le nombre de messages à copier (maximum 10). Pour "
             "respectivement mentionner les auteurs de ces messages ou les supprimer, ajoutez "
             "l'argument `--ping` ou `--delete` (droits de modération requis).",
        ignore_extra=True
    )
    @commands.check(checker.is_allowed_in_all_channels)
    @commands.check(checker.has_any_user_role)
    async def switch(self, context, dest_channel: discord.TextChannel, *, options=""):
        if context.channel == dest_channel \
                or not context.author.permissions_in(dest_channel).send_messages:
            raise exceptions.ForbiddenChannel(dest_channel)
        number_option = utils.get_option_value(options, 'number')
        if number_option is not None:  # Value assigned
            try:
                messages_number = int(number_option)
            except ValueError:
                raise exceptions.MisformattedArgument(number_option, "valeur entière")
            if messages_number < 1:
                raise exceptions.UndersizedArgument(messages_number, 1)
            elif messages_number > 10 and not checker.has_any_mod_role(context, print_error=False):
                raise exceptions.OversizedArgument(messages_number, 10)
        elif utils.is_option_enabled(options, 'number', has_value=True):  # No value assigned
            raise exceptions.MisformattedArgument(number_option, "valeur entière")
        else:  # Option not used
            messages_number = 3
        do_ping = utils.is_option_enabled(options, 'ping')
        do_delete = utils.is_option_enabled(options, 'delete')
        if do_ping or do_delete:
            checker.has_any_mod_role(context, print_error=True)

        messages = await context.channel.history(limit=messages_number+1).flatten()
        messages.reverse()  # Order by oldest first
        messages.pop()  # Remove message used for the command

        await context.message.delete()
        await context.send(
            f"**Veuillez basculer cette discussion dans le canal {dest_channel.mention} qui serait "
            f"plus approprié ! 🧹**"
        )
        await dest_channel.send(f"**Suite de la discussion de {context.channel.mention} 💨**")
        await self.move_messages(messages, dest_channel, do_ping, do_delete)

    @staticmethod
    async def move_messages(messages, dest_channel, do_ping, do_delete):

        async def _flush_buffer():
            author_mention = current_author.mention if do_ping \
                else '@' + current_author.display_name
            await dest_channel.send(f"{author_mention} :\n>>> " + "\n".join(content_buffer))
            content_buffer.clear()

        content_buffer, current_author = [], None
        for message in messages:
            if message.author != current_author and current_author is not None:  # New message batch
                await _flush_buffer()
            current_author = message.author
            content_buffer.append(message.content)
            if do_delete:
                await message.delete()
        await _flush_buffer()

    @commands.group(
        name='work',
        brief="Gère les notifications de travaux sur le bot",
        hidden=False,
        invoke_without_command=True
    )
    @commands.guild_only()
    async def work(self, context):
        if context.invoked_subcommand is None:
            raise exceptions.MissingSubCommand(context.command.name)

    @work.command(
        name='start',
        aliases=['begin'],
        brief="Annonce le début des travaux sur le bot",
        help="L'annonce est postée dans le canal courant, la commande est supprimée et le status "
             "est défini sur travaux en cours.",
        ignore_extra=True
    )
    @commands.check(checker.is_allowed_in_current_channel)
    @commands.check(checker.has_any_mod_role)
    async def work_start(self, context):
        zbot.db.update_metadata('work_in_progress', True)
        await context.message.delete()
        await context.send(
            f"**Début des travaux sur le bot {self.user.mention}** :man_factory_worker:"
        )

    @work.command(
        name='done',
        brief="Annonce la fin des travaux sur le bot",
        help="L'annonce est postée dans le canal courant, la commande est supprimée et le status "
             "est défini sur travaux terminés.",
        ignore_extra=True
    )
    @commands.check(checker.is_allowed_in_current_channel)
    @commands.check(checker.has_any_mod_role)
    async def work_done(self, context):
        zbot.db.update_metadata('work_in_progress', False)
        await context.message.delete()
        await context.send(f"**Fin des travaux sur le bot {self.user.mention}** :mechanical_arm:")

    @work.command(
        name='status',
        aliases=['statut'],
        brief="Affiche l'état des travaux sur le bot",
        help="Le résultat est posté dans le canal courant.",
        ignore_extra=True
    )
    @commands.check(checker.is_allowed_in_current_channel)
    @commands.check(checker.has_any_user_role)
    async def work_status(self, context):
        work_in_progress = zbot.db.get_metadata('work_in_progress') or False  # Might not be set
        if work_in_progress:
            await context.send(f"Les travaux sur le bot sont toujours en cours.")
        else:
            await context.send(f"Les travaux sur le bot sont terminés. :ok_hand:")

    async def celebrate_account_anniversaries(self):
        # Get anniversary data
        self.record_account_creation_dates()
        today = converter.get_tz_aware_local_datetime()
        account_anniversaries = zbot.db.get_anniversary_account_ids(
            today, self.MIN_ACCOUNT_CREATION_DATE
        )
        member_anniversaries = {}
        for years, account_ids in account_anniversaries.items():
            for account_id in account_ids:
                member = self.guild.get_member(account_id)
                if member and checker.has_role(member, Messaging.PLAYER_ROLE_NAME):
                    member_anniversaries.setdefault(years, []).append(member)

        # Remove celebration emojis in names from previous anniversaries
        for member in self.guild.members:
            if self.CELEBRATION_EMOJI in member.display_name:
                try:
                    await member.edit(
                        nick=member.display_name.replace(self.CELEBRATION_EMOJI, '').rstrip()
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass
        # Add celebration emojis for today's anniversaries
        for year, members in member_anniversaries.items():
            for member in members:
                try:
                    await member.edit(
                        nick=member.display_name + " " + self.CELEBRATION_EMOJI * year
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass

        # Announce anniversaries (after updating names to refresh the cache)
        celebration_channel = self.guild.get_channel(self.CELEBRATION_CHANNEL_ID)
        if member_anniversaries:
            await celebration_channel.send("**Voici les anniversaires du jour !** 🎂")
            for year in sorted(member_anniversaries.keys(), reverse=True):
                for member in member_anniversaries[year]:
                    await celebration_channel.send(
                        f"  • {member.mention} fête ses **{year}** ans sur World of Tanks ! 🥳"
                    )

    def record_account_creation_dates(self):
        # Build list of unrecorded members
        members = []
        for member in self.guild.members:
            if checker.has_role(member, Messaging.PLAYER_ROLE_NAME):
                members.append(member)
        members = zbot.db.get_unrecorded_members(members)

        # Map members with their account id
        players_info = wot_utils.get_players_info(
            [member.display_name for member in members], self.app_id
        )
        members_account_ids, members_account_data = {}, {}
        for player_name, account_id in players_info.items():
            for member in members:
                result = utils.PLAYER_NAME_PATTERN.match(member.display_name)
                if result:
                    display_name = result.group(1)
                    if display_name.lower() == player_name.lower():
                        members_account_ids[member] = account_id
                        members_account_data.setdefault(member, {})['display_name'] = display_name

        # Map members with their account creation date
        players_details = wot_utils.get_players_details(
            list(members_account_ids.values()), self.app_id
        )
        for member, account_id in members_account_ids.items():
            members_account_data[member].update(creation_date=players_details[account_id][0])
        zbot.db.update_accounts_data(members_account_data)


def setup(bot):
    bot.add_cog(Messaging(bot))
