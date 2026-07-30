import asyncio
import os

_SAVE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stickers")


async def on_message(bot, msg):
    if msg["text"].strip().lower() != "/dl":
        return

    if msg.get("quoted_awe_type") != 1805:
        return

    quoted_id = str(msg.get("quoted_msg_id", ""))
    cached = bot.get_message(quoted_id)
    if not cached or not cached.get("sticker_url"):
        await bot.send_message(text="sticker not in cache, send it again and retry", msg=msg)
        return

    await bot.send_reaction(msg=msg, emoji="✍️")
    try:
        result = await bot.download(cached)
    except Exception as e:
        await bot.send_message(text=f"download error: {e}", msg=msg)
        await bot.remove_reaction(msg=msg, emoji="✍️")
        return

    if not result:
        await bot.send_message(text="no se pudo descargar el sticker", msg=msg)
        await bot.remove_reaction(msg=msg, emoji="✍️")
        return

    data, filename = result
    os.makedirs(_SAVE_DIR, exist_ok=True)
    path = os.path.join(_SAVE_DIR, filename)
    with open(path, "wb") as f:
        f.write(data)

    await bot.send_message(text=f"saved: {path}", msg=msg)
    await bot.remove_reaction(msg=msg, emoji="✍️")
