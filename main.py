import asyncio
import logging

import uvicorn
from pyrogram import Client, idle

from bot.commands import register_handlers
from bot.config import Config
from bot.engine import POOL
from web.app import app

logging.basicConfig(
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logger = logging.getLogger("tg-stream-bot")


async def _start_clients():
    primary = Client(
        "stream-bot",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        bot_token=Config.BOT_TOKEN,
        in_memory=True,
    )
    await primary.start()
    POOL.register(primary)
    register_handlers(primary)

    extras = []
    for i, token in enumerate(Config.STREAM_TOKENS):
        client = Client(
            f"stream-bot-extra-{i}",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=token,
            in_memory=True,
        )
        await client.start()
        POOL.register(client)
        extras.append(client)

    return primary, extras


async def main():
    primary, extras = await _start_clients()
    logger.info(
        "Connected with %d client(s). Streaming base URL: %s",
        1 + len(extras),
        Config.BASE_URL,
    )

    server = uvicorn.Server(
        uvicorn.Config(app, host=Config.HOST, port=Config.PORT, log_level="warning")
    )

    try:
        await asyncio.gather(server.serve(), idle())
    finally:
        await primary.stop()
        for client in extras:
            await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
