import datetime

import discord

from zbot import checker
from zbot import scheduler
from zbot import utils
from zbot import wot_utils
from zbot import zbot
from . import _command


class Messaging(_command.Command):

    """Commands for social interactions."""

    DISPLAY_NAME = "Messages & Évènements"
    DISPLAY_SEQUENCE = 5
    MOD_ROLE_NAMES = ['Administrateur', 'Modérateur']
    USER_ROLE_NAMES = ['Joueur']

    PLAYER_ROLE_NAME = 'Joueur'
    MIN_ACCOUNT_CREATION_DATE = datetime.datetime(2011, 4, 11)
    CELEBRATION_CHANNEL_ID = 525037740690112527  # général
    CELEBRATION_EMOJI = "🕯"

    def __init__(self, bot):
        super().__init__(bot)
        anniversary_celebration_time = datetime.datetime.combine(
            datetime.datetime.today().date(), datetime.time(9, 0, 0)
        )
        scheduler.schedule_volatile_job(
            anniversary_celebration_time, self.celebrate_account_anniversaries
        )

    async def celebrate_account_anniversaries(self):
        # Get anniversary data
        self.record_account_creation_dates()
        today = datetime.datetime.today()
        account_anniversaries = zbot.db.get_anniversary_account_ids(
            today, self.MIN_ACCOUNT_CREATION_DATE
        )
        member_anniversaries = {}
        for years, account_ids in account_anniversaries.items():
            for account_id in account_ids:
                member = self.guild.get_member(account_id)
                if member and checker.has_role(member, Messaging.PLAYER_ROLE_NAME):
                    member_anniversaries.setdefault(years, []).append(member)

        # Announce anniversaries
        celebration_channel = self.guild.get_channel(self.CELEBRATION_CHANNEL_ID)
        await celebration_channel.send("**Voici les anniversaires du jour !** 🎂")
        for year in sorted(member_anniversaries.keys(), reverse=True):
            for member in member_anniversaries[year]:
                await celebration_channel.send(
                    f"  • {member.mention} fête ses **{year}** ans sur World of Tanks ! 🥳"
                )

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
