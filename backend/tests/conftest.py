import os

# Settings require a bot token; tests never talk to Telegram.
os.environ.setdefault("BOT_TOKEN", "123456:TEST")
