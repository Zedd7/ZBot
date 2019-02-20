import asyncio
import os
import random

import discord

__version__ = '0.0.1'

CONFIG_PATH = '../res/config.txt'


def load_bot_token(config_path):
    """Load the bot token from config."""
    token = None
    if os.path.exists(config_path):
        with open(config_path, 'r') as config:
            bot_token_line = config.readline().rstrip()
            if len(bot_token_line.split('=')) == 2 and bot_token_line.split('=')[0] == 'BOT_TOKEN':
                token = bot_token_line.split('=')[1]
    if token:
        print(f"Bot token loaded from config: {token}")
    else:
        print(f"No bot token could be found in {os.path.abspath(config_path)}")
    return token


class Client(discord.Client):
    """Represent the client connection which connects to Discord."""

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

            Command format : pick <#channel> <message_id> <:emoji:> <seed>
        """
        if len(command_args) != 4:
            await message.channel.send("Incorrect command format. Use `@ZBot pick <#channel> <message_id> <:emoji:> <seed>`")
            return

        try:
            channel_id = int(command_args[0][2:-1])  # Extract id from <#id>
            message_id = int(command_args[1])
            emoji = command_args[2]
            seed = int(command_args[3])
            channel = discord.utils.get(message.guild.text_channels, id=channel_id)
            target_message = await channel.get_message(message_id)
            reaction = discord.utils.get(target_message.reactions, emoji=emoji)
            users = [_ async for _ in reaction.users()]
            random.seed(seed)
            winner = random.choice(users)
            await message.channel.send(f"**Loterie !**\n"
                                       f"Nous allons procéder au tirage au sort du gagnant parmi {len(users)} participants...")
            await asyncio.sleep(10)
            await message.channel.send("Patience...")
            await asyncio.sleep(30)
            await message.channel.send("https://media.giphy.com/media/dvgefaMHmaN2g/giphy.gif")
            await asyncio.sleep(30)
            await message.channel.send(":zzz: .. Hein heu ?\n\n**Et le gagnant est...**")
            await asyncio.sleep(10)
            await message.channel.send(f":champagne: **{winner.mention} !!!** :champagne: ")
        except Exception as e:
            print("An error occurred.")
            print(e)


if __name__ == '__main__':
    bot_token = load_bot_token(CONFIG_PATH)
    if bot_token:
        client = Client()
        client.run(bot_token)
