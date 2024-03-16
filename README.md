# Study Discord Bot


## Local Development Quick Start 

```bash
> cd group-discord-bot-local-env
> docker-compose up
> source /env/bin/activate
```
create a local .env
```bash
> touch .env
```
add the following to your .env file
```text
DISCORD_BOT_TOKEN=REPLACE_THIS_WITH_YOUR_DISCORD_BOT_TOKEN
MONGODB_CONNECTION_STRING=mongodb://root:password@localhost/study_bot_db?authSource=admin
```

```bash
> python bot.py
```