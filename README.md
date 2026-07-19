# LTTK - TikTok DM Bot

> [!IMPORTANT]
> **NO AUTOMATED BROWSERS** - this is pure API. No Selenium, no Playwright, no Puppeteer. Everything goes through TikTok's internal endpoints directly.

Python bot for TikTok DMs. Connects to TikTok's internal WebSocket, reads incoming messages and runs plugins on them.

> **Disclaimer:** This is a reverse-engineered TikTok client. Use at your own risk. Not affiliated with TikTok/ByteDance.

This started as a personal project and I decided to share it. It's early stage - expect rough edges, and expect improvements over time.

---

## Features

- Real-time DMs via WebSocket (`wss://im-ws-va.tiktok.com/ws/v2`)
- 1-on-1 and group conversations
- Text, videos, photos, music, stickers, voice notes, stories, live streams and more
- Reactions and message deletions
- Auto re-login with QR when session expires
- Plugin system with hot-reload - just edit the file, no restart needed
- QR login, no password needed

---

## Structure

```
bot/
├── main.py
├── client.py
├── config.py
├── log.py
├── qrlogin.py
├── sesion/
│   └── username.json
├── core/
│   ├── api.py
│   ├── proto.py
│   └── signer_client.py
└── plugins/
    ├── ping.py
    ├── info.py
    ├── react.py
    ├── menu.py
    └── videodl.py
```

---

## Requirements

- Python 3.10+
- A signing service running at the URL set in `core/signer_client.py`

```bash
pip install -r requirements.txt
```

---

## Usage

```bash
python main.py
```

First run opens a QR code - scan it with TikTok and the session gets saved to `sesion/<username>.json`. After that, just run the same command and it picks up the session automatically. If it expires it'll ask for QR again.

### Console commands

| Command | What it does |
|---|---|
| `retry` | Reconnect |
| `stop` | Stop the bot, keep the session |
| `close` | Logout from TikTok, delete session file and stop |

---

## Built-in commands

| Command | Description |
|---|---|
| `/ping` | Replies "pong" and deletes after 3s |
| `/info` | Shows sender's username and user ID |
| `/react [emoji]` | Reacts to the message |
| `/menu` | Shows available commands |

Videos and photos shared in DMs get downloaded and re-hosted automatically.

---

## Writing a plugin

Drop a `.py` file in `plugins/` and it loads automatically.

```python
# plugins/hello.py

async def on_message(bot, msg):
    if msg["text"].strip() == "/hello":
        await bot.send_message(text="hello!", msg=msg)
```

### Hooks

| Hook | When |
|---|---|
| `on_start(bot)` | Bot connected |
| `on_message(bot, msg)` | New message |
| `on_reaction(bot, rxn)` | Reaction added or removed |
| `on_delete(bot, deleted)` | Message deleted |

### `msg` fields

| Field | |
|---|---|
| `msg["text"]` | Message text |
| `msg["sender_id"]` | Sender's user ID |
| `msg["conv_id"]` | Conversation ID |
| `msg["msg_id"]` | Message ID |
| `msg["msg_type"]` | Internal type (for reactions/deletes) |
| `msg["awe_type"]` | Content type (1=text, 800=video, 1813=voice...) |
| `msg["is_group"]` | True if group chat |
| `msg["video_id"]` | Video ID (awe_type 800/810) |
| `msg["quoted_text"]` | Quoted message text |

### Bot methods

```python
# send a text message
await bot.send_message(text="hello!", msg=msg)

# react to a message
await bot.send_reaction(emoji="🔥", msg=msg)

# remove a reaction
await bot.remove_reaction(emoji="🔥", msg=msg)

# delete a message
await bot.delete_message(msg=msg)

# share a video (conv_id from msg, item_id is the TikTok video ID)
await bot.send_video(msg["conv_id"], "7123456789")

# get a user's profile
user = await bot.get_user(msg["sender_id"])
print(user["unique_id"], user["nick_name"])
```

---

## Message types (`awe_type`)

| Value | Type |
|---|---|
| `1` | Text |
| `22` | Music |
| `25` | User profile |
| `40` | Video comment |
| `800` / `810` | Video / photo |
| `1021` | Live stream |
| `1025` | Story |
| `1805` | Sticker |
| `1813` | Voice note |
| `1814` | Greeting card |
| `50001` | Group event |

---

## Multiple sessions

Each account has its own file in `sesion/`. The bot loads the first one it finds. To switch accounts just remove or rename the files.

Don't commit `sesion/` to git, it has your cookies.

---

## Contributing

PRs, fixes and ideas are welcome. If you find something broken or want to add something, go for it.

---

## License

MIT
