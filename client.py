import asyncio
import importlib
import importlib.util
import os
import re
import ssl
import sys
import time
from datetime import datetime


import websockets

from . import config
from . import log as _log
from .core import build_ws_packet, build_reaction_packet, build_delete_packet, build_video_share_packet, get_user_profiles, get_own_user_id, get_item_detail, get_music_detail, get_group_names

_USER_CACHE_TTL = 60           

class _BotRestart(Exception): pass
class _BotStop(Exception): pass


class LttkClient:
    def __init__(self):
        cookie = "; ".join(f"{k}={v}" for k, v in config.COOKIES.items())

        self._ws_url = config.WS_URL
        self._headers = [
            ("User-Agent",      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"),
            ("Origin",          "https://www.tiktok.com"),
            ("Cookie",          cookie),
            ("Pragma",          "no-cache"),
            ("Cache-Control",   "no-cache"),
            ("Accept-Encoding", "gzip, deflate, br"),
            ("Accept-Language", "es-ES,es;q=0.9"),
        ]
        self._subprotocols = ["binary", "base64", "pbbp2"]
        self.websocket = None
        self._own_user_id: str = config.OWN_USER_ID
        self._plugins: dict[str, object] = {}
        self._plugin_mtimes: dict[str, float] = {}
        self._user_cache: dict[str, dict] = {}
        self._group_names: dict[str, str] = {}
        self._group_names_loaded = False
        self._active_session: str | None = None

                                                                                

    def _plugins_dir(self) -> str:
        return os.path.join(os.path.dirname(__file__), "plugins")

    def _load_plugins(self):
        pdir = self._plugins_dir()
        current = set()
        for fname in os.listdir(pdir):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            name = fname[:-3]
            path = os.path.join(pdir, fname)
            mtime = os.path.getmtime(path)
            current.add(name)
            if name not in self._plugins or self._plugin_mtimes.get(name) != mtime:
                action = "nuevo" if name not in self._plugins else "modificado"
                try:
                    spec = importlib.util.spec_from_file_location(f"bot.plugins.{name}", path)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    self._plugins[name] = mod
                    self._plugin_mtimes[name] = mtime
                    _log.plugin("lttk", action, name)
                except Exception as e:
                    _log.error("lttk", f"error cargando plugin {name}: {e}")
        for name in list(self._plugins):
            if name not in current:
                del self._plugins[name]
                del self._plugin_mtimes[name]
                _log.plugin("lttk", "eliminado", name)

                                                                                

    async def get_group_name(self, conv_id: str) -> str:
        if not self._group_names_loaded:
            try:
                names = await asyncio.get_event_loop().run_in_executor(None, get_group_names)
                self._group_names.update(names)
            except Exception as e:
                _log.error("lttk", f"error obteniendo nombres de grupos: {e}")
            self._group_names_loaded = True
        return self._group_names.get(conv_id, conv_id)

    async def get_user(self, user_id: str) -> dict | None:
        entry = self._user_cache.get(user_id)
        if entry and time.monotonic() - entry["ts"] < _USER_CACHE_TTL:
            return entry["profile"]
        try:
            profiles = await asyncio.get_event_loop().run_in_executor(
                None, get_user_profiles, [user_id]
            )
            if profiles:
                self._user_cache[user_id] = {"profile": profiles[0], "ts": time.monotonic()}
                return profiles[0]
        except Exception as e:
            _log.error("lttk", f"error obteniendo perfil {user_id}: {e}")
        return entry["profile"] if entry else None

    async def get_item(self, item_id: str) -> dict | None:
        try:
            return await asyncio.get_event_loop().run_in_executor(
                None, get_item_detail, item_id
            )
        except Exception as e:
            _log.error("lttk", f"error obteniendo video {item_id}: {e}")
        return None

    async def get_music(self, music_id: str) -> dict | None:
        try:
            return await asyncio.get_event_loop().run_in_executor(
                None, get_music_detail, music_id
            )
        except Exception as e:
            _log.error("lttk", f"error obteniendo audio {music_id}: {e}")
        return None

                                                                                

    async def send_message(self, conv_id: str = "", text: str = "",
                           short_id: int = 1, quote: dict | None = None,
                           *, msg: dict | None = None) -> int:
        is_group = False
        if msg is not None:
            if not conv_id:
                conv_id = msg["conv_id"]
            is_group = msg.get("is_group", False)
            if quote is None:
                quote = {
                    "text":     msg["text"],
                    "uid":      msg["sender_id"],
                    "sec_uid":  msg["sec_uid"],
                    "awe_type": msg["awe_type"],
                    "msg_id":   msg["msg_id"],
                    "msg_type": msg["msg_type"],
                }
        packet, msg_type = build_ws_packet(
            conv_id        = conv_id,
            short_id       = short_id,
            text           = text,
            device_id      = config.DEVICE_ID,
            sdk_ms_token   = config.MSG_SDK_MS_TOKEN,
            tt_public_key  = config.TT_PUBLIC_KEY,
            tt_client_data = config.TT_CLIENT_DATA,
            quote          = quote,
            is_group       = is_group,
        )
        await self.websocket.send(packet)
        return msg_type

    async def send_video(self, conv_id: str, item_id: str, short_id: int = 1) -> int:
        detail = await asyncio.get_event_loop().run_in_executor(None, get_item_detail, item_id)
        packet, msg_type = build_video_share_packet(
            conv_id        = conv_id,
            item_detail    = detail,
            device_id      = config.DEVICE_ID,
            sdk_ms_token   = config.MSG_SDK_MS_TOKEN,
            tt_public_key  = config.TT_PUBLIC_KEY,
            tt_client_data = config.TT_CLIENT_DATA,
            short_id       = short_id,
        )
        await self.websocket.send(packet)
        return msg_type

    async def send_reaction(self, conv_id: str = "", msg_type: int = 0,
                            sender_id: str = "", emoji: str = "❤️",
                            short_id: int = 1, *, msg: dict | None = None):
        if msg is not None:
            if not conv_id:   conv_id   = msg["conv_id"]
            if not msg_type:  msg_type  = msg["msg_type"]
            if not sender_id: sender_id = msg["sender_id"]
        packet = build_reaction_packet(
            conv_id        = conv_id,
            msg_type       = msg_type,
            emoji          = emoji,
            sender_id      = sender_id,
            device_id      = config.DEVICE_ID,
            sdk_ms_token   = config.MSG_SDK_MS_TOKEN,
            tt_public_key  = config.TT_PUBLIC_KEY,
            tt_client_data = config.TT_CLIENT_DATA,
            short_id       = short_id,
        )
        await self.websocket.send(packet)

    async def delete_message(self, conv_id: str = "", msg_type: int = 0,
                             short_id: int = 1, *, msg: dict | None = None):
        if msg is not None:
            if not conv_id:  conv_id  = msg["conv_id"]
            if not msg_type: msg_type = msg["msg_type"]
        packet = build_delete_packet(
            conv_id        = conv_id,
            msg_type       = msg_type,
            device_id      = config.DEVICE_ID,
            sdk_ms_token   = config.MSG_SDK_MS_TOKEN,
            tt_public_key  = config.TT_PUBLIC_KEY,
            tt_client_data = config.TT_CLIENT_DATA,
            short_id       = short_id,
        )
        await self.websocket.send(packet)

    async def remove_reaction(self, conv_id: str = "", msg_type: int = 0,
                              sender_id: str = "", emoji: str = "❤️",
                              short_id: int = 1, *, msg: dict | None = None):
        if msg is not None:
            if not conv_id:   conv_id   = msg["conv_id"]
            if not msg_type:  msg_type  = msg["msg_type"]
            if not sender_id: sender_id = msg["sender_id"]
        packet = build_reaction_packet(
            conv_id        = conv_id,
            msg_type       = msg_type,
            emoji          = emoji,
            sender_id      = sender_id,
            device_id      = config.DEVICE_ID,
            sdk_ms_token   = config.MSG_SDK_MS_TOKEN,
            tt_public_key  = config.TT_PUBLIC_KEY,
            tt_client_data = config.TT_CLIENT_DATA,
            short_id       = short_id,
            remove         = True,
        )
        await self.websocket.send(packet)

                                                                                

    @staticmethod
    def _read_varint(data: bytes, i: int):
        v = 0; sh = 0
        while i < len(data):
            b = data[i]; i += 1
            v |= (b & 0x7f) << sh; sh += 7
            if not (b & 0x80): break
        return v, i

    @staticmethod
    def _parse_msgbody(data: bytes) -> dict:
        import json as _json
        result = {}
        i = 0
        while i < len(data):
            if i >= len(data) or data[i] == 0: i += 1; continue
            try:
                tag, i = LttkClient._read_varint(data, i)
            except Exception: break
            field = tag >> 3; wtype = tag & 0x7
            if wtype == 0:
                v, i = LttkClient._read_varint(data, i)
                if field == 3:   result["msg_type"] = v
                elif field == 4: result["msg_id"] = v
                elif field == 5: result.setdefault("msg_type", v)
                elif field == 6: result["awe_type"] = v
                elif field == 7: result["sender_id"] = str(v)
            elif wtype == 2:
                ln, i = LttkClient._read_varint(data, i)
                if i + ln > len(data): break
                val = data[i:i+ln]; i += ln
                if field == 1:
                    try: result["conv_id"] = val.decode("utf-8")
                    except: pass
                elif field == 8:
                    try:
                        obj = _json.loads(val.decode("utf-8"))
                        result["text"] = obj.get("text", "")
                        awe = obj.get("aweType", result.get("awe_type", 0))
                        result["awe_type"] = awe
                        if awe in (800, 810):
                            result["video_id"]      = str(obj.get("itemId", ""))
                            result["video_creator"] = str(obj.get("uid", ""))
                        elif awe == 22:
                            result["music_id"]    = str(obj.get("music_id", ""))
                            result["music_title"] = obj.get("title", "")
                        elif awe == 1021:
                            result["live_room_id"]    = str(obj.get("room_id", ""))
                            result["live_owner_id"]   = str(obj.get("room_owner_id", ""))
                            result["live_owner_name"] = obj.get("room_owner_name", "")
                        elif awe == 40:
                            result["comment_text"]        = obj.get("comment", "")
                            result["comment_video_id"]    = str(obj.get("aweme_id", ""))
                            result["comment_author_name"] = obj.get("author_name", "")
                        elif awe == 50001:
                            result["group_command"]  = obj.get("command_type", 0)
                            result["group_conv_id"]  = str(obj.get("conversation_id", ""))
                            result["group_added"]    = [str(x) for x in obj.get("added_participant", [])]
                            result["group_removed"]  = [str(x) for x in obj.get("removed_participant", [])]
                        elif awe == 25:
                            result["profile_uid"]      = str(obj.get("uid", ""))
                            result["profile_sec_uid"]  = obj.get("secUID", "")
                            result["profile_name"]     = obj.get("name", "")
                    except: pass
                elif field == 18:
                                                           
                                                                                        
                    import json as _json
                    try:
                        j = 0
                        while j < len(val):
                            t2, j = LttkClient._read_varint(val, j)
                            f2 = t2 >> 3; w2 = t2 & 7
                            if w2 == 0:
                                v2, j = LttkClient._read_varint(val, j)
                                if f2 == 1: result["quoted_msg_id"] = v2
                            elif w2 == 2:
                                ln2, j = LttkClient._read_varint(val, j)
                                v2 = val[j:j+ln2]; j += ln2
                                if f2 == 2:
                                    try:
                                        ref = _json.loads(v2.decode("utf-8"))
                                        result["quoted_uid"]     = ref.get("refmsg_uid", "")
                                        result["quoted_sec_uid"] = ref.get("refmsg_sec_uid", "")
                                        result["quoted_type"]    = ref.get("refmsg_type", 0)
                                        inner = ref.get("refmsg_content", "")
                                        try:
                                            inner_obj = _json.loads(inner)
                                            result["quoted_text"]     = inner_obj.get("text", "")
                                            result["quoted_awe_type"] = inner_obj.get("aweType", 0)
                                            result["quoted_video_id"] = str(inner_obj.get("itemId", ""))
                                            result["quoted_video_uid"]= str(inner_obj.get("uid", ""))
                                        except: pass
                                    except: pass
                            else: break
                    except: pass
                elif field == 14:
                    try: result["sec_uid"] = val.decode("utf-8")
                    except: pass
            else:
                break
        return result

    @staticmethod
    def _decompress_lz4_frame(data: bytes) -> bytes | None:
        lz4_pos = data.find(b'__lz4')
        if lz4_pos == -1:
            return None
                                                                                                   
                                                                        
        i = lz4_pos + 5
                                                                                          
        if i >= len(data):
            return None
        i += 1                 
        ln = 0; sh = 0
        while i < len(data):
            b = data[i]; i += 1
            ln |= (b & 0x7f) << sh; sh += 7
            if not (b & 0x80): break
        i += ln                   
                                                                               
        if i >= len(data):
            return None
        i += 1                 
        comp_len = 0; sh = 0
        while i < len(data):
            b = data[i]; i += 1
            comp_len |= (b & 0x7f) << sh; sh += 7
            if not (b & 0x80): break
        if i + comp_len > len(data):
            return None
        compressed = data[i:i + comp_len]
        try:
            import lz4.block
            return lz4.block.decompress(compressed, uncompressed_size=65536)
        except Exception:
            return None

    @staticmethod
    def _parse_delete(data: bytes) -> dict | None:
        if b's:recall_uid' not in data:
            return None
        conv_id = ""
        sender_id = ""
        client_msg_id = ""
        m = re.search(rb'0:1:\d+:\d+', data)
        if m:
            conv_id = m.group().decode()
        m = re.search(rb's:recall_uid\x12.([\d]+)', data)
        if m:
            sender_id = m.group(1).decode()
        m = re.search(rb's:client_message_id\x12\x24([0-9a-f\-]{36})', data)
        if m:
            client_msg_id = m.group(1).decode()
        if not conv_id:
            return None
        return {"conv_id": conv_id, "sender_id": sender_id, "client_msg_id": client_msg_id}

    @staticmethod
    def _parse_reaction(data: bytes) -> dict | None:
        import json as _json
        marker = data.find(b's:property_modify')
        if marker == -1:
            return None
        j = data.find(b'{', marker)
        if j == -1:
            return None
        for end in range(min(j + 32768, len(data)), j + 20, -1):
            try:
                obj = _json.loads(data[j:end].decode("utf-8"))
                break
            except Exception:
                pass
        else:
            return None
        modifys = obj.get("Modifys", [])
        if not modifys:
            return None
        emoji_key = modifys[0].get("Key", "")
        if not emoji_key.startswith("e:"):
            return None
        conv_match = re.search(rb'0:1:(\d+):(\d+)', data)
        if not conv_match:
            return None
        return {
            "conv_id":     conv_match.group(0).decode(),
            "sender_id":   str(obj.get("UserId", "")),
            "emoji":       emoji_key[2:],
            "msg_type":    obj.get("ServerMessageId", 0),
            "op":          modifys[0].get("Op", 0),
        }

    def _parse(self, data: bytes, decompressed: bytes | None = None) -> dict | None:
        def find_msgbody(raw, depth=0):
            if depth > 8:
                return None
            i = 0
            while i < len(raw):
                if raw[i] == 0: i += 1; continue
                try:
                    tag, i = self._read_varint(raw, i)
                except Exception: break
                wtype = tag & 0x7
                if wtype == 0:
                    _, i = self._read_varint(raw, i)
                elif wtype == 2:
                    ln, i = self._read_varint(raw, i)
                    if i + ln > len(raw): break
                    val = raw[i:i+ln]; i += ln
                    if ln > 10:
                        candidate = self._parse_msgbody(val)
                        if candidate.get("conv_id") and (candidate.get("text") or candidate.get("awe_type")):
                            return candidate
                        result = find_msgbody(val, depth + 1)
                        if result:
                            return result
                else:
                    break
            return None

        msg = find_msgbody(data)
        if not msg and decompressed is not None:
            msg = find_msgbody(decompressed)
        if not msg or not msg.get("conv_id") or not (msg.get("text") or msg.get("awe_type")):
            return None

                                                 
                                                                                       
        f7_sender = msg.get("sender_id", "")

        conv_match = re.search(r'0:1:(\d+):(\d+)', msg.get("conv_id", ""))
        if conv_match:
            id_a, id_b = conv_match.group(1), conv_match.group(2)
            own = self._own_user_id
            msg["sender_id"] = id_b if id_a == own else id_a

                                                                                 
        if f7_sender == self._own_user_id:
            return None

                                                                   
        sticker_id = ""
        sticker_type = 0
        sticker_origin_video_id = ""
        sticker_creator_uid = ""
        voice_id = ""
        voice_duration = ""
        raw_search = decompressed if decompressed else data
        if msg.get("awe_type") == 1805:
            m = re.search(rb'a:sticker_id\x12.([0-9]+)', raw_search)
            if m:
                sticker_id = m.group(1).decode()
            m = re.search(rb'a:sticker_type\x12.([0-9]+)', raw_search)
            if m:
                sticker_type = int(m.group(1).decode())
            m = re.search(rb'a:origin_video_id\x12.([0-9]+)', raw_search)
            if m:
                sticker_origin_video_id = m.group(1).decode()
            m = re.search(rb'a:sticker_creator_user_id\x12.([0-9]+)', raw_search)
            if m:
                sticker_creator_uid = m.group(1).decode()
        elif msg.get("awe_type") == 1814:
                                                                                          
            m = re.search(rb'\xa2\x01[\x80-\xff][\x00-\xff]\x7a[\x80-\xff][\x00-\xff]\x12.([\x0a])(.)([\x20-\x7e\xc0-\xff].{0,250})', raw_search)
            if m:
                try:
                    msg_ln = m.group(2)[0]
                    msg["greeting_card_text"] = m.group(3)[:msg_ln].decode("utf-8", errors="replace")
                except Exception:
                    pass
        elif msg.get("awe_type") == 1813:
            m = re.search(rb'\x0a\x20([a-z0-9]{32})', raw_search)
            if m:
                voice_id = m.group(1).decode()
            m = re.search(rb'\[mensaje de voz\] (\d+:\d+)', raw_search)
            if m:
                voice_duration = m.group(1).decode()

                                                         
        story_item_id = ""
        story_uid = ""
        story_title = ""
        if msg.get("awe_type") == 1 and b'share_video_story' in raw_search:
            import json as _json
            j = raw_search.find(b'{"aweType"')
            if j != -1:
                for end in range(min(j + 4096, len(raw_search)), j + 20, -1):
                    try:
                        obj = _json.loads(raw_search[j:end].decode("utf-8"))
                        story_item_id = str(obj.get("itemId", ""))
                        story_uid     = str(obj.get("uid", ""))
                        story_title   = obj.get("content_name", "")
                        break
                    except Exception:
                        pass
            if story_item_id:
                msg["awe_type"] = 1025                                                  

        is_group = not msg.get("conv_id", "").startswith("0:1:")
        return {
            "conv_id":   msg.get("conv_id", ""),
            "sender_id": msg.get("sender_id", ""),
            "is_group":  is_group,
            "text":      msg.get("text", ""),
            "sec_uid":   msg.get("sec_uid", ""),
            "msg_id":    str(msg.get("msg_id", "")),
            "msg_type":  msg.get("msg_type", 0),
            "awe_type":  msg.get("awe_type", 0),
            "video_id":               msg.get("video_id", ""),
            "video_creator":          msg.get("video_creator", ""),
            "music_id":               msg.get("music_id", ""),
            "music_title":            msg.get("music_title", ""),
            "sticker_id":              sticker_id,
            "sticker_type":            sticker_type,
            "sticker_origin_video_id": sticker_origin_video_id,
            "sticker_creator_uid":     sticker_creator_uid,
            "voice_id":                voice_id,
            "voice_duration":          voice_duration,
            "live_room_id":            msg.get("live_room_id", ""),
            "live_owner_id":           msg.get("live_owner_id", ""),
            "live_owner_name":         msg.get("live_owner_name", ""),
            "comment_text":            msg.get("comment_text", ""),
            "comment_video_id":        msg.get("comment_video_id", ""),
            "comment_author_name":     msg.get("comment_author_name", ""),
            "profile_uid":             msg.get("profile_uid", ""),
            "profile_sec_uid":         msg.get("profile_sec_uid", ""),
            "profile_name":            msg.get("profile_name", ""),
            "story_item_id":           story_item_id,
            "story_uid":               story_uid,
            "story_title":             story_title,
            "greeting_card_text":      msg.get("greeting_card_text", ""),
            "group_command":           msg.get("group_command", 0),
            "group_added":             msg.get("group_added", []),
            "group_removed":           msg.get("group_removed", []),
            "quoted_msg_id":           msg.get("quoted_msg_id", 0),
            "quoted_uid":              msg.get("quoted_uid", ""),
            "quoted_sec_uid":          msg.get("quoted_sec_uid", ""),
            "quoted_awe_type":         msg.get("quoted_awe_type", 0),
            "quoted_text":             msg.get("quoted_text", ""),
            "quoted_video_id":         msg.get("quoted_video_id", ""),
            "quoted_video_uid":        msg.get("quoted_video_uid", ""),
        }

                                                                                

    async def _watch_plugins(self):
        while True:
            await asyncio.sleep(1)
            self._load_plugins()

    async def _dispatch(self, msg: dict):
        for name, plugin in list(self._plugins.items()):
            try:
                if hasattr(plugin, "on_message"):
                    await plugin.on_message(self, msg)
            except Exception as e:
                _log.error("lttk", f"error en plugin {name}: {e}")

    async def _dispatch_reaction(self, rxn: dict):
        for name, plugin in list(self._plugins.items()):
            try:
                if hasattr(plugin, "on_reaction"):
                    await plugin.on_reaction(self, rxn)
            except Exception as e:
                _log.error("lttk", f"error en plugin {name} (reaction): {e}")

    async def _dispatch_delete(self, deleted: dict):
        for name, plugin in list(self._plugins.items()):
            try:
                if hasattr(plugin, "on_delete"):
                    await plugin.on_delete(self, deleted)
            except Exception as e:
                _log.error("lttk", f"error en plugin {name} (delete): {e}")

    async def _heartbeat(self):
        while True:
            try:
                await self.websocket.send("hi")
                await asyncio.sleep(10)
            except Exception:
                break

    async def _receiver(self):
        while True:
            try:
                raw = await self.websocket.recv()
                if isinstance(raw, bytes):
                    decompressed = self._decompress_lz4_frame(raw)
                    rxn = self._parse_reaction(decompressed) if decompressed else None
                    if rxn and rxn["sender_id"] != self._own_user_id:
                        user = await self.get_user(rxn["sender_id"])
                        name = f"{user['nick_name']} (@{user['unique_id']})" if user else rxn["sender_id"]
                        ts = datetime.now().strftime("%H:%M:%S")
                        action = "reacciono" if rxn["op"] == 0 else "quito reaccion"
                        _log.reaction(ts, name, action, rxn['emoji'])
                        asyncio.create_task(self._dispatch_reaction(rxn))
                        continue
                    search_buf = decompressed if decompressed else raw
                    deleted = self._parse_delete(search_buf)
                    if deleted and deleted["sender_id"] != self._own_user_id:
                        user = await self.get_user(deleted["sender_id"])
                        name = f"{user['nick_name']} (@{user['unique_id']})" if user else deleted["sender_id"]
                        ts = datetime.now().strftime("%H:%M:%S")
                        is_group = not deleted["conv_id"].startswith("0:1:")
                        if is_group:
                            gname = await self.get_group_name(deleted["conv_id"])
                            group_tag = gname
                        else:
                            group_tag = ""
                        _log.msg(ts, name, group_tag, "[elimino un mensaje]")
                        asyncio.create_task(self._dispatch_delete(deleted))
                        continue
                    msg = self._parse(raw, decompressed)
                    if msg:
                        if msg["sender_id"] == self._own_user_id:
                            continue
                        user = await self.get_user(msg["sender_id"])
                        name = f"{user['nick_name']} (@{user['unique_id']})" if user else msg["sender_id"]
                        ts = datetime.now().strftime("%H:%M:%S")
                        is_group = not msg["conv_id"].startswith("0:1:")
                        if is_group:
                            gname = await self.get_group_name(msg["conv_id"])
                            group_tag = f"[{gname}] "
                        else:
                            group_tag = ""
                        if msg["awe_type"] == 50001:
                            cmd = msg["group_command"]
                            if cmd == 7 and msg["group_added"]:
                                added_names = []
                                for uid in msg["group_added"]:
                                    u = await self.get_user(uid)
                                    added_names.append(f"@{u['unique_id']}" if u else uid)
                                _log.msg(ts, name, group_tag.strip("[] "), f"agrego a {', '.join(added_names)}")
                            elif cmd == 6:
                                _log.msg(ts, name, group_tag.strip("[] "), f"[evento de grupo cmd={cmd}]")
                            else:
                                _log.msg(ts, name, group_tag.strip("[] "), f"[evento de grupo cmd={cmd}]")
                        elif msg["awe_type"] == 1814:
                            card_text = f": \"{msg['greeting_card_text']}\"" if msg["greeting_card_text"] else ""
                            _log.msg(ts, name, group_tag.strip("[] "), f"[tarjeta de regalo{card_text}]")
                        elif msg["awe_type"] == 1025:
                            creator = await self.get_user(msg["story_uid"]) if msg["story_uid"] else None
                            creator_tag = f"@{creator['unique_id']}" if creator else f"@{msg['story_uid']}"
                            _log.msg(ts, name, group_tag.strip("[] "), f"[historia de {creator_tag}: \"{msg['story_title']}\"] https://www.tiktok.com/{creator_tag}/video/{msg['story_item_id']}")
                        elif msg["awe_type"] == 25:
                            _log.msg(ts, name, group_tag.strip("[] "), f"[perfil de {msg['profile_name']}] https://www.tiktok.com/@{msg['profile_sec_uid']}")
                        elif msg["awe_type"] == 40:
                            _log.msg(ts, name, group_tag.strip("[] "), f"[comentario \"{msg['comment_text']}\"] https://www.tiktok.com/@{msg['comment_author_name']}/video/{msg['comment_video_id']}")
                        elif msg["awe_type"] == 1021:
                            _log.msg(ts, name, group_tag.strip("[] "), f"[live de @{msg['live_owner_name']}] https://www.tiktok.com/@{msg['live_owner_name']}/live")
                        elif msg["awe_type"] == 1813:
                            _log.msg(ts, name, group_tag.strip("[] "), f"[nota de voz {msg['voice_duration']}]")
                        elif msg["awe_type"] == 1805:
                            if msg["sticker_origin_video_id"]:
                                creator = await self.get_user(msg["sticker_creator_uid"]) if msg["sticker_creator_uid"] else None
                                creator_tag = f"@{creator['unique_id']}" if creator else f"@{msg['sticker_creator_uid']}"
                                _log.msg(ts, name, group_tag.strip("[] "), f"[video sticker by {creator_tag}] https://www.tiktok.com/{creator_tag}/video/{msg['sticker_origin_video_id']}")
                            else:
                                _log.msg(ts, name, group_tag.strip("[] "), f"[sticker {msg['sticker_id']}]")
                        elif msg["awe_type"] in (800, 810):
                            kind = "photo" if msg["awe_type"] == 810 else "video"
                            creator = await self.get_user(msg["video_creator"]) if msg["video_creator"] else None
                            creator_tag = f"@{creator['unique_id']}" if creator else msg["video_creator"]
                            path = "photo" if msg["awe_type"] == 810 else "video"
                            _log.msg(ts, name, group_tag.strip("[] "), f"[{kind} by {creator_tag}] https://www.tiktok.com/{creator_tag}/{path}/{msg['video_id']}")
                        elif msg["awe_type"] == 22:
                            slug = re.sub(r'[^a-z0-9]+', '-', msg['music_title'].lower()).strip('-') or "audio"
                            _log.msg(ts, name, group_tag.strip("[] "), f"[audio] {msg['music_title']} https://www.tiktok.com/music/{slug}-{msg['music_id']}")
                        else:
                            _log.msg(ts, name, group_tag.strip("[] "), msg['text'])
                        asyncio.create_task(self._dispatch(msg))
            except websockets.exceptions.ConnectionClosed:
                _log.warn("lttk", "conexion cerrada")
                break
            except Exception as e:
                _log.error("lttk", f"error recv: {e}")
                break

    def _logout_and_delete(self):
        import urllib.request
        cookie = "; ".join(f"{k}={v}" for k, v in config.COOKIES.items())
        try:
            req = urllib.request.Request(
                "https://www.tiktok.com/logout?redirect_url=https%3A%2F%2Fwww.tiktok.com%2F",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Referer": "https://www.tiktok.com/",
                    "Cookie": cookie,
                },
            )
            urllib.request.urlopen(req, timeout=10)
            _log.ok("lttk", "sesion cerrada en TikTok")
        except Exception as e:
            _log.warn("lttk", f"error al cerrar sesion en TikTok ({e})")

        if self._active_session:
            from .qrlogin import _SESSION_DIR
            import os
            path = os.path.join(_SESSION_DIR, f"{self._active_session}.json")
            try:
                os.remove(path)
                _log.ok("lttk", f"credencial eliminada: {self._active_session}.json")
            except FileNotFoundError:
                pass
            self._active_session = None
        config.COOKIES = {}

    async def _console(self):
        loop = asyncio.get_event_loop()
        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            cmd = line.strip().lower()
            if cmd == "stop":
                raise _BotStop()
            elif cmd == "close":
                await asyncio.get_event_loop().run_in_executor(None, self._logout_and_delete)
                raise _BotStop()
            elif cmd == "retry":
                raise _BotRestart()
            elif cmd:
                _log.info("lttk", f"comandos: retry | stop | close")

    def _load_session(self):
        from .qrlogin import list_sessions, load_session
        sessions = list_sessions()
        if sessions:
            username = sessions[0]
            cookies = load_session(username)
            if cookies.get("sessionid"):
                _log.info("lttk", f"cargando sesion: {username}")
                config.COOKIES = cookies
                self._active_session = username
                cookie = "; ".join(f"{k}={v}" for k, v in cookies.items())
                for i, (k, _) in enumerate(self._headers):
                    if k == "Cookie":
                        self._headers[i] = ("Cookie", cookie)
                        break
                return True
        return False

    async def run(self):
        if not config.COOKIES.get("sessionid"):
            if not self._load_session():
                _log.warn("lttk", "no hay sesion, iniciando login por QR...")
                from .qrlogin import run as qr_run, _stop_event as qr_stop
                try:
                    await asyncio.get_event_loop().run_in_executor(None, qr_run)
                except (KeyboardInterrupt, asyncio.CancelledError):
                    qr_stop.set()
                    return
                self._load_session()

        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        try:
            self._own_user_id = await asyncio.get_event_loop().run_in_executor(None, get_own_user_id)
            config.OWN_USER_ID = self._own_user_id
            profiles = await asyncio.get_event_loop().run_in_executor(None, get_user_profiles, [self._own_user_id])
            if profiles:
                p = profiles[0]
                _log.ok("lttk", f"conectado como: {p['nick_name']} (@{p['unique_id']}) [{self._own_user_id}]")
            else:
                _log.info("lttk", f"uid: {self._own_user_id}")
        except Exception as e:
            if "Login expired" in str(e):
                _log.warn("lttk", "sesion caducada o invalida, borrando cookies y reiniciando login...")
                from .qrlogin import run as qr_run, _stop_event as qr_stop
                config.COOKIES = {}
                try:
                    await asyncio.get_event_loop().run_in_executor(None, qr_run)
                except (KeyboardInterrupt, asyncio.CancelledError):
                    qr_stop.set()
                    return
                self._load_session()
            else:
                _log.warn("lttk", f"no se pudo verificar sesion ({e}), continuando...")

        while True:
            _log.info("lttk", "conectando...")
            try:
                async with websockets.connect(
                    self._ws_url,
                    extra_headers=self._headers,
                    subprotocols=self._subprotocols,
                    ssl=ssl_ctx,
                    ping_interval=20,
                    ping_timeout=10,
                ) as ws:
                    self.websocket = ws
                    _log.ok("lttk", "conectado")
                    await ws.send("hi")
                    try:
                        await asyncio.wait_for(ws.recv(), timeout=10)
                    except asyncio.TimeoutError:
                        pass
                    self._load_plugins()
                    startup_tasks = []
                    for name, plugin in list(self._plugins.items()):
                        if hasattr(plugin, "on_start"):
                            startup_tasks.append(asyncio.create_task(plugin.on_start(self)))
                    tasks = [
                        asyncio.create_task(self._heartbeat()),
                        asyncio.create_task(self._receiver()),
                        asyncio.create_task(self._watch_plugins()),
                        asyncio.create_task(self._console()),
                        *startup_tasks,
                    ]
                    try:
                        done, pending = await asyncio.wait(
                            tasks, return_when=asyncio.FIRST_COMPLETED
                        )
                        for t in pending:
                            t.cancel()
                        for t in done:
                            t.result()
                    except _BotRestart:
                        _log.info("lttk", "reiniciando...")
                        await self.run()
                        return
                    except _BotStop:
                        _log.info("lttk", "detenido.")
                        return
            except _BotStop:
                return
            except Exception as e:
                _log.warn("lttk", f"conexion perdida ({e}), reconectando en 5s...")
                await asyncio.sleep(5)
