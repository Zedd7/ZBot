import datetime
from copy import copy

from discord.ext import commands

from .. import checker
from .. import converter
from .. import exceptions
from . import _command
from .admin import Admin
from .bot import Bot
from .stats import Stats


class Special(_command.Command):
    """Special commands tailored for specific roles"""

    DISPLAY_NAME = "Commandes spéciales"
    DISPLAY_SEQUENCE = 7
    USER_ROLE_NAMES = ['Joueur']

    def __init__(self, bot):
        super().__init__(bot)

    @commands.group(
        name='validate',
        aliases=['valider'],
        brief="Valide le suivi du règlement",
        invoke_without_command=True
    )
    @commands.check(checker.has_any_user_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def validate(self, context):
        if not context.subcommand_passed:
            await Bot.display_group_help(context, context.command)
        else:
            raise exceptions.MissingSubCommand(context.command.name)

    @validate.command(
        name='announce',
        aliases=['annonce', 'recruitment', 'recrutement', 'recrut'],
        usage="",
        brief="Valide le suivi du règlement d'une annonce de recrutement",
        help="La validation consiste à vérifier que :\n"
             "• Le membre possède le rôle \"Contact de clan\"\n"
             "• Le contact de clan n'a posté au maximum qu'une seule annonce à la fois\n"
             "• La longueur de l'annonce est inférieure à 1200 caractères (min 100/ligne)\n"
             "• L'annonce ne contient aucun embed\n"
             "• L'annonce précédente est antérieure à 30 jours",
        ignore_extra=False
    )
    @commands.check(checker.has_any_user_role)
    @commands.check(checker.is_allowed_in_current_guild_channel)
    async def validate_recruitments(self, context):
        if not checker.has_guild_role(context.guild, context.author, Stats.CLAN_CONTACT_ROLE_NAME):
            raise exceptions.MissingRoles([Stats.CLAN_CONTACT_ROLE_NAME])

        recruitment_channel = self.guild.get_channel(Admin.RECRUITMENT_CHANNEL_ID)
        all_recruitment_announces = [message async for message in recruitment_channel.history()]
        recruitment_announces = list(filter(lambda a: a.author == context.author, all_recruitment_announces))
        last_recruitment_announce = recruitment_announces and recruitment_announces[0]

        if not last_recruitment_announce:
            await context.send("Aucune annonce de recrutement n'a été trouvée.")
        else:
            patched_context = copy(context)
            patched_context.send = self.mock_send
            validation_succeeded = True
            if await Admin.check_recruitment_announces_uniqueness(patched_context, recruitment_announces):
                validation_succeeded = False
                await context.send(
                    f"Tu as publié {len(recruitment_announces)} annonces. Une seule est autorisée à la fois."
                )
            if await Admin.check_recruitment_announces_length(patched_context, [last_recruitment_announce]):
                validation_succeeded = False
                apparent_length = Admin.compute_apparent_length(last_recruitment_announce)
                await context.send(
                    f"L'annonce est d'une longueur apparente de **{apparent_length}** caractères (max "
                    f"{Admin.MAX_RECRUITMENT_ANNOUNCE_LENGTH}). Réduit sa longueur en retirant du contenu ou en "
                    f"réduisant le nombre de sauts de lignes."
                )
            if await Admin.check_recruitment_announces_embeds(patched_context, [last_recruitment_announce]):
                validation_succeeded = False
                await context.send(
                    f"Ton annonce contient un embed, ce qui n'est pas autorisé. Utilise un raccourcisseur d'URLs comme "
                    f"<https://tinyurl.com> pour héberger tes liens."
                )
            if await Admin.check_recruitment_announces_timespan(
                patched_context, recruitment_channel, [last_recruitment_announce]
            ):
                validation_succeeded = False
                await context.send(
                    f"Ton annonce a été postée avant le délai minimum de {Admin.MIN_RECRUITMENT_ANNOUNCE_TIMESPAN} "
                    f"jours entre deux annonces."
                )

            if validation_succeeded:
                await context.send(f"L'annonce ne présente aucun problème. :ok_hand: ")

            last_announce_time_localized = converter.to_utc(self.db.load_recruitment_announces_data(
                query={'author': context.author.id}, order=[('time', -1)]
            )[0]['time'])
            min_timespan = datetime.timedelta(
                # Apply a tolerance of 2 days for players interpreting the 30 days range as "one month".
                # This is a subtraction because the resulting value is the number of days to wait before posting again.
                days=Admin.MIN_RECRUITMENT_ANNOUNCE_TIMESPAN - Admin.RECRUITMENT_ANNOUNCE_TIMESPAN_TOLERANCE
            )
            next_announce_time_localized = last_announce_time_localized + min_timespan
            await context.send(
                f"Tu pourras à nouveau poster une annonce à partir du "
                f"{converter.to_human_format(next_announce_time_localized)}."
            )


async def setup(bot):
    await bot.add_cog(Special(bot))
