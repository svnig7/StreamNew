# tg-stream-bot

A minimal Telegram bot with a single command: **`/stream`**. Reply to any
video, document, or audio message with `/stream` and the bot replies with a
shareable browser link that plays (or downloads) the file straight off
Telegram's servers — no re-upload, no local storage.

## How it works

```
Browser ──► FastAPI (web/app.py)
                │  Range requests, HTML player page
                ▼
        Pyrogram Client.stream_media()
                │  pulls fixed-size chunks from Telegram
                ▼
             Telegram
```

Everything runs in a single process on one asyncio event loop: `main.py`
starts the Pyrogram client(s) and hands the FastAPI app to `uvicorn`,
running both concurrently.

- **`bot/engine.py`** — `iter_range()` wraps `Client.stream_media()` and
  trims the first/last chunk to the exact byte range a browser's `Range`
  header asked for. This is what makes seeking in the video player work.
- **`bot/db.py`** — a tiny JSON-file token store mapping short tokens to
  `(chat_id, message_id)`. Swap it for a real database if you need more
  than single-instance, low-volume use.
- **`web/app.py`** — `/stream/{token}` and `/dl/{token}` serve the file
  with proper `Accept-Ranges`/`Content-Range` headers; `/watch/{token}`
  serves a small HTML page with a native `<video>`/`<audio>` element.

## Setup

1. **Get credentials**
   - `API_ID` / `API_HASH` from <https://my.telegram.org> → API Development Tools
   - `BOT_TOKEN` from [@BotFather](https://t.me/BotFather)

2. **Configure**
   ```bash
   cp .env.example .env
   # edit .env with your values
   ```

3. **Install & run**
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   python main.py
   ```

4. **Expose it publicly**
   The bot only binds to `127.0.0.1:$PORT` by default in most deployments
   behind a proxy — point a reverse proxy (nginx, Caddy) or a tunnel
   (`cloudflared tunnel`, `ngrok http 8080`) at it, and set `BASE_URL` in
   `.env` to that public address. `BASE_URL` is what gets embedded in every
   `/stream` link, so it must be reachable by whoever you send links to.

## Usage

In your bot chat:
1. Send or forward a video/document/audio file.
2. Reply to it with `/stream`.
3. The bot replies with **Watch** and **Download** links.

## Scaling streaming load

If one bot account isn't enough (Telegram bots have per-account rate
limits), add more bot tokens to `STREAM_TOKENS` in `.env` (comma-separated).
Each additional bot must also have access to wherever the source media
lives (e.g. be a member of the same chat/channel), since it needs to be
able to read the message to stream it. Requests round-robin across all
registered clients.

## Limitations (by design, for minimalism)

- Single command only — no playlists, custom posters, expiring links, or
  link deletion. The [WZML-X](https://github.com/SilentDemonSD/WZML-X)
  project this was extracted from has a much larger feature set if you
  need those.
- JSON-file token store — fine for personal/small-group use, not for high
  write volume.
- No auth on the web endpoints beyond the unguessable token — anyone with
  a link can view/download that one file.

## License

MIT — see [LICENSE](LICENSE).
