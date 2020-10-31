import sys

import keep_alive
import zbot.zbot as bot

MIN_PYTHON = (3, 9)
if sys.version_info < MIN_PYTHON:
    sys.exit("Python %s.%s or later is required." % MIN_PYTHON)

if __name__ == '__main__':
    keep_alive.keep_alive()
    bot.run()
