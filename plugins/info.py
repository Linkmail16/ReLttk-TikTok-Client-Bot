async def on_message(bot, msg):
    if msg["text"].strip().lower() != "/info":
        return

    user = await bot.get_user(msg["sender_id"])
    if not user:
        await bot.send_message(msg["conv_id"], "couldn't get your profile")
        return

    follow  = "following" if user.get("follow_status") == 2 else "not following"
    follows = "follows you" if user.get("follower_status") == 1 else "doesn't follow you"

    text = (
        f"@{user['unique_id']}\n"
        f"Nombre: {user['nick_name']}\n"
        f"ID: {user['user_id_str']}\n"
        f"{follow} · {follows}"
    )
    await bot.send_message(msg["conv_id"], text, quote={
        "text":     msg["text"],
        "uid":      msg["sender_id"],
        "sec_uid":  msg["sec_uid"],
        "awe_type": msg["awe_type"],
        "msg_id":   msg["msg_id"],
        "msg_type": msg["msg_type"],
    })
