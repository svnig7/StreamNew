"""Tiny JSON-file token store.

Good enough for a single-instance minimal bot. Swap this module out for a
real database (SQLite, Postgres, MongoDB, ...) if you outgrow it -- every
other module only imports the four functions below.
"""

import json
import os
from asyncio import Lock
from secrets import token_urlsafe

from .config import Config

_lock = Lock()
_cache = None


def _load():
    global _cache
    if _cache is not None:
        return _cache
    if os.path.exists(Config.DB_PATH):
        with open(Config.DB_PATH, "r") as fh:
            _cache = json.load(fh)
    else:
        _cache = {}
    return _cache


def _persist():
    os.makedirs(os.path.dirname(Config.DB_PATH) or ".", exist_ok=True)
    with open(Config.DB_PATH, "w") as fh:
        json.dump(_cache, fh)


async def add_stream(chat_id, msg_id, name, mime, size):
    """Return an existing token for this message, or mint a new one."""
    async with _lock:
        data = _load()
        for token, rec in data.items():
            if rec["chat_id"] == chat_id and rec["msg_id"] == msg_id:
                return token
        for _ in range(6):
            token = token_urlsafe(5)
            if token not in data:
                data[token] = {
                    "chat_id": chat_id,
                    "msg_id": msg_id,
                    "name": name,
                    "mime": mime,
                    "size": size,
                }
                _persist()
                return token
    return None


async def get_stream(token):
    async with _lock:
        return _load().get(token)


async def rm_stream(token):
    async with _lock:
        data = _load()
        if token in data:
            del data[token]
            _persist()
            return True
    return False
