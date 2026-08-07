import random

_INVIS = ["​", "‌", "‍", "⁠", "﻿"]

def _pad(text):
    chars = random.choices(_INVIS, k=random.randint(1, 4))
    pos = random.randint(0, len(text))
    return text[:pos] + "".join(chars) + text[pos:]

MENU_TEXT = (
    "commands:\n"
    "/ping — check if the bot is alive\n"
    "/info — show your profile\n"
    "/react [emoji] — react to the message\n"
    "/menu — show this menu"
)

async def on_message(bot, msg):
    if msg["text"].strip().lower() != "/menu":
        return
    await bot.send_message(text=_pad(MENU_TEXT), msg=msg)
