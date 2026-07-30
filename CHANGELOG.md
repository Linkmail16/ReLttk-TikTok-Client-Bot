# Changelog

## [Unreleased]

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
- `core/__init__.py`: Added exports `get_conversation_history`, `get_conversations_api`
