import logging
import logging.handlers
import pathlib
import sys

ZBOT_LOG_FILE = pathlib.Path('./logs/zbot.log')
ZBOT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
DISCORD_LOG_FILE = pathlib.Path('./logs/discord.log')
DISCORD_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def setup_handler(logger, handler, set_suffix=False):
    if set_suffix:
        handler.suffix = '%Y-%m-%d_%H-%M-%S'
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)


zbot_logger = logging.getLogger('zbot')
zbot_logger.setLevel(logging.DEBUG)
setup_handler(zbot_logger, logging.StreamHandler(sys.stdout))
setup_handler(
    zbot_logger,
    logging.handlers.TimedRotatingFileHandler(ZBOT_LOG_FILE, when='midnight', encoding='utf-8'),
    set_suffix=True
)

discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.INFO)
setup_handler(
    discord_logger,
    logging.handlers.TimedRotatingFileHandler(DISCORD_LOG_FILE, when='midnight', encoding='utf-8'),
    set_suffix=True
)


def debug(message, *args, **kwargs):
    zbot_logger.debug(message, *args, **kwargs)


def info(message, *args, **kwargs):
    zbot_logger.info(message, *args, **kwargs)


def warning(message, *args, **kwargs):
    zbot_logger.warning(message, *args, **kwargs)


def error(message, *args, **kwargs):
    zbot_logger.error(message, *args, **kwargs)


def critical(message, *args, **kwargs):
    zbot_logger.critical(message, *args, **kwargs)


def exception(message, *args, **kwargs):
    zbot_logger.exception(message, *args, **kwargs)
