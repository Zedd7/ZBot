import pathlib

BOT_TOKEN_KEY = 'BOT_TOKEN'


def load_bot_token(config_file: pathlib.Path):
    """Load the bot token from config."""
    token = None
    if config_file.exists():
        with config_file.open(mode='r') as config:
            bot_token_line = config.readline().rstrip()
            if len(bot_token_line.split('=')) == 2 and bot_token_line.split('=')[0] == BOT_TOKEN_KEY:
                token = bot_token_line.split('=')[1]
    if token:
        print(f"Bot token loaded from config: {token}")
    else:
        print(f"No bot token could be found in {config_file.absolute()}")
    return token
