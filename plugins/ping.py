import asyncio

async def on_message(bot, msg):
    if msg["text"].strip().lower() == "/ping":
        sent_type = await bot.send_message(text="pong", msg=msg)
        await asyncio.sleep(3)
        await bot.delete_message(conv_id=msg["conv_id"], msg_type=sent_type)
