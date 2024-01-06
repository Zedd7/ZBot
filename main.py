import os
import sys

from dotenv import load_dotenv
from flask import Flask
from waitress import serve

import zbot.zbot as bot


load_dotenv()


MIN_PYTHON = (3, 12)
if sys.version_info < MIN_PYTHON:
    sys.exit(f"Python {MIN_PYTHON=} or later is required.")

app = Flask('')


@app.route('/')
def index():
    return "<h1>App ready!</h1>"


if __name__ == '__main__':
    # bot.run()
    serve(app, host='0.0.0.0', port=os.getenv('PORT'))
