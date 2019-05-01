# ZBot

The file structure is designed to run on [Repl.it](https://repl.it). \
Specificaly, the root directory must contain a `main.py` file used to bootstrap the client.

The root directory must also contain a `.env` file used to store private keys. \
The required keys are the following : `BOT_TOKEN`, `MONGODB_PASSWORD`, `WG_API_APPLICATION_ID`.

If ran on Repl.it or similar host where idle processes are likely to be killed, a < 60 min automatic ping must be scheduled to keep the Flask server alive.
Use of [UptimeRobot](https://uptimerobot.com/) is recommended.