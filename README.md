# LTTK - TikTok DM Bot

> [!IMPORTANT]
> **NO AUTOMATED BROWSERS** - this is pure API. No Selenium, no Playwright, no Puppeteer. Everything goes through TikTok's internal endpoints directly.

Python bot for TikTok DMs. Connects to TikTok's internal WebSocket, reads incoming messages and runs plugins on them.

> **Disclaimer:** This is a reverse-engineered TikTok client. Use at your own risk. Not affiliated with TikTok/ByteDance.

This started as a personal project and I decided to share it. It's early stage - expect rough edges, and expect improvements over time.

When will I fully add the API? My rooted phone was stolen. Once I buy a new one, I'll implement many more features, like sending audio, images, and videos, un-sending messages, calls, streak pets, profiles, feeds, music, creating groups, joining groups, editing groups, managing groups, and much more.

---
# Changelog


### Added
- `client.py`: Message database (SQLite) — persists received messages locally, max 1000 entries
  - `_init_msg_db()`, `_store_msg()`, `get_message()`, `get_messages()`
- `client.py`: Conversation history API
  - `fetch_history()`, `fetch_history_raw()`, `_parse_history_response()`, `_parse_history_msg()`
- `client.py`: `_proto_to_dict()` — converts raw protobuf bytes to dict for inspection
- `client.py`: `get_conversations()`, `get_groups()`, `get_private_chats()` — list and filter conversations
- `client.py`: `download(msg)` — downloads stickers, videos and voice messages
- `core/api.py`: `_fetch_inbox()`, `_parse_inbox()`, `get_conversations()` — inbox fetch with full conversation metadata (name, is_group, unread, member_count, avatar)
- `core/api.py`: `get_conversation_history()` — paginated history fetch with cursor support
- `core/api.py`: `_varint()`, `_pb_varint()`, `_pb_bytes()`, `_pb_str()` — protobuf encoding helpers
- `plugins/stickerdl.py`: `/dl` command to download quoted stickers, saves to `stickers/`
- `main.py`: `cookies <path>` argument — import cookies from JSON file
- `main.py`: `browser <name>` argument — import cookies from browser (Chrome, Firefox, etc.)
- `browsercookies.py`: helper to extract TikTok cookies from local browser storage

### Changed
- `core/api.py`: Rewrote `get_group_names()` — was broken (wrong payload + wrong parser), now delegates to `_fetch_inbox()` + `_parse_inbox()`
- `client.py`: `_dispatch()` now calls `_store_msg()` to persist messages as they arrive
- `client.py`: `get_group_name()` — no longer stays stuck on loaded=True if the result was empty; retries on next message
- `client.py`: `send_message()` now logs sent messages
- `client.py`: `_parse()` — now also extracts `sticker_url`, `quoted_sticker_url`, `quoted_sticker_id`
- `plugins/videodl.py`: Added group chat support — retrieves quoted video from message cache



## Features

- Real-time DMs via WebSocket
- 1-on-1 and group conversations
- Text, videos, photos, music, stickers, voice notes, stories, live streams and more
- Reactions and message deletions
- Conversation history fetch with pagination
- Local message cache (SQLite)
- Download stickers, videos, and voice notes
- List conversations, filter groups or private chats
- Auto re-login with QR when session expires
- Plugin system with hot-reload - just edit the file, no restart needed
- QR login, no password needed

---

## Structure

```
lttk/
├── main.py
├── client.py
├── config.py
├── log.py
├── qrlogin.py
├── browsercookies.py
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
    ├── videodl.py
    └── stickerdl.py
```

---

## Requirements

- Python 3.10+
- A signing service running at the URL set in `core/signer_client.py`
- `pycryptodome` — only needed if you use the `browser` cookie import feature

```bash
pip install -r requirements.txt
```

---

## Usage

```bash
python main.py
```

First run opens a QR code - scan it with TikTok and the session gets saved to `sesion/<username>.json`. After that, just run the same command and it picks up the session automatically. If it expires it'll ask for QR again.

### Import cookies from a file

```bash
python main.py cookies cookies.json
```

Accepts a JSON array (exported from a browser extension) or a plain `{"name": "value"}` object.

### Import cookies from your browser

```bash
python main.py browser chrome
python main.py browser firefox
```

Reads TikTok cookies directly from your local browser profile. No export needed.

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
| `/dl` | Download a quoted sticker (saves to `stickers/`) |

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
| `msg["sticker_url"]` | Sticker URL (awe_type 1805) |
| `msg["voice_id"]` | Voice note ID (awe_type 1813) |
| `msg["quoted_text"]` | Quoted message text |
| `msg["quoted_awe_type"]` | Quoted message content type |
| `msg["proto"]` | Raw protobuf fields as dict |

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

# fetch conversation history (returns list of msg dicts)
msgs = await bot.fetch_history(msg["conv_id"], count=20)

# get a cached message by ID
cached = bot.get_message(msg["msg_id"])

# get recent cached messages from a conversation
recent = bot.get_messages(msg["conv_id"], limit=50)

# download a sticker, video or voice note
result = await bot.download(msg)
if result:
    data, filename = result

# list all conversations
convs = await bot.get_conversations()

# only groups
groups = await bot.get_groups()

# only private chats
privates = await bot.get_private_chats()

# get a TikTok video's detail
detail = await bot.get_item("7123456789")

# get a music track's detail
track = await bot.get_music("7123456789")

# inspect the raw protobuf fields of a received message
import json
print(json.dumps(msg["proto"], indent=2, default=str))

# fetch raw history response bytes (useful for debugging the protobuf)
raw = await bot.fetch_history_raw(msg["conv_id"], count=20)

# parse any protobuf blob to a dict
parsed = bot._proto_to_dict(raw)
print(json.dumps(parsed, indent=2, default=str))
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
