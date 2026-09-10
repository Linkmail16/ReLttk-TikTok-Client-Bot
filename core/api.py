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


def _cookie_str(cookies: dict) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def get_own_user_id(cookies: dict | None = None) -> str:
    cookies = cookies or config.COOKIES
    session = cookies.get("sessionid", "")
    current_hash = hashlib.sha256(session.encode()).hexdigest()[:16]

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
            "cookie":           _cookie_str(cookies),
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


def get_user_profiles(user_ids: list[str], cookies: dict | None = None) -> list[dict]:
    cookies = cookies or config.COOKIES
    ids_param = urllib.parse.quote(json.dumps(user_ids))
    url = f"https://www.tiktok.com/tiktok/v1/im/user/profile/?aid=1988&user_ids={ids_param}"

    req = urllib.request.Request(url, headers={
        "accept":           "*/*",
        "accept-language":  "es-US,es;q=0.9",
        "referer":          "https://www.tiktok.com/messages?lang=es-419",
        "user-agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        "cookie":           _cookie_str(cookies),
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
        "Cookie":          _cookie_str(config.COOKIES),
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _fetch_inbox(cookies: dict | None = None, device_id: str | None = None, ms_token: str | None = None, verify_fp: str | None = None) -> bytes:
    cookies = cookies or config.COOKIES
    _BV = "5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0"
    _FULL_UA = f"Mozilla/5.0 {_BV}"
    device_id = device_id or config.DEVICE_ID or "0"
    ms_token  = ms_token or cookies.get("msToken", "") or config.MSG_SDK_MS_TOKEN or ""
    verify_fp = verify_fp or cookies.get("s_v_web_id", "verify_ms75rg2f_ftn5TmOL_0JAu_4qoc_Aq2f_n2UmR5ESX7SX")

    def _kv(k, v):
        return _pb_bytes(15, _pb_str(1, k) + _pb_str(2, v))

    body = (
        _pb_varint(1, 203) +
        _pb_varint(2, 10002) +
        _pb_str(3, "1.7.0") +
        _pb_str(4, "") +
        _pb_varint(5, 3) +
        _pb_varint(6, 1) +
        _pb_str(7, "3035f17:feat/call-trace-plugin") +
        _pb_bytes(8, _pb_bytes(203, _pb_varint(1, 0))) +
        _pb_str(9, device_id) +
        _pb_str(11, "web") +
        _kv("aid", "1988") +
        _kv("app_name", "tiktok_web") +
        _kv("channel", "web") +
        _kv("device_platform", "web_pc") +
        _kv("device_id", device_id) +
        _kv("region", "CO") +
        _kv("priority_region", "CO") +
        _kv("os", "windows") +
        _kv("referer", "https://www.tiktok.com/messages") +
        _kv("root_referer", "") +
        _kv("cookie_enabled", "true") +
        _kv("screen_width", "1920") +
        _kv("screen_height", "1080") +
        _kv("browser_language", "es-419") +
        _kv("browser_platform", "Win32") +
        _kv("browser_name", "Mozilla") +
        _kv("browser_version", _BV) +
        _kv("browser_online", "true") +
        _kv("verifyFp", verify_fp) +
        _kv("app_language", "es-419") +
        _kv("webcast_language", "es-419") +
        _kv("tz_name", "America/Bogota") +
        _kv("is_page_visible", "true") +
        _kv("focus_state", "true") +
        _kv("is_fullscreen", "false") +
        _kv("history_len", "2") +
        _kv("user_is_login", "true") +
        _kv("data_collection_enabled", "true") +
        _kv("from_appID", "1988") +
        _kv("locale", "es-419") +
        _kv("user_agent", _FULL_UA) +
        _kv("Web-Sdk-Ms-Token", ms_token) +
        _pb_varint(18, 1)
    )
    req = urllib.request.Request(
        "https://im-api-sg.tiktok.com/v2/message/get_by_user_init",
        data=body, method="POST",
        headers={
            "Content-Type": "application/x-protobuf",
            "Accept":       "application/x-protobuf",
            "Origin":       "https://www.tiktok.com",
            "Referer":      "https://www.tiktok.com/",
            "User-Agent":   _FULL_UA,
            "Cookie":       _cookie_str(cookies),
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


def _parse_inbox(resp_body: bytes) -> list[dict]:
    def _read_varint(buf, pos):
        r = 0; sh = 0
        while pos < len(buf):
            b = buf[pos]; pos += 1
            r |= (b & 0x7f) << sh; sh += 7
            if not (b & 0x80): break
        return r, pos

    def _pf(buf):
        fields = {}
        pos = 0
        while pos < len(buf):
            if buf[pos] == 0: pos += 1; continue
            try: tag, pos = _read_varint(buf, pos)
            except Exception: break
            f = tag >> 3; wt = tag & 7
            if wt == 2:
                try: ln, pos = _read_varint(buf, pos)
                except Exception: break
                fields.setdefault(f, []).append(buf[pos:pos+ln]); pos += ln
            elif wt == 0:
                try: v, pos = _read_varint(buf, pos)
                except Exception: break
                fields.setdefault(f, []).append(v)
            elif wt == 1: pos += 8
            elif wt == 5: pos += 4
            else: break
        return fields

    def _str(fields, key):
        v = fields.get(key, [None])[0]
        if isinstance(v, bytes):
            try: return v.decode("utf-8")
            except: return ""
        return str(v) if v is not None else ""

    convs = []
    top = _pf(resp_body)
    for f6_blob in top.get(6, []):
        f6 = _pf(f6_blob)
        for f203_blob in f6.get(203, []):
            f203 = _pf(f203_blob)
            for conv_blob in f203.get(2, []):
                conv = _pf(conv_blob)
                conv_id = _str(conv, 1)
                if not conv_id:
                    continue
                conv_type = conv.get(3, [1])[0] if conv.get(3) else 1
                is_group = (conv_type == 2)
                member_count = conv.get(7, [0])[0]
                unread = conv.get(11, [0])[0]
                name = conv_id
                avatar = ""
                for f50_blob in conv.get(50, []):
                    f50 = _pf(f50_blob)
                    n = _str(f50, 5)
                    if n: name = n
                    a = _str(f50, 7)
                    if a: avatar = a
                convs.append({
                    "conv_id":      conv_id,
                    "name":         name,
                    "is_group":     is_group,
                    "unread":       unread,
                    "member_count": member_count,
                    "avatar":       avatar,
                })
    return convs


def get_conversations(cookies: dict | None = None, device_id: str | None = None) -> list[dict]:
    return _parse_inbox(_fetch_inbox(cookies=cookies, device_id=device_id))


def get_group_names(cookies: dict | None = None, device_id: str | None = None) -> dict[str, str]:
    convs = _parse_inbox(_fetch_inbox(cookies=cookies, device_id=device_id))
    return {c["conv_id"]: c["name"] for c in convs if c["is_group"] and c["name"] != c["conv_id"]}


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
        "Cookie":          _cookie_str(config.COOKIES),
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _varint(v: int) -> bytes:
    out = []
    while True:
        b = v & 0x7F; v >>= 7
        out.append(b | (0x80 if v else 0))
        if not v: break
    return bytes(out)

def _pb_varint(field: int, v: int) -> bytes:
    return _varint((field << 3) | 0) + _varint(v)

def _pb_bytes(field: int, v: bytes) -> bytes:
    return _varint((field << 3) | 2) + _varint(len(v)) + v

def _pb_str(field: int, s: str) -> bytes:
    return _pb_bytes(field, s.encode())

def get_conversation_history(conv_id: str, count: int = 20, cursor: int = 0, conv_short_id: int = 0, conv_type: int = 10011, cookies: dict | None = None, device_id: str | None = None) -> bytes:
    cookies = cookies or config.COOKIES
    _BV = "5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0"
    _FULL_UA = f"Mozilla/5.0 {_BV}"
    device_id  = device_id or config.DEVICE_ID or "0"
    ms_token   = cookies.get("msToken", "") or config.MSG_SDK_MS_TOKEN or ""
    verify_fp  = cookies.get("s_v_web_id", "verify_ms75rg2f_ftn5TmOL_0JAu_4qoc_Aq2f_n2UmR5ESX7SX")

    def _kv(k, v):
        inner = _pb_str(1, k) + _pb_str(2, v)
        return _pb_bytes(15, inner)

    inner = (
        _pb_str(1, conv_id) +
        _pb_varint(2, 1) +
        _pb_varint(3, conv_short_id) +
        _pb_varint(4, 1) +
        _pb_varint(5, cursor) +
        _pb_varint(6, count)
    )
    payload = (
        _pb_varint(1, 301) +
        _pb_varint(2, conv_type) +
        _pb_str(3, "1.7.0") +
        _pb_str(4, "") +
        _pb_varint(5, 3) +
        _pb_varint(6, 0) +
        _pb_str(7, "3035f17:feat/call-trace-plugin") +
        _pb_bytes(8, _pb_bytes(301, inner)) +
        _pb_str(9, device_id) +
        _pb_str(11, "web") +
        _kv("aid", "1988") +
        _kv("app_name", "tiktok_web") +
        _kv("channel", "web") +
        _kv("device_platform", "web_pc") +
        _kv("device_id", device_id) +
        _kv("region", "CO") +
        _kv("priority_region", "CO") +
        _kv("os", "windows") +
        _kv("referer", "https://www.tiktok.com/messages") +
        _kv("root_referer", "") +
        _kv("cookie_enabled", "true") +
        _kv("screen_width", "1920") +
        _kv("screen_height", "1080") +
        _kv("browser_language", "es-419") +
        _kv("browser_platform", "Win32") +
        _kv("browser_name", "Mozilla") +
        _kv("browser_version", _BV) +
        _kv("browser_online", "true") +
        _kv("verifyFp", verify_fp) +
        _kv("app_language", "es-419") +
        _kv("webcast_language", "es-419") +
        _kv("tz_name", "America/Bogota") +
        _kv("is_page_visible", "true") +
        _kv("focus_state", "true") +
        _kv("is_fullscreen", "false") +
        _kv("history_len", "2") +
        _kv("user_is_login", "true") +
        _kv("data_collection_enabled", "true") +
        _kv("from_appID", "1988") +
        _kv("locale", "es-419") +
        _kv("user_agent", _FULL_UA) +
        _kv("Web-Sdk-Ms-Token", ms_token) +
        _pb_varint(18, 1)
    )
    req = urllib.request.Request(
        "https://im-api-sg.tiktok.com/v1/message/get_by_conversation",
        data=payload, method="POST",
        headers={
            "User-Agent":   _FULL_UA,
            "Content-Type": "application/x-protobuf",
            "Accept":       "application/x-protobuf",
            "Origin":       "https://www.tiktok.com",
            "Referer":      "https://www.tiktok.com/",
            "Cookie":       _cookie_str(cookies),
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()

def get_pending_strangers(cookies: dict | None = None, own_user_id: str | None = None, device_id: str | None = None) -> list[dict]:
    cookies = cookies or config.COOKIES
    own_id  = own_user_id or config.OWN_USER_ID or ""

    def _kv2(key, val):
        inner = _pb_str(1, key) + _pb_str(2, val)
        return _pb_bytes(15, inner)

    device_id = device_id or config.DEVICE_ID or "7643756217525126672"
    ms_token  = cookies.get("msToken", "")
    verify_fp = cookies.get("s_v_web_id", "") or config.VERIFY_FP or ""

    body = (
        _pb_varint(1, 203) +
        _pb_varint(2, 10003) +
        _pb_str(3, "1.7.0") +
        _pb_str(4, "") +
        _pb_varint(5, 3) +
        _pb_varint(6, 3) +
        _pb_str(7, "3035f17:feat/call-trace-plugin") +
        _pb_bytes(8, _pb_bytes(203, _pb_varint(1, 0))) +
        _pb_str(9, device_id) +
        _pb_str(11, "web") +
        _kv2("aid", "1988") +
        _kv2("app_name", "tiktok_web") +
        _kv2("channel", "web") +
        _kv2("device_platform", "web_pc") +
        _kv2("device_id", device_id) +
        _kv2("region", "CO") +
        _kv2("priority_region", "CO") +
        _kv2("os", "windows") +
        _kv2("referer", "https://www.tiktok.com/messages") +
        _kv2("root_referer", "") +
        _kv2("cookie_enabled", "true") +
        _kv2("screen_width", "1920") +
        _kv2("screen_height", "1080") +
        _kv2("browser_language", "es-419") +
        _kv2("browser_platform", "Win32") +
        _kv2("browser_name", "Mozilla") +
        _kv2("browser_version", "5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0") +
        _kv2("browser_online", "true") +
        _kv2("verifyFp", verify_fp) +
        _kv2("app_language", "es-419") +
        _kv2("webcast_language", "es-419") +
        _kv2("tz_name", "America/Bogota") +
        _kv2("is_page_visible", "true") +
        _kv2("focus_state", "true") +
        _kv2("is_fullscreen", "false") +
        _kv2("history_len", "2") +
        _kv2("user_is_login", "true") +
        _kv2("data_collection_enabled", "true") +
        _kv2("from_appID", "1988") +
        _kv2("locale", "es-419") +
        _kv2("user_agent", f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0") +
        _kv2("Web-Sdk-Ms-Token", ms_token) +
        _pb_varint(18, 1)
    )

    req = urllib.request.Request(
        "https://im-api-sg.tiktok.com/v2/message/get_by_user_init",
        data=body, method="POST",
        headers={
            "Content-Type": "application/x-protobuf",
            "Accept":       "application/x-protobuf",
            "Origin":       "https://www.tiktok.com",
            "Referer":      "https://www.tiktok.com/",
            "User-Agent":   _UA,
            "Cookie":       _cookie_str(cookies),
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp_body = resp.read()

    def _rv(buf, pos):
        r = 0; sh = 0
        while pos < len(buf):
            b = buf[pos]; pos += 1
            r |= (b & 0x7f) << sh; sh += 7
            if not (b & 0x80): break
        return r, pos

    def _iter_fields(buf):
        pos = 0
        while pos < len(buf):
            try: tv, pos = _rv(buf, pos)
            except: break
            fn = tv >> 3; wt = tv & 7
            if wt == 2:
                ln, pos = _rv(buf, pos)
                yield fn, buf[pos:pos+ln]; pos += ln
            elif wt == 0: _, pos = _rv(buf, pos)
            elif wt == 1: pos += 8
            elif wt == 5: pos += 4
            else: break

    def _uid_from_conv(conv_id):
        parts = conv_id.split(":")
        if len(parts) != 4: return ""
        a, b = parts[2], parts[3]
        return b if a == own_id else a if b == own_id else ""

    seen = set()
    results = []
    for fn, f6 in _iter_fields(resp_body):
        if fn != 6: continue
        for fn2, f203 in _iter_fields(f6):
            if fn2 != 203: continue
            for fn3, item in _iter_fields(f203):
                if fn3 not in (1, 2): continue
                for fn4, val in _iter_fields(item):
                    if fn4 != 1: continue
                    try: conv_id = val.decode("utf-8")
                    except: break
                    if conv_id in seen or not conv_id.startswith("0:1:"): break
                    uid = _uid_from_conv(conv_id)
                    if uid and uid != own_id:
                        seen.add(conv_id)
                        results.append({"conv_id": conv_id, "uid": uid})
                    break
    return results


def accept_stranger(conv_id: str, to_user_id: str, cookies: dict | None = None, device_id: str | None = None) -> bool:
    cookies   = cookies or config.COOKIES
    device_id = device_id or config.DEVICE_ID or ""
    csrf      = cookies.get("tt_csrf_token", "") or config.TT_CSRF_TOKEN or ""
    verify_fp = cookies.get("s_v_web_id", "") or config.VERIFY_FP or ""
    params = urllib.parse.urlencode({
        "aid": "1988",
        "app_language": "es-419",
        "app_name": "tiktok_web",
        "browser_language": "es-419",
        "browser_name": "Mozilla",
        "browser_online": "true",
        "browser_platform": "Win32",
        "browser_version": "5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0",
        "channel": "tiktok_web",
        "cookie_enabled": "true",
        "data_collection_enabled": "true",
        "device_id": device_id,
        "device_platform": "web_pc",
        "focus_state": "true",
        "history_len": "2",
        "is_fullscreen": "false",
        "is_page_visible": "true",
        "os": "windows",
        "priority_region": "CO",
        "referer": "https://www.tiktok.com/messages",
        "region": "CO",
        "screen_height": "1080",
        "screen_width": "1920",
        "tz_name": "America/Bogota",
        "user_is_login": "true",
        "verifyFp": verify_fp,
        "webcast_language": "es-419",
    })
    url = f"https://www.tiktok.com/api/im/stranger/unlimit?{params}"
    body = urllib.parse.urlencode({
        "conversation_id": conv_id,
        "to_user_id": to_user_id,
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "accept": "*/*",
        "accept-language": "es-419,es;q=0.9",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.tiktok.com",
        "referer": "https://www.tiktok.com/messages",
        "tt-csrf-token": csrf,
        "user-agent": _UA,
        "cookie": _cookie_str(cookies),
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return data.get("status_code") == 0
    except Exception:
        return False


def block_user(user_id: str, cookies: dict | None = None) -> bool:
    cookies   = cookies or config.COOKIES
    csrf      = cookies.get("tt_csrf_token", "") or config.TT_CSRF_TOKEN or ""
    verify_fp = cookies.get("s_v_web_id", "") or config.VERIFY_FP or ""
    device_id = config.DEVICE_ID or ""
    params = urllib.parse.urlencode({
        "aid": "1988",
        "app_language": "es-419",
        "app_name": "tiktok_web",
        "browser_language": "es-419",
        "browser_name": "Mozilla",
        "browser_online": "true",
        "browser_platform": "Win32",
        "browser_version": "5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0",
        "channel": "tiktok_web",
        "cookie_enabled": "true",
        "data_collection_enabled": "true",
        "device_id": device_id,
        "device_platform": "web_pc",
        "focus_state": "true",
        "history_len": "2",
        "is_fullscreen": "false",
        "is_page_visible": "true",
        "os": "windows",
        "priority_region": "CO",
        "referer": "https://www.tiktok.com/messages",
        "region": "CO",
        "screen_height": "1080",
        "screen_width": "1920",
        "tz_name": "America/Bogota",
        "user_is_login": "true",
        "verifyFp": verify_fp,
        "webcast_language": "es-419",
    })
    url  = f"https://www.tiktok.com/api/commit/relation/block/?{params}"
    body = urllib.parse.urlencode({"to_user_id": user_id}).encode()
    req  = urllib.request.Request(url, data=body, method="POST", headers={
        "accept": "*/*",
        "accept-language": "es-419,es;q=0.9",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.tiktok.com",
        "referer": "https://www.tiktok.com/messages",
        "tt-csrf-token": csrf,
        "user-agent": _UA,
        "cookie": _cookie_str(cookies),
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return data.get("status_code") == 0
    except Exception:
        return False


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
        "Cookie":       _cookie_str(config.COOKIES),
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
