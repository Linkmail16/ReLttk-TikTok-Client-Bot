import asyncio

async def on_message(bot, msg):
    text = msg["text"].strip()
    if text.lower().startswith("/react"):
        parts = text.split(maxsplit=1)
        emoji = parts[1] if len(parts) > 1 else "👍"
        await bot.send_reaction(msg=msg, emoji=emoji)
        await asyncio.sleep(1)
        await bot.remove_reaction(msg=msg, emoji=emoji)
