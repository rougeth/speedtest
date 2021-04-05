# speedtest

![](https://media.giphy.com/media/3og0INAY5MLmEBubyU/giphy.gif)

A script to monitor and notify internet speed.

- Monitor download, upload and ping, every 10min, using [speedtest-cli](https://github.com/sivel/speedtest-cli).
- Reports through a Telegram bot.

## Usage

### Install

You can install the dependencies with the good and old requirements.txt:
```
$ pip install -r requirements.txt
```

### Monitor
The monitor job will create a JSON file for each speed test it runs in the folder defined at `--path`:
```
$ python speed.py --path /path/to/output
```

### Telegram bot

If you can to see the reports through Telegram, create a bot (Message `@botfather` at the app for more info) and get its token to use here:
```
$ python speed.py --path /path/to/output --token <telegram-bot-token> --id <your-telegram-id> 
```
Your Telegram ID is required so that the bot replies only to you. You can run it without it and use the command `/myid` to get your Telegram user ID. After that, you can use the commands `/today` and `/last_week` at the bot you created and see today's and last seven day's speed tests.

### Using Docker
You can also use Docker to run both the monitor and bot:
```
# Considering you can the reports to be stored at ~/speedtests
$ docker run -it -v ~/speedtests/output -d rougeth/speedtest --path /output
$ docker run -it -v ~/speedtests:/output -d rougeth/speedtest --path /output --id <your-telegram-id> --token <telegram-bot-token>
```
