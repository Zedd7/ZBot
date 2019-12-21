import logging
import logging.handlers
import pathlib
import sys

DEFAULT_LOG_FILE = pathlib.Path('./logs/log')
DEFAULT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def setup_handler(logger, handler, set_suffix=False):
    if set_suffix:
        handler.suffix = '%Y-%m-%d_%H-%M-%S'
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)


_logger = logging.getLogger('zbot')
_logger.setLevel(logging.DEBUG)
setup_handler(_logger, logging.StreamHandler(sys.stdout))
setup_handler(_logger, logging.handlers.TimedRotatingFileHandler(DEFAULT_LOG_FILE, when='midnight', encoding='utf-8'), set_suffix=True)


def debug(message, *args, **kwargs):
    _logger.debug(message, *args, **kwargs)


def info(message, *args, **kwargs):
    _logger.info(message, *args, **kwargs)


def warning(message, *args, **kwargs):
    _logger.warning(message, *args, **kwargs)


def error(message, *args, **kwargs):
    _logger.error(message, *args, **kwargs)


def critical(message, *args, **kwargs):
    _logger.critical(message, *args, **kwargs)