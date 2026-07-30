import json


async def on_message(bot, msg):
    if msg.get("awe_type") != 1805:
        return

    print(f"\n=== STICKER {msg['sticker_id']} ===")
    print(f"sticker_type:             {msg['sticker_type']}")
    print(f"sticker_url:              {msg['sticker_url']}")
    print(f"sticker_origin_video_id:  {msg['sticker_origin_video_id']}")
    print(f"sticker_creator_uid:      {msg['sticker_creator_uid']}")
    print("--- proto ---")
    print(json.dumps(msg["proto"], indent=2, default=str))
