import os
import random

import discord
#from discord.ext import commands
import dotenv

import keep_alive

__version__ = '1.0.1'


class Client(discord.Client):
    """Represent the client connection which connects to Discord."""

    # bot = commands.Bot(command_prefix='/')
    #
    # @bot.command()
    # async def test(context):
    #     await context.message.send("test123")
    #     pass

    async def on_ready(self):
        print(f"Logged in as {self.user}")

    async def on_message(self, message):
        if isinstance(message.channel, discord.DMChannel):  # Don't respond to DMs
            await message.author.send("Les commandes par MP ne sont pas autorisées !")
            return
        if not self.user.mentioned_in(message) or message.mention_everyone:  # Only respond to direct mentions
            return
        if message.author == self.user:  # Don't respond to own messages
            return
        if not message.channel.permissions_for(message.author).administrator:  # Only respond to admins
            return
        if not message.content.startswith(self.user.mention):  # Only handles messages starting with mention
            return

        await self.dispatch_command(message)

    async def dispatch_command(self, message):
        """Recognize and dispatch the command to the right handler."""
        command = message.content.split(self.user.mention)[1].strip()
        if not command:  # Stop if command not provided
            return

        command_args = command.split(' ')
        if command_args[0] == 'pick':
            await self.handle_pick_command(message, command_args[1:])
        else:
            await message.channel.send("Unknown command.")

    async def handle_pick_command(self, message, command_args):
        """
            Process the command pick.

            Command format : pick <#n> <#channel> <message_id> <:emoji:> <seed>
        """
        if len(command_args) != 4:
            await message.channel.send("Incorrect command format. Use `@ZBot pick <#n> <#channel> <message_id> <:emoji:>`")
            return

        try:
            await message.delete()
            n = int(command_args[0])
            channel_id = int(command_args[1][2:-1])  # Extract id from <#id>
            message_id = int(command_args[2])
            emoji = command_args[3]
            channel = discord.utils.get(message.guild.text_channels, id=channel_id)
            target_message = await channel.get_message(message_id)
            reaction = discord.utils.get(target_message.reactions, emoji=emoji)
            users = [_ async for _ in reaction.users()]
            seed = random.randrange(10**6)
            random.seed(seed)
            winners = random.sample(users, n)
            await message.channel.send(f"**Tirage au sort !** (seed : {seed})\n"
                                       f"Les {n} gagnants parmi {len(users)} participants sont...")
            for winner in winners:
                await message.channel.send(f":tada: {winner.mention} :champagne: ")
        except Exception as e:
            print("An error occurred.")
            print(e)


if __name__ == '__main__':
    dotenv.load_dotenv()
    bot_token = os.getenv("BOT_TOKEN")
    keep_alive.keep_alive()

    if bot_token:
        client = Client()
        client.run(bot_token)
    else:
        print("You must add the bot token in the .env file under the key 'BOT_TOKEN'.")
