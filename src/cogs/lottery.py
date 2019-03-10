import datetime
import random

import discord
from discord.ext import commands

import src.utils as utils

# TODO allow custom emojis <https://discordpy.readthedocs.io/en/rewrite/ext/commands/commands.html#typing-union>
# TODO PM players when they attempt to play but don't have the required role
# TODO PM winners
# TODO add custom check for allowed channels


class Lottery:

    MAIN_COMMAND_NAME = 'lottery'
    MOD_ROLES = ['Administrateur', 'Modérateur', 'Annonceur']
    USER_ROLE = 'Joueur'

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
        usage="<#src_channel> <message_id> <emoji> <nb_winners> <#dest_channel>",
        ignore_extra=False
    )
    @commands.check(utils.has_any_mod_role)
    async def pick(self, context, src_channel: discord.TextChannel, message_id: int, emoji: str, nb_winners: int, dest_channel: discord.TextChannel):
        if not context.author.permissions_in(dest_channel).send_messages:
            raise commands.MissingPermissions([f"`send_messages` in {dest_channel.mention}"])

        seed = random.randrange(10**6)
        random.seed(seed)
        print(f"Picking winner using seed = {seed} ({datetime.datetime.now()})")

        target_message = await utils.try_get_message(utils.MissingMessage(message_id), src_channel, message_id)
        reaction = await utils.try_get(utils.ForbiddenEmoji(emoji), target_message.reactions, emoji=emoji)
        players = [player async for player in reaction.users() if await utils.has_role(context.guild, player, self.USER_ROLE)]
        if nb_winners > len(players): raise utils.OversizedArgument(nb_winners, len(players))
        winners = random.sample(players, nb_winners)

        embed = discord.Embed(
            title="Résultat de la loterie :tada:",
            description=f"Gagnant(s) parmi {len(players)} participants:\n" + "\n".join(winner.mention for winner in winners),
            footer="footer"
        )
        await dest_channel.send(embed=embed)


def setup(bot):
    bot.add_cog(Lottery(bot))
