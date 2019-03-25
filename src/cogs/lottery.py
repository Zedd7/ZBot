import datetime
import random

import discord
from discord.ext import commands

import src.utils as utils
import src.exceptions as exceptions

# TODO allow custom emojis <https://discordpy.readthedocs.io/en/rewrite/ext/commands/commands.html#typing-union>
# TODO DM players when they attempt to play but don't have the required role
# TODO DM winners
# TODO add custom check for allowed channels
# TODO allow to schedule lottery pick at a given time
# TODO store hardcoded data in MongoDB
# TODO allow command arguments to be given one at a time


class Lottery:

    MAIN_COMMAND_NAME = 'lottery'
    MOD_ROLES = ['Administrateur', 'Modérateur', 'Annonceur']
    USER_ROLE = 'Joueur'
    EMBED_COLOR = 0xFAA61A

    def __init__(self, bot):
        self.bot = bot
        self.user = self.bot.user

    @commands.group(
        name=MAIN_COMMAND_NAME,
        invoke_without_command=True
    )
    @commands.guild_only()
    async def lottery(self, context):
        if context.invoked_subcommand is None:
            await context.send("Commande manquante.")

    @lottery.command(
        name='pick',
        aliases=['p'],
        usage="<#src_channel> <message_id> <emoji> <nb_winners> <#dest_channel> [<organisateur>]",
        ignore_extra=False
    )
    @commands.check(utils.has_any_mod_role)
    async def pick(self,
                   context,
                   src_channel: discord.TextChannel,
                   message_id: int,
                   emoji: str,
                   nb_winners: int,
                   dest_channel: discord.TextChannel,
                   organizer: discord.User = None):

        if not context.author.permissions_in(dest_channel).send_messages:
            raise commands.MissingPermissions([f"`send_messages` in {dest_channel.mention}"])
        if nb_winners < 1:
            raise exceptions.UndersizedArgument(nb_winners, 1)

        seed = random.randrange(10**6)
        random.seed(seed)
        print(f"Picking winner using seed = {seed} ({datetime.datetime.now()})")

        target_message = await utils.try_get_message(exceptions.MissingMessage(message_id), src_channel, message_id)
        reaction = await utils.try_get(exceptions.ForbiddenEmoji(emoji), target_message.reactions, emoji=emoji)
        players = [player async for player in reaction.users() if await utils.has_role(context.guild, player, self.USER_ROLE)]
        nb_winners = min(nb_winners, len(players))
        winners = random.sample(players, nb_winners)

        embed = discord.Embed(
            title="Résultat du tirage au sort :tada:",
            description=f"Gagnant(s) parmi {len(players)} participants:\n" + "\n".join(f"**@{winner.display_name}**" for winner in winners),
            color=self.EMBED_COLOR
        )
        embed.set_author(name=f"Organisé par @{organizer.display_name}", icon_url=organizer.avatar_url)
        await dest_channel.send(embed=embed)

        if organizer:
            for winner in winners:
                await winner.send(f"Félicitations ! Tu as été tiré au sort lors de la loterie organisée par {organizer.mention} !\n"
                                  f"Contacte cette personne par MP pour obtenir ta récompense :wink:")
            await organizer.send(f"Les gagnants de la loterie sont: {', '.join(winner.mention for winner in winners)}")


def setup(bot):
    bot.add_cog(Lottery(bot))
