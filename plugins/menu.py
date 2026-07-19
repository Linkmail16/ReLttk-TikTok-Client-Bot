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
    await bot.send_message(text=MENU_TEXT, msg=msg)
