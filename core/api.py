import hashlib
import json
import os
import re
import urllib.request
import urllib.parse

from .. import config

_ROOT = os.path.dirname(os.path.dirname(__file__))
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"

_UID_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".uid_cache.json")


def _session_hash() -> str:
    session = config.COOKIES.get("sessionid", "")
    return hashlib.sha256(session.encode()).hexdigest()[:16]


def _cookie_header() -> str:
    return "; ".join(f"{k}={v}" for k, v in config.COOKIES.items())


def get_own_user_id() -> str:
    current_hash = _session_hash()

    try:
        with open(_UID_CACHE_FILE) as f:
            cache = json.load(f)
        if cache.get("session_hash") == current_hash:
            return cache["uid"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        pass

    req = urllib.request.Request(
        "https://www.tiktok.com/messages?lang=es-419",
        headers={
            "accept":           "text/html",
            "accept-language":  "es-US,es;q=0.9",
            "user-agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
            "cookie":           _cookie_header(),
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    m = re.search(r'"odinId"\s*:\s*"(\d+)"', html)
    if not m:
        raise RuntimeError("No se pudo obtener OWN_USER_ID desde la pagina de mensajes")

    uid = m.group(1)
    with open(_UID_CACHE_FILE, "w") as f:
        json.dump({"session_hash": current_hash, "uid": uid}, f)

    return uid


def get_user_profiles(user_ids: list[str]) -> list[dict]:
    ids_param = urllib.parse.quote(json.dumps(user_ids))
    url = f"https://www.tiktok.com/tiktok/v1/im/user/profile/?aid=1988&user_ids={ids_param}"

    req = urllib.request.Request(url, headers={
        "accept":           "*/*",
        "accept-language":  "es-US,es;q=0.9",
        "referer":          "https://www.tiktok.com/messages?lang=es-419",
        "user-agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        "cookie":           _cookie_header(),
    })

    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())

    if data.get("status_code") != 0:
        raise RuntimeError(f"TikTok API error: {data.get('status_msg')}")

    return [u["im_user_profile"] for u in data.get("users", [])]


def get_fyp_video() -> str:
    import sys
    sys.path.insert(0, _ROOT)
    from fyp2 import get_fyp_video as _get
    return _get()


def get_item_detail(item_id: str) -> dict:
    import sys
    sys.path.insert(0, os.path.join(os.path.expanduser("~"), "Documents", "ttsigner"))
    from Web.bogus import Signer
    from Web.gnarly import get_X_Gnarly

    odin_id = config.COOKIES.get("odin_tt", "")[:19] or config.OWN_USER_ID
    ms_token = config.COOKIES.get("msToken", "")

    query = (
        "WebIdLastTime=1777359527&aid=1988"
        "&app_language=es-419&app_name=tiktok_web&browser_language=es-US"
        "&browser_name=Mozilla&browser_online=true&browser_platform=Win32"
        "&browser_version=5.0%20%28Windows%20NT%2010.0%3B%20Win64%3B%20x64%29"
        "%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Chrome%2F147.0.0.0"
        "%20Safari%2F537.36&channel=tiktok_web&cookie_enabled=true&coverFormat=2"
        "&data_collection_enabled=true"
        f"&device_id={config.DEVICE_ID}"
        "&device_platform=web_pc&focus_state=true&from_page=user&history_len=5"
        "&is_fullscreen=false&is_page_visible=true"
        f"&itemId={item_id}"
        "&language=es-419"
        f"&odinId={config.OWN_USER_ID}"
        "&os=windows&priority_region=CO&referer=&region=CO"
        "&root_referer=https%3A%2F%2Fwww.tiktok.com%2F"
        "&screen_height=1080&screen_width=1920&tz_name=America%2FBogota"
        "&user_is_login=true&video_encoding=dash&webcast_language=es-419"
        f"&msToken={urllib.parse.quote(ms_token)}"
    )

    signed_query = Signer.sign(query, _UA)
    x_gnarly = get_X_Gnarly(query_string=query, request_body="", user_agent=_UA)
    url = f"https://www.tiktok.com/api/item/detail/?{signed_query}&X-Gnarly={x_gnarly}"

    req = urllib.request.Request(url, headers={
        "User-Agent":      _UA,
        "Accept":          "application/json, text/plain, */*",
        "Accept-Language": "es-419,es;q=0.9",
        "Referer":         "https://www.tiktok.com/",
        "Cookie":          _cookie_header(),
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def get_group_names() -> dict[str, str]:
                                    
                                                                        
                                                           
                                                       
    def _pb_vi(field: int, v: int) -> bytes:
        tag = (field << 3) | 0
        out = bytearray()
        tag_b = tag
        while True:
            b = tag_b & 0x7f
            tag_b >>= 7
            out.append(b | (0x80 if tag_b else 0))
            if not tag_b: break
        while True:
            b = v & 0x7f; v >>= 7
            out.append(b | (0x80 if v else 0))
            if not v: break
        return bytes(out)

    def _pb_str(field: int, s: str) -> bytes:
        enc = s.encode("utf-8")
        tag = (field << 3) | 2
        out = bytearray()
        t = tag
        while True:
            b = t & 0x7f; t >>= 7
            out.append(b | (0x80 if t else 0))
            if not t: break
        n = len(enc)
        while True:
            b = n & 0x7f; n >>= 7
            out.append(b | (0x80 if n else 0))
            if not n: break
        return bytes(out) + enc

    def _pb_kv(key: str, val: str) -> bytes:
        inner = _pb_str(1, key) + _pb_str(2, val)
        return _pb_str(15, inner.decode("latin-1")) if False else (
            (15 << 3 | 2).to_bytes(1, "big") + _encode_varint(len(inner)).to_bytes(1, "big") + inner
        )

    def _encode_varint(n: int) -> bytes:
        out = bytearray()
        while True:
            b = n & 0x7f; n >>= 7
            out.append(b | (0x80 if n else 0))
            if not n: break
        return bytes(out)

    def _field(field: int, wire: int, payload: bytes) -> bytes:
        tag = (field << 3) | wire
        return _encode_varint(tag) + (payload if wire == 0 else _encode_varint(len(payload)) + payload)

    def _vi(field: int, v: int) -> bytes:
        return _field(field, 0, _encode_varint(v))

    def _st(field: int, s: str) -> bytes:
        b = s.encode("utf-8")
        return _field(field, 2, b)

    def _kv(key: str, val: str) -> bytes:
        inner = _st(1, key) + _st(2, val)
        return _field(15, 2, inner)

    device_id = config.DEVICE_ID or "7643756217525126672"
    own_id    = config.OWN_USER_ID or ""

    body = (
        _vi(1, 203) +
        _vi(2, 10002) +
        _st(3, "1.7.0") +
        _st(4, "") +
        _vi(5, 3) +
        _vi(6, 1) +
        _st(7, "e465244:feat/call-trace-plugin") +
        _st(9, own_id) +
        _st(11, "web") +
        _kv("aid", "1988") +
        _kv("app_name", "tiktok_web") +
        _kv("channel", "web") +
        _kv("device_platform", "web_pc") +
        _kv("device_id", device_id) +
        _kv("region", "CO") +
        _kv("priority_region", "CO") +
        _kv("os", "windows") +
        _kv("cookie_enabled", "true") +
        _kv("screen_width", "1920") +
        _kv("screen_height", "1080") +
        _kv("browser_language", "es-US") +
        _kv("browser_platform", "Win32") +
        _kv("browser_name", "Mozilla") +
        _kv("browser_version", "5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36") +
        _kv("browser_online", "true") +
        _kv("app_language", "es-419") +
        _kv("webcast_language", "es-419") +
        _kv("tz_name", "America/Bogota") +
        _kv("is_page_visible", "true") +
        _kv("focus_state", "true") +
        _kv("is_fullscreen", "false") +
        _kv("history_len", "5") +
        _kv("user_is_login", "true") +
        _kv("data_collection_enabled", "true") +
        _kv("from_appID", "1988") +
        _kv("locale", "es-419") +
        _vi(18, 1)
    )

    req = urllib.request.Request(
        "https://im-api-sg.tiktok.com/v2/message/get_by_user_init",
        data=body,
        method="POST",
        headers={
            "Host":             "im-api-sg.tiktok.com",
            "Content-Type":     "application/x-protobuf",
            "Accept":           "application/x-protobuf",
            "Accept-Language":  "es-US,es;q=0.9",
            "Origin":           "https://www.tiktok.com",
            "Referer":          "https://www.tiktok.com/",
            "User-Agent":       _UA,
            "Cookie":           _cookie_header(),
        },
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        resp_body = resp.read()

                                                                       
                                                                                 
    def _read_varint(buf, pos):
        r = 0; sh = 0
        while pos < len(buf):
            b = buf[pos]; pos += 1
            r |= (b & 0x7f) << sh; sh += 7
            if not (b & 0x80): break
        return r, pos

    def _parse_entries(buf):
        results: dict[str, str] = {}
        pos = 0
        while pos < len(buf):
            try:
                tv, pos = _read_varint(buf, pos)
            except Exception:
                break
            fn = tv >> 3; wt = tv & 7
            if wt == 2:
                ln, pos = _read_varint(buf, pos)
                val = buf[pos:pos + ln]; pos += ln
                if fn == 6:
                                      
                    p2 = 0
                    while p2 < len(val):
                        try: tv2, p2 = _read_varint(val, p2)
                        except: break
                        fn2 = tv2 >> 3; wt2 = tv2 & 7
                        if wt2 == 2:
                            ln2, p2 = _read_varint(val, p2)
                            v2 = val[p2:p2 + ln2]; p2 += ln2
                            if fn2 == 203:
                                results.update(_parse_conv_entry(v2))
                        elif wt2 == 0:
                            _, p2 = _read_varint(val, p2)
                        else:
                            break
            elif wt == 0:
                _, pos = _read_varint(buf, pos)
            elif wt == 1:
                pos += 8
            elif wt == 5:
                pos += 4
            else:
                break
        return results

    def _parse_conv_entry(buf) -> dict:
        import json as _json
        conv_id = None; group_name = None
        pos = 0
        while pos < len(buf):
            try: tv, pos = _read_varint(buf, pos)
            except: break
            fn = tv >> 3; wt = tv & 7
            if wt == 2:
                ln, pos = _read_varint(buf, pos)
                val = buf[pos:pos + ln]; pos += ln
                if fn == 1:
                    try: conv_id = val.decode("utf-8")
                    except: pass
                elif fn == 8 and b"group_name" in val:
                    try:
                        obj = _json.loads(val.decode("utf-8"))
                        group_name = obj.get("group_name", "")
                    except: pass
            elif wt == 0:
                _, pos = _read_varint(buf, pos)
            elif wt == 1:
                pos += 8
            elif wt == 5:
                pos += 4
            else:
                break
        if conv_id and group_name:
            return {conv_id: group_name}
        return {}

    return _parse_entries(resp_body)


def get_music_detail(music_id: str) -> dict:
    import sys
    sys.path.insert(0, os.path.join(os.path.expanduser("~"), "Documents", "ttsigner"))
    from Web.bogus import Signer
    from Web.gnarly import get_X_Gnarly

    ms_token = config.COOKIES.get("msToken", "")

    query = (
        "WebIdLastTime=1777359527&aid=1988"
        "&app_language=es-419&app_name=tiktok_web&browser_language=es-US"
        "&browser_name=Mozilla&browser_online=true&browser_platform=Win32"
        "&browser_version=5.0%20%28Windows%20NT%2010.0%3B%20Win64%3B%20x64%29"
        "%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Chrome%2F147.0.0.0"
        "%20Safari%2F537.36&channel=tiktok_web&cookie_enabled=true"
        "&data_collection_enabled=true"
        f"&device_id={config.DEVICE_ID}"
        "&device_platform=web_pc&focus_state=true&from_page=music"
        "&is_fullscreen=false&is_page_visible=true&language=es-419"
        f"&musicId={music_id}"
        f"&odinId={config.OWN_USER_ID}"
        "&os=windows&priority_region=CO&referer=&region=CO"
        "&root_referer=https%3A%2F%2Fwww.tiktok.com%2F"
        "&screen_height=1080&screen_width=1920&tz_name=America%2FBogota"
        "&user_is_login=true&webcast_language=es-419"
        f"&msToken={urllib.parse.quote(ms_token)}"
    )

    signed_query = Signer.sign(query, _UA)
    x_gnarly = get_X_Gnarly(query_string=query, request_body="", user_agent=_UA)
    url = f"https://www.tiktok.com/api/music/detail/?{signed_query}&X-Gnarly={x_gnarly}"

    req = urllib.request.Request(url, headers={
        "User-Agent":      _UA,
        "Accept":          "application/json, text/plain, */*",
        "Accept-Language": "es-419,es;q=0.9",
        "Referer":         "https://www.tiktok.com/",
        "Cookie":          _cookie_header(),
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


_VERIFY_FP    = "verify_mplnlgno_s07vIKFn_2ii8_43lR_800G_hibLVGVaQnut"
_SHORTEN_LANG = "es-419"


def shorten_url(target: str) -> str:
    params = (
        f"aid=1988&app_language={_SHORTEN_LANG}&app_name=tiktok_web"
        f"&browser_language={_SHORTEN_LANG}&browser_name=Mozilla&browser_online=true"
        f"&browser_platform=Win32"
        f"&browser_version={urllib.parse.quote(_UA)}"
        f"&channel=tiktok_web&cookie_enabled=true&data_collection_enabled=false"
        f"&device_id={config.DEVICE_ID or '7596338482468373197'}&device_platform=web_pc"
        f"&focus_state=true&from_page=&history_len=3"
        f"&is_fullscreen=false&is_page_visible=true&os=windows"
        f"&priority_region=&referer=&region=CO"
        f"&safe_token=true&screen_height=1050&screen_width=1680"
        f"&tz_name=America%2FBogota&user_is_login=false"
        f"&verifyFp={_VERIFY_FP}&webcast_language={_SHORTEN_LANG}"
    )
    url = f"https://www.tiktok.com/shorten/?{params}"
    body = urllib.parse.urlencode({
        "belong": "tiktok-webapp-qrcode",
        "persist": "0",
        "expired_time": "3600",
        "targets": target,
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "User-Agent":   _UA,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer":      "https://www.tiktok.com/",
        "Accept":       "application/json, text/plain, */*",
        "Cookie":       _cookie_header(),
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        entries = data.get('data', [])
        if entries and data.get('code') == 0:
            return entries[0]['short_url']
    except Exception:
        pass
    return target
