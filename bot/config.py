"""Environment-driven configuration for the bot and web server."""

import os

from dotenv import load_dotenv

load_dotenv()


def _split(env_val):
    return [x.strip() for x in (env_val or "").split(",") if x.strip()]


def _require(name):
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


class Config:
    API_ID = int(_require("API_ID"))
    API_HASH = _require("API_HASH")
    BOT_TOKEN = _require("BOT_TOKEN")

    # Optional extra bot tokens to spread streaming load across.
    # Each must be a member/admin wherever the media lives.
    STREAM_TOKENS = _split(os.environ.get("STREAM_TOKENS"))

    # Public URL the bot is reachable at (behind your reverse proxy / tunnel).
    BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8080").rstrip("/")
    PORT = int(os.environ.get("PORT", "8080"))
    HOST = os.environ.get("HOST", "0.0.0.0")

    # Size, in bytes, of each chunk pulled from Telegram while streaming.
    STREAM_CHUNK = int(os.environ.get("STREAM_CHUNK", 1024 * 1024))

    # Max concurrent Telegram file-chunk requests in flight at once.
    STREAM_GATE = int(os.environ.get("STREAM_GATE", 24))

    DB_PATH = os.environ.get("DB_PATH", "data/streams.json")
