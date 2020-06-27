import asyncio
import datetime
import random

import discord
from discord.ext import commands
from discord.ext import tasks

from zbot import checker
from zbot import converter
from zbot import exceptions
from zbot import logger
from zbot import scheduler
from zbot import utils
from zbot import wot_utils
from zbot import zbot
from . import _command


class Messaging(_command.Command):

    """Commands for social interactions."""

    DISPLAY_NAME = "Communications"
    DISPLAY_SEQUENCE = 6
    MOD_ROLE_NAMES = ['Administrateur', 'Modérateur']
    USER_ROLE_NAMES = ['Joueur']
    EMBED_COLOR = 0x91b6f2  # Pastel blue

    PLAYER_ROLE_NAME = 'Joueur'
    TIMEZONE = converter.COMMUNITY_TIMEZONE
    MIN_ACCOUNT_CREATION_DATE = TIMEZONE.localize(datetime.datetime(2011, 4, 11))
    CELEBRATION_CHANNEL_ID = 525037740690112527  # #général
    CELEBRATION_EMOJI = "🕯"
    AUTOMESSAGE_FREQUENCY = datetime.timedelta(hours=4)  # The time to wait after that the last message was posted
    AUTOMESSAGE_COOLDOWN = datetime.timedelta(days=2)  # The time to wait before sending two messages in a row
    AUTOMESSAGE_WAIT = datetime.timedelta(minutes=5)  # The time to wait for a channel to be quiet

    def __init__(self, bot):
        super().__init__(bot)
        bot.loop.create_task(self.schedule_anniversaries_celebration())
        self.send_automessage.start()

    async def schedule_anniversaries_celebration(self):
        # Silently prevent scheduling the job if it has run today to avoid the scheduler logging a warning
        today = converter.get_tz_aware_datetime_now()
        last_anniversaries_celebration = zbot.db.get_metadata('last_anniversaries_celebration')
        if last_anniversaries_celebration and last_anniversaries_celebration.date() == today.date():
            return

        anniversary_celebration_time = self.TIMEZONE.localize(datetime.datetime.combine(today, datetime.time(9, 0, 0)))
        scheduler.schedule_volatile_job(
            anniversary_celebration_time,
            self.celebrate_account_anniversaries,
            interval=datetime.timedelta(days=1)
        )

    async def celebrate_account_anniversaries(self):
        # Check if not running above frequency
        today = converter.get_tz_aware_datetime_now()
        last_anniversaries_celebration = zbot.db.get_metadata('last_anniversaries_celebration')
        if last_anniversaries_celebration and last_anniversaries_celebration.date() == today.date():
            logger.debug(f"Prevented sending anniversaries celebration because running above defined frequency.")
            return

        # Get anniversary data
        self.record_account_creation_dates()
        today = converter.get_tz_aware_datetime_now()
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

        zbot.db.update_metadata('last_anniversaries_celebration', today)

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

    @tasks.loop(seconds=AUTOMESSAGE_FREQUENCY.seconds)
    async def send_automessage(self):
        # Check if not running above frequency
        last_automessage_date = zbot.db.get_metadata('last_automessage_date')
        if last_automessage_date:
            last_automessage_date_localized = converter.to_guild_tz(last_automessage_date)  # MongoDB uses UTC
            if last_automessage_date_localized >= converter.get_tz_aware_datetime_now() - self.AUTOMESSAGE_FREQUENCY:
                logger.debug(f"Prevented sending automessage because running above defined frequency.")
                return

        # Get automessages data
        automessages_data = zbot.db.load_automessages(
            {'automessage_id': {
                '$ne': zbot.db.get_metadata('last_automessage_id')  # Don't post the same message twice in a row
            }},
            ['automessage_id', 'channel_id', 'message']
        )
        if not automessages_data:  # At most a single automessage exists
            automessages_data = zbot.db.load_automessages(  # Load it anyway
                {}, ['automessage_id', 'channel_id', 'message']
            )
        if not automessages_data:  # Not automessage exists
            return  # Abort
        automessage_data = random.choice(automessages_data)
        automessage_id = automessage_data['automessage_id']
        message = automessage_data['message']
        channel = self.guild.get_channel(automessage_data['channel_id'])
        last_channel_message = (await channel.history(limit=1).flatten())[0]

        # Run halt checks on target channel
        now = converter.get_tz_aware_datetime_now()
        if last_channel_message.author == self.user:  # Avoid spamming an channel
            # Check if the cooldown between two bot messages has expired
            last_channel_message_date = converter.to_guild_tz(last_channel_message.created_at)
            cooldown_expired = last_channel_message_date < now - self.AUTOMESSAGE_COOLDOWN
            if not cooldown_expired:
                logger.debug(f"Skipped automessage of id {automessage_id} as cooldown has not expired yet.")
                return
        else:  # Avoid interrupting conversations
            is_channel_quiet, attempt_count = False, 0
            while not is_channel_quiet:  # Wait for the channel to be quiet to send the message
                now = converter.get_tz_aware_datetime_now()
                last_channel_message_date = converter.to_guild_tz(last_channel_message.created_at)
                is_channel_quiet = last_channel_message_date < now - self.AUTOMESSAGE_WAIT
                if not is_channel_quiet:
                    attempt_count += 1
                    if attempt_count < 3:
                        logger.debug(
                            f"Pausing automessage of id {automessage_id} for {self.AUTOMESSAGE_WAIT.seconds} "
                            f"seconds while waiting for quietness in target channel."
                        )
                        await asyncio.sleep(self.AUTOMESSAGE_WAIT.seconds)  # Sleep for the duration of the delay
                    else:  # After 3 failed attempts, skip
                        logger.debug(f"Skipped automessage of id {automessage_id} after 3 waits for quietness.")
                        return

        # All checks passed, send the automessage
        zbot.db.update_metadata('last_automessage_id', automessage_id)
        zbot.db.update_metadata('last_automessage_date', now)
        await channel.send(message)

    @commands.group(
        name='automessage',
        aliases=['auto'],
        brief="Gère les messages automatiques",
        hidden=True,
        invoke_without_command=True
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def automessage(self, context):
        if context.invoked_subcommand is None:
            raise exceptions.MissingSubCommand(context.command.name)

    @automessage.command(
        name='add',
        aliases=['new'],
        usage="<#channel> <\"message\">",
        brief="Ajoute un nouveau message automatique",
        help="Le bot tire au sort à intervalles réguliers un message automatique parmi ceux existants et le poste dans "
             "le canal associé.",
        hidden=True,
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def automessage_add(self, context, channel: discord.TextChannel, message: str):
        if not context.author.permissions_in(channel).send_messages:
            raise exceptions.ForbiddenChannel(channel)

        automessage_id = self.get_next_automessage_id()
        zbot.db.insert_automessage(automessage_id, message, channel)
        await context.send(
            f"Message automatique d'identifiant `{automessage_id}` créé et lié au canal {channel.mention}."
        )

    @staticmethod
    def get_next_automessage_id() -> int:
        automessage_ids = [
            automessage_data['automessage_id'] for automessage_data in zbot.db.load_automessages({}, ['automessage_id'])
        ]
        return max(automessage_ids) + 1 if automessage_ids else 1

    @automessage.command(
        name='list',
        aliases=['l', 'ls'],
        brief="Affiche la liste des messages automatiques",
        hidden=True,
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def automessage_list(self, context):
        automessage_descriptions = {}
        for automessage_data in zbot.db.load_automessages({}, ['automessage_id', 'message', 'channel_id']):
            automessage_id = automessage_data['automessage_id']
            message = automessage_data['message']
            if len(message) > 120:  # Avoid reaching the 2000 chars limit per message
                message = message[:120] + "..."
            channel = self.guild.get_channel(automessage_data['channel_id'])
            automessage_descriptions[automessage_id] = f" • `[{automessage_id}]` dans {channel.mention}: \"{message}\""
        embed_description = "Aucun" if not automessage_descriptions \
            else "\n".join([automessage_descriptions[automessage_id]
                            for automessage_id in sorted(automessage_descriptions.keys())])
        embed = discord.Embed(
            title="Message(s) automatique(s)",
            description=embed_description,
            color=self.EMBED_COLOR
        )
        await context.send(embed=embed)

    @automessage.command(
        name='print',
        aliases=['p', 'test'],
        usage="<automessage_id> [--raw]",
        brief="Poste un message automatique",
        help="Le canal courant est utilisé au lieu du canal associé et toutes les vérifications sont désactivées. Si "
             "l'argument `--raw` est fourni, le message est posté en texte brut.",
        hidden=True,
        ignore_extra=True
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def automessage_print(self, context, automessage_id: int, *, options=""):
        automessages_data = zbot.db.load_automessages({'automessage_id': automessage_id}, ['message'])
        if not automessages_data:
            raise exceptions.UnknownAutomessage(automessage_id)

        raw_text = utils.is_option_enabled(options, 'raw')
        message = automessages_data[0]['message']
        await context.send(message if not raw_text else f"`{message}`")

    @automessage.command(
        name='remove',
        aliases=['r', 'delete', 'del', 'd'],
        usage="<automessage_id>",
        brief="Supprime un message automatique",
        hidden=True,
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def automessage_remove(self, context, automessage_id: int):
        automessages_data = zbot.db.load_automessages({}, ['_id', 'automessage_id'])
        automessage_data = [data for data in automessages_data if data['automessage_id'] == automessage_id]
        if not automessage_data:
            raise exceptions.UnknownAutomessage(automessage_id)

        document_id = automessage_data[0]['_id']  # Backup before overwrite
        automessages_update_data = {}
        for automessage_data in automessages_data:
            if automessage_data['automessage_id'] > automessage_id:
                automessages_update_data[automessage_data['_id']] = {
                    'automessage_id': automessage_data['automessage_id'] - 1
                }
        zbot.db.update_automessages(automessages_update_data)
        zbot.db.delete_automessage(document_id)
        await context.send(f"Message automatique d'identifiant `{automessage_id}` supprimé.")

    @automessage.group(
        name='edit',
        brief="Modifie un message automatique",
        hidden=True,
        invoke_without_command=True
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def automessage_edit(self, context):
        if context.invoked_subcommand is None:
            raise exceptions.MissingSubCommand(f'automessage {context.command.name}')

    @automessage_edit.command(
        name='channel',
        aliases=['chan'],
        usage="<automessage_id> <#channel>",
        brief="Modifie le canal du message automatique",
        help="Les futurs messages de cette entrée seront postés dans le canal fourni.",
        hidden=True,
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def automessage_edit_channel(self, context, automessage_id: int, channel: discord.TextChannel):
        automessages_data = zbot.db.load_automessages({'automessage_id': automessage_id}, ['_id'])
        if not automessages_data:
            raise exceptions.UnknownAutomessage(automessage_id)
        if not context.author.permissions_in(channel).send_messages:
            raise exceptions.ForbiddenChannel(channel)

        document_id = automessages_data[0]['_id']
        zbot.db.update_automessages({document_id: {'channel_id': channel.id}})
        await context.send(f"Message automatique d'identifiant {automessage_id} lié au canal {channel.mention}.")

    @automessage_edit.command(
        name='message',
        aliases=['m'],
        usage="<automessage_id> <\"message\">",
        brief="Modifie le contenu du message automatique",
        help="Les futurs posts de cette entrée contiendront le message fourni.",
        hidden=True,
        ignore_extra=False
    )
    @commands.check(checker.has_any_mod_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def automessage_edit_message(self, context, automessage_id: int, message: str):
        automessages_data = zbot.db.load_automessages({'automessage_id': automessage_id}, ['_id'])
        if not automessages_data:
            raise exceptions.UnknownAutomessage(automessage_id)

        document_id = automessages_data[0]['_id']
        zbot.db.update_automessages({document_id: {'message': message}})
        await context.send(f"Contenu du message automatique d'identifiant {automessage_id} changé en : `{message}`.")

    @commands.command(
        name='switch',
        usage='<#dest_channel> [--number=N] [--ping] [--delete]',
        brief="Redirige une conversation",
        help="Suggère au participants d'une conversation dans le canal courant à la poursuivre ailleurs. Par défaut, "
             "les 3 derniers messages sont copiés dans le canal de destination. Pour modifier le nombre de messages à "
             "copier, ajoutez l'argument `--number=N` où `N` est le nombre de messages à copier (maximum 10). Pour "
             "respectivement mentionner les auteurs de ces messages ou les supprimer, ajoutez l'argument `--ping` ou "
             "`--delete` (droits de modération requis).",
        ignore_extra=True
    )
    @commands.check(checker.has_any_user_role)
    @commands.check(checker.is_allowed_in_all_guild_channels)
    async def switch(self, context, dest_channel: discord.TextChannel, *, options=""):
        if context.channel == dest_channel or not context.author.permissions_in(dest_channel).send_messages:
            raise exceptions.ForbiddenChannel(dest_channel)
        number_option = utils.get_option_value(options, 'number')
        if number_option is not None:  # Value assigned
            try:
                messages_number = int(number_option)
            except ValueError:
                raise exceptions.MisformattedArgument(number_option, "valeur entière")
            if messages_number < 0:
                raise exceptions.UndersizedArgument(messages_number, 0)
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
        if not do_delete:
            await context.send(
                f"**Veuillez basculer cette discussion dans le canal {dest_channel.mention} qui serait plus "
                f"approprié !** 🧹"
            )
        else:
            await context.send(
                f"**La discussion a été déplacée dans le canal {dest_channel.mention} !** ({len(messages)} messages "
                f"supprimés) 🧹"
            )
        if messages_number != 0:
            await dest_channel.send(f"**Suite de la discussion de {context.channel.mention}** 💨")
        await self.move_messages(messages, dest_channel, do_ping, do_delete)

    @staticmethod
    async def move_messages(messages, dest_channel, do_ping, do_delete):

        async def _flush_buffer():
            if content_buffer:
                author_mention = current_author.mention if do_ping else '@' + current_author.display_name
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


def setup(bot):
    bot.add_cog(Messaging(bot))
