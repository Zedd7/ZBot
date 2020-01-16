# ZBot

The file structure is designed to run on [Heroku](https://heroku.com) and [Repl.it](https://repl.it).

For Heroku, the root directory must contain the files:
- `Procfile` to specify the workers
- `runtime.txt` to specify the Python environment

For Repl.it, the root directory must contain the file:
- `main.py` to bootstrap the client.

The root directory must also contain a `.env` file used to store private keys. The required keys are the following : `OWNER_ID`, `BOT_TOKEN`, `MONGODB_PASSWORD`, `WG_API_APPLICATION_ID`.

If ran on Heroku, Repl.it or similar host where idle processes are likely to be killed, a < 30 min automatic ping must be scheduled to keep the Flask server alive.
Use of [UptimeRobot](https://uptimerobot.com/) is recommended.
