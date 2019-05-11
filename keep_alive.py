from threading import Thread

from flask import Flask

app = Flask('')


@app.route('/')
def home():
    return "App ready."


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    """Prepare the server and allow it to be pinged."""
    server = Thread(target=run)
    server.start()
