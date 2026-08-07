import asyncio
import random

_INVIS = ["​", "‌", "‍", "⁠"]

def _pad(text):
    chars = random.choices(_INVIS, k=random.randint(1, 4))
    pos = random.randint(0, len(text))
    return text[:pos] + "".join(chars) + text[pos:]

async def on_message(bot, msg):
    if msg["text"].strip().lower() == "/ping":
        sent_type = await bot.send_message(text=_pad("pong"), msg=msg)
        await asyncio.sleep(3)
        await bot.delete_message(conv_id=msg["conv_id"], msg_type=sent_type)
