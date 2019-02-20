import os

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
        print(f"New bot token loaded from config: {token}")
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
        if not self.user.mentioned_in(message):  # Only respond to direct mentions
            return
        if message.author == self.user:  # Don't respond to own messages
            return
        if not message.channel.permissions_for(message.author).administrator:  # Only respond to admins
            return
        await message.channel.send(f"Hello {message.author.mention}.")


if __name__ == '__main__':
    bot_token = load_bot_token(CONFIG_PATH)
    if bot_token:
        client = Client()
        client.run(bot_token)
