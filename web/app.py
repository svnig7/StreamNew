from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from bot.db import get_stream
from bot.engine import POOL, iter_range

app = FastAPI(title="tg-stream-bot")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _disposition(name, inline):
    kind = "inline" if inline else "attachment"
    return f"{kind}; filename*=UTF-8''{quote(name, safe='')}"


def _parse_range(header, size):
    """Return (start, end) inclusive byte range for a Range header, or full file."""
    if not header or not header.lower().startswith("bytes="):
        return 0, size - 1
    spec = header[6:].split(",", 1)[0].strip()
    start_s, _, end_s = spec.partition("-")
    if start_s == "":
        # "bytes=-N" -> last N bytes
        n = int(end_s or 0)
        return max(0, size - n), size - 1
    start = int(start_s)
    end = int(end_s) if end_s else size - 1
    return start, min(end, size - 1)


@app.get("/watch/{token}", response_class=HTMLResponse)
async def watch(token: str, request: Request):
    rec = await get_stream(token)
    if not rec:
        raise HTTPException(404, "Unknown link")
    return templates.TemplateResponse(request, "watch.html", {"token": token})


@app.get("/api/meta/{token}")
async def meta(token: str):
    rec = await get_stream(token)
    if not rec:
        raise HTTPException(404, "Unknown link")
    return JSONResponse(
        {
            "name": rec["name"],
            "mime": rec["mime"],
            "size": rec["size"],
            "playable": rec["mime"].startswith(("video/", "audio/")),
        }
    )


async def _serve(token, request, inline):
    rec = await get_stream(token)
    if not rec:
        raise HTTPException(404, "Unknown link")

    size = rec["size"]
    if size <= 0:
        raise HTTPException(404, "File has no known size")

    range_header = request.headers.get("range")
    start, end = _parse_range(range_header, size)
    if start < 0 or end < start or start >= size:
        raise HTTPException(416, "Invalid range")

    client = POOL.pick()
    message = await client.get_messages(rec["chat_id"], rec["msg_id"])
    if message is None or message.empty:
        raise HTTPException(404, "Source message is gone")

    partial = range_header is not None
    headers = {
        "Content-Type": rec["mime"],
        "Content-Length": str(end - start + 1),
        "Accept-Ranges": "bytes",
        "Content-Disposition": _disposition(rec["name"], inline),
        "Cache-Control": "private, max-age=86400",
    }
    if partial:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"

    return StreamingResponse(
        iter_range(client, message, start, end),
        status_code=206 if partial else 200,
        headers=headers,
    )


@app.get("/stream/{token}", name="stream")
async def stream_route(token: str, request: Request):
    return await _serve(token, request, inline=True)


@app.get("/dl/{token}", name="download")
async def dl_route(token: str, request: Request):
    return await _serve(token, request, inline=False)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    if request.url.path.startswith(("/api/", "/stream/", "/dl/")):
        return JSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)
    return HTMLResponse(
        f"<h1>{exc.status_code}: {exc.detail}</h1>", status_code=exc.status_code
    )
