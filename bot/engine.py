"""Pulls bytes out of Telegram for the web layer to serve.

Uses Pyrogram's ``Client.stream_media`` (an async generator over a message's
media, yielding fixed-size chunks) rather than raw MTProto calls -- it's the
same mechanism ``download_media`` uses internally, so it's transparently
subject to Pyrogram's own DC/flood-wait handling.

``stream_media`` returns whole 1 MiB-ish chunks addressed by *chunk index*,
not by byte offset, so ``iter_range`` below does the offset math to trim the
first and last chunk down to the exact byte range an HTTP client asked for.
"""

from asyncio import Semaphore
from itertools import cycle

from .config import Config

_CHUNK = 1024 * 1024  # Pyrogram's internal stream_media chunk size
_gate = Semaphore(max(4, Config.STREAM_GATE))


class StreamError(Exception):
    """Raised when a file can't be located or streamed."""


class ClientPool:
    """Round-robins requests across one or more logged-in bot clients."""

    def __init__(self):
        self._clients = []
        self._cycle = None

    def register(self, client):
        self._clients.append(client)
        self._cycle = cycle(self._clients)

    def pick(self):
        if not self._clients:
            raise StreamError("no Telegram clients are connected")
        return next(self._cycle)

    def __bool__(self):
        return bool(self._clients)


POOL = ClientPool()


def media_of(message):
    """Return the downloadable media object on a message, or raise."""
    media = (
        message.video
        or message.document
        or message.audio
        or message.animation
        or message.voice
        or message.video_note
    )
    if media is None:
        raise ValueError("message has no downloadable media")
    return media


async def probe(chat_id, msg_id):
    """Fetch name/mime/size for a stored (chat_id, msg_id) pair."""
    client = POOL.pick()
    message = await client.get_messages(chat_id, msg_id)
    if message is None or message.empty:
        raise StreamError("source message is gone")
    media = media_of(message)
    return {
        "name": getattr(media, "file_name", "") or "file",
        "mime": getattr(media, "mime_type", "") or "application/octet-stream",
        "size": getattr(media, "file_size", 0) or 0,
    }


async def iter_range(client, message, start, end):
    """Yield bytes for the inclusive byte range [start, end] of a message's media.

    Wraps ``client.stream_media`` and trims the first/last underlying chunk
    to line up with the exact bytes requested (needed for HTTP Range
    requests, i.e. video seeking).
    """
    offset = start // _CHUNK
    first_cut = start % _CHUNK
    last_cut = end % _CHUNK + 1
    part_count = (end // _CHUNK) - offset + 1

    current = 0
    async with _gate:
        async for chunk in client.stream_media(message, offset=offset, limit=part_count):
            if not chunk:
                break
            if part_count == 1:
                yield chunk[first_cut:last_cut]
            elif current == 0:
                yield chunk[first_cut:]
            elif current == part_count - 1:
                yield chunk[:last_cut]
            else:
                yield chunk
            current += 1
