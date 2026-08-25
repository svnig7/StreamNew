from pyrogram import filters
from pyrogram.types import Message

from .config import Config
from .db import add_stream
from .engine import media_of


def register_handlers(client):
    """Wire up /start and /stream on the given (primary) Client."""

    @client.on_message(filters.command("start"))
    async def start(_, message: Message):
        await message.reply_text(
            "Send me a video, document, or audio file (or reply to one "
            "already in this chat) with /stream and I'll give you a "
            "shareable playback link."
        )

    @client.on_message(filters.command("stream"))
    async def stream(_, message: Message):
        target = message.reply_to_message or message

        try:
            media = media_of(target)
        except ValueError:
            await message.reply_text(
                "Reply to a video, document, or audio message with /stream "
                "(or attach media directly to the /stream message)."
            )
            return

        name = getattr(media, "file_name", "") or "file"
        mime = getattr(media, "mime_type", "") or "application/octet-stream"
        size = getattr(media, "file_size", 0) or 0

        status = await message.reply_text("Generating link...")

        token = await add_stream(target.chat.id, target.id, name, mime, size)
        if not token:
            await status.edit_text("Could not generate a link, try again.")
            return

        watch = f"{Config.BASE_URL}/watch/{token}"
        direct = f"{Config.BASE_URL}/dl/{token}"
        playable = mime.startswith(("video/", "audio/"))
        size_mb = size / (1024 * 1024)

        lines = [f"<b>{name}</b>", f"Size: {size_mb:.1f} MB", ""]
        if playable:
            lines.append(f"▶️ <a href='{watch}'>Watch</a>")
        lines.append(f"⬇️ <a href='{direct}'>Download</a>")

        await status.edit_text("\n".join(lines), disable_web_page_preview=True)
