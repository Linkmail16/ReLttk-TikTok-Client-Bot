import asyncio
import io
import json
import urllib.request
import urllib.error

try:
    from .. import config
except ImportError:
    import importlib, os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    _pkg = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config = importlib.import_module(f"{_pkg}.config")

_UA_DL = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
_UPLOAD_URL = "https://linkmail.wtf/cut/upload"


def _cookie_header():
    return "; ".join(f"{k}={v}" for k, v in config.COOKIES.items())


def _download_video(url: str) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA_DL,
        "Referer":    "https://www.tiktok.com/",
        "Cookie":     _cookie_header(),
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _upload(data: bytes, filename: str) -> str:
    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: video/mp4\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(_UPLOAD_URL, data=body, method="POST", headers={
        "User-Agent":   _UA_DL,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept":       "application/json",
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
    return result["url"]


async def on_message(bot, msg):
    if msg["is_group"]:
        if msg["text"].strip().lower() != "/dl":
            return
        quoted = bot.get_message(str(msg.get("quoted_msg_id", "")))
        if not quoted or quoted.get("awe_type") not in (800, 810) or not quoted.get("video_id"):
            return
        msg = quoted
    elif msg["awe_type"] not in (800, 810) or not msg["video_id"]:
        return

    detail = await bot.get_item(msg["video_id"])
    if not detail:
        await bot.send_message(text="couldn't get video info", msg=msg)
        return

    item = detail.get("itemInfo", {}).get("itemStruct", {})
    if not item:
        await bot.send_message(text="couldn't get video info", msg=msg)
        return

    video = item.get("video", {})
    download_url = video.get("playAddr") or ""

    if not download_url:
        await bot.send_message(text="no download URL found", msg=msg)
        return

    await bot.send_message(text="⏳ downloading...", msg=msg)
    await bot.send_reaction(msg=msg, emoji="✍️")
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, _download_video, download_url)
    except Exception as e:
        await bot.send_message(text=f"download error: {e}", msg=msg)
        return

    filename = f"{msg['video_id']}.mp4"
    try:
        url = await asyncio.get_event_loop().run_in_executor(None, _upload, data, filename)
    except urllib.error.HTTPError as e:
        if e.code == 413:
            await bot.send_message(text="video is too large", msg=msg)
            await bot.remove_reaction(msg=msg, emoji="✍️")
        else:
            await bot.send_message(text=f"upload error: {e}", msg=msg)
        return
    except Exception as e:
        await bot.send_message(text=f"upload error: {e}", msg=msg)
        return

    await bot.send_message(text=url, msg=msg)
    await bot.remove_reaction(msg=msg, emoji="✍️")
