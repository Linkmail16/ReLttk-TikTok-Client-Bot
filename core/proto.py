import uuid
import time
import json
from .signer_client import sign_ws

UA  = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
BV  = "5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
CMD                  = 10015
CMD_REACT            = 705
CMD_REACT_FRAME      = 10010
CMD_UNREACT_FRAME    = 10154
CMD_DELETE           = 701
CMD_DELETE_FRAME     = 10021

_MSG_TYPE_QUOTE = 7524542718409605381
_MSG_TYPE_PLAIN = 7524577932753895688

REACTIONS = {
    "❤️":  7643714214541166097,
    "😂":  7643714214541166098,
    "😮":  7643714214541166099,
    "😢":  7643714214541166100,
    "😠":  7643714214541166101,
    "👍":  7643714214541166102,
}


def encode_varint(v: int) -> bytes:
    v = int(v)
    out = []
    while True:
        bits = v & 0x7F
        v >>= 7
        out.append(0x80 | bits if v else bits)
        if not v:
            break
    return bytes(out)

def f_varint(field: int, v: int) -> bytes:
    return encode_varint((field << 3) | 0) + encode_varint(v)

def f_bytes(field: int, v: bytes) -> bytes:
    return encode_varint((field << 3) | 2) + encode_varint(len(v)) + v

def f_str(field: int, s: str) -> bytes:
    return f_bytes(field, s.encode())

def f_header(k: str, v: str) -> bytes:
    return f_bytes(5, f_str(1, k) + f_str(2, v))

def f_ctx(k: str, v: str) -> bytes:
    return f_bytes(15, f_str(1, k) + f_str(2, v))


def _build_video_share_body(conv_id: str, short_id: int, item_detail: dict,
                            client_id: str) -> bytes:
    video = item_detail.get("itemInfo", {}).get("itemStruct", item_detail)
    item_id   = str(video.get("id", ""))
    author    = video.get("author", {})
    uid       = str(author.get("id", ""))
    sec_uid   = author.get("secUid", "")

    cover_thumb_url = ""
    avatar_thumb = author.get("avatarThumb", "")
    video_cover = video.get("video", {}).get("cover", "")
    thumb_url = video_cover or avatar_thumb or ""

    cover_url_str = video.get("video", {}).get("originCover", video_cover)
    cover_w = video.get("video", {}).get("width", 720)
    cover_h = video.get("video", {}).get("height", 1280)

    content_name = video.get("desc", "")

    def _url_obj(url: str) -> dict:
        return {"url_list": [url], "uri": url}

    payload = {
        "aweType":       800,
        "itemId":        item_id,
        "uid":           uid,
        "secUID":        sec_uid,
        "content_thumb": _url_obj(thumb_url),
        "content_name":  content_name,
        "cover_url":     _url_obj(cover_url_str),
        "cover_width":   cover_w,
        "cover_height":  cover_h,
    }
    content_str = json.dumps(payload, separators=(',', ':'))
    return (
        f_str(1, conv_id) +
        f_varint(2, short_id) +
        f_varint(3, _MSG_TYPE_PLAIN) +
        f_str(4, content_str) +
        f_bytes(5, f_str(1, "s:mentioned_users")   + f_str(2, "")) +
        f_bytes(5, f_str(1, "s:client_message_id") + f_str(2, client_id)) +
        f_varint(6, 8) +
        f_str(7, "deprecated") +
        f_str(8, client_id)
    )


def _build_msg_body(conv_id: str, short_id: int, text: str, client_id: str,
                    quote: dict | None = None, is_group: bool = False) -> bytes:
    if is_group:
        awe = 703 if quote else 0
        content_str = json.dumps({"aweType": awe, "text": text}, separators=(',', ':'))
        body = (
            f_str(1, conv_id) +
            f_varint(2, 2) +
            f_varint(3, int(conv_id)) +
            f_str(4, content_str) +
            f_bytes(5, f_str(1, "s:mentioned_users")   + f_str(2, "")) +
            f_bytes(5, f_str(1, "s:client_message_id") + f_str(2, client_id)) +
            f_varint(6, 7) +
            f_str(7, "deprecated") +
            f_str(8, client_id)
        )
        if quote:
            sub11 = (
                f_varint(1, int(quote.get("msg_type", 0))) +
                f_str(2, json.dumps({
                    "content":               json.dumps({"aweType": quote.get("awe_type", 0), "text": quote["text"]}, separators=(',', ':')),
                    "refmsg_content":        json.dumps(json.dumps({"aweType": quote.get("awe_type", 0), "text": quote["text"]}, separators=(',', ':'))),
                    "refmsg_sec_uid":        quote.get("sec_uid", ""),
                    "refmsg_type":           7,
                    "refmsg_uid":            quote["uid"],
                    "refmsg_sub_type":       "",
                    "refmsg_template_quote": "",
                }, separators=(',', ':'))) +
                f_varint(3, int(quote.get("msg_type", 0))) +
                f_varint(4, int(quote.get("msg_id", 0)))
            )
            body += f_bytes(11, sub11)
        return body

    if quote:
        content_str = json.dumps({"aweType": 703, "text": text}, separators=(',', ':'))
        quoted_inner = json.dumps({"aweType": quote.get("awe_type", 0), "text": quote["text"]}, separators=(',', ':'))
        ref_obj = {
            "content":               quoted_inner,
            "refmsg_content":        json.dumps(json.dumps(quoted_inner)),
            "refmsg_sec_uid":        quote.get("sec_uid", ""),
            "refmsg_type":           7,
            "refmsg_uid":            quote["uid"],
            "refmsg_sub_type":       "",
            "refmsg_template_quote": "",
        }
        sub11 = (
            f_varint(1, int(quote.get("msg_type", 7643712568255399440))) +
            f_varint(3, int(quote.get("msg_type", 7643712568255399440))) +
            f_varint(4, int(quote.get("msg_id", 0)))
        )
        field3_val = 7524542718409605381
    else:
        content_str = json.dumps({"aweType": 0, "text": text}, separators=(',', ':'))
        field3_val  = 7305620471088775430

    body = (
        f_str(1, conv_id) +
        f_varint(2, short_id) +
        f_varint(3, field3_val) +
        f_str(4, content_str) +
        f_bytes(5, f_str(1, "s:mentioned_users")   + f_str(2, "")) +
        f_bytes(5, f_str(1, "s:client_message_id") + f_str(2, client_id)) +
        f_varint(6, 7) +
        f_str(7, "deprecated") +
        f_str(8, client_id)
    )
    if quote:
        body += f_bytes(11, sub11)
    return body


def _build_reaction_body(conv_id: str, short_id: int, msg_type: int,
                         emoji: str, sender_id: str, client_id: str,
                         remove: bool = False) -> bytes:
    emoji_str = f"e:{emoji}"
    sub6 = (
        f_varint(1, 1 if remove else 0) +
        f_bytes(2, emoji_str.encode("utf-8")) +
        f_str(4, sender_id)
    )
    inner = (
        f_str(1, conv_id) +
        f_varint(2, short_id) +
        f_varint(3, 7524577932753895688) +
        f_varint(4, msg_type) +
        f_str(5, client_id) +
        f_bytes(6, sub6)
    )
    return f_bytes(1, inner)


def _build_reaction_request_body(react_body: bytes, device_id: str, sdk_ms_token: str,
                                  tt_public_key: str, tt_client_data: str) -> bytes:
    ctx = [
        ("aid",             "1988"),
        ("app_name",        "tiktok_web"),
        ("channel",         "web"),
        ("device_platform", "web_pc"),
        ("device_id",       device_id),
        ("region",          "CO"),
        ("priority_region", "CO"),
        ("os",              "windows"),
        ("referer",         "https://www.tiktok.com/messages?lang=es-419"),
        ("root_referer",    ""),
        ("cookie_enabled",  "true"),
        ("screen_width",    "1920"),
        ("screen_height",   "1080"),
        ("browser_language","es-ES"),
        ("browser_platform","Win32"),
        ("browser_name",    "Mozilla"),
        ("browser_version", BV),
        ("browser_online",  "true"),
        ("verifyFp",        ""),
        ("app_language",    "es-419"),
        ("webcast_language","es-419"),
        ("tz_name",         "America/Bogota"),
        ("is_page_visible", "true"),
        ("focus_state",     "true"),
        ("is_fullscreen",   "false"),
        ("history_len",     "3"),
        ("user_is_login",   "true"),
        ("data_collection_enabled", "true"),
        ("from_appID",      "1988"),
        ("locale",          "es-419"),
        ("user_agent",      UA),
        ("Web-Sdk-Ms-Token",                    sdk_ms_token),
        ("tt-ticket-guard-public-key",          tt_public_key),
        ("tt-ticket-guard-client-data",         tt_client_data),
        ("tt-ticket-guard-version",             "2"),
        ("tt-ticket-guard-iteration-version",   "0"),
        ("tt-ticket-guard-web-version",         "1"),
    ]
    return (
        f_varint(1, CMD_REACT) +
        f_varint(2, CMD_REACT) +
        f_str(3, "1.7.0") +
        f_str(4, "") +
        f_varint(5, 3) +
        f_varint(6, 0) +
        f_str(7, "e465244:feat/call-trace-plugin") +
        f_bytes(8, f_bytes(CMD_REACT, react_body) + f_str(2, "deprecated")) +
        f_str(9, device_id) +
        f_str(11, "web") +
        b''.join(f_ctx(k, v) for k, v in ctx) +
        f_varint(18, 1)
    )


def _build_request_body(msg_body: bytes, device_id: str, sdk_ms_token: str,
                        tt_public_key: str, tt_client_data: str) -> bytes:
    ctx = [
        ("aid",             "1988"),
        ("app_name",        "tiktok_web"),
        ("channel",         "web"),
        ("device_platform", "web_pc"),
        ("device_id",       device_id),
        ("region",          "CO"),
        ("priority_region", "CO"),
        ("os",              "windows"),
        ("referer",         "https://www.tiktok.com/messages?lang=es-419"),
        ("root_referer",    ""),
        ("cookie_enabled",  "true"),
        ("screen_width",    "1920"),
        ("screen_height",   "1080"),
        ("browser_language","es-ES"),
        ("browser_platform","Win32"),
        ("browser_name",    "Mozilla"),
        ("browser_version", BV),
        ("browser_online",  "true"),
        ("verifyFp",        ""),
        ("app_language",    "es-419"),
        ("webcast_language","es-419"),
        ("tz_name",         "America/Bogota"),
        ("is_page_visible", "true"),
        ("focus_state",     "true"),
        ("is_fullscreen",   "false"),
        ("history_len",     "3"),
        ("user_is_login",   "true"),
        ("data_collection_enabled", "true"),
        ("from_appID",      "1988"),
        ("locale",          "es-419"),
        ("user_agent",      UA),
        ("Web-Sdk-Ms-Token",                    sdk_ms_token),
        ("tt-ticket-guard-public-key",          tt_public_key),
        ("tt-ticket-guard-client-data",         tt_client_data),
        ("tt-ticket-guard-version",             "2"),
        ("tt-ticket-guard-iteration-version",   "0"),
        ("tt-ticket-guard-web-version",         "1"),
    ]
    return (
        f_varint(1, 100) +
        f_varint(2, CMD) +
        f_str(3, "1.7.0") +
        f_str(4, "") +
        f_varint(5, 3) +
        f_varint(6, 0) +
        f_str(7, "e465244:feat/call-trace-plugin") +
        f_bytes(8, f_bytes(100, msg_body)) +
        f_str(9, device_id) +
        f_str(11, "web") +
        b''.join(f_ctx(k, v) for k, v in ctx) +
        f_varint(18, 1)
    )


def build_ws_packet(
    conv_id: str,
    short_id: int,
    text: str,
    device_id: str,
    sdk_ms_token: str,
    tt_public_key: str  = "",
    tt_client_data: str = "",
    bogus_index: int    = 1,
    quote: dict | None  = None,
    is_group: bool      = False,
) -> tuple[bytes, int]:
    client_id = str(uuid.uuid4())
    seq_id    = int(time.time() * 1000)

    if is_group:
        msg_type = int(conv_id)
    elif quote:
        msg_type = 7524542718409605381
    else:
        msg_type = 7305620471088775430
    msg_body     = _build_msg_body(conv_id, short_id, text, client_id, quote, is_group)
    request_body = _build_request_body(msg_body, device_id, sdk_ms_token,
                                       tt_public_key, tt_client_data)

    raw_for_sign = (
        f_varint(1, CMD) +
        f_varint(2, seq_id) +
        f_varint(3, 5) +
        f_varint(4, 1) +
        f_str(7, "pb") +
        f_bytes(8, request_body)
    )
    x_bogus = sign_ws(raw_for_sign.hex()[:32], bogus_index)

    frame_headers = [
        ("X-Bogus",         x_bogus),
        ("aid",             "1988"),
        ("app_name",        "tiktok_web"),
        ("channel",         "web"),
        ("device_platform", "web_pc"),
        ("device_id",       device_id),
        ("region",          "CO"),
        ("priority_region", "CO"),
        ("os",              "windows"),
        ("referer",         "https://www.tiktok.com/messages?lang=es-419"),
        ("root_referer",    ""),
        ("cookie_enabled",  "true"),
        ("screen_width",    "1920"),
        ("screen_height",   "1080"),
        ("browser_language","es-ES"),
        ("browser_platform","Win32"),
        ("browser_name",    "Mozilla"),
        ("browser_version", BV),
        ("browser_online",  "true"),
        ("verifyFp",        ""),
        ("app_language",    "es-419"),
        ("webcast_language","es-419"),
        ("tz_name",         "America/Bogota"),
        ("is_page_visible", "true"),
        ("focus_state",     "true"),
        ("is_fullscreen",   "false"),
        ("history_len",     "3"),
        ("user_is_login",   "true"),
        ("data_collection_enabled", "true"),
        ("from_appID",      "1988"),
        ("locale",          "es-419"),
        ("user_agent",      UA),
        ("Web-Sdk-Ms-Token", sdk_ms_token),
    ]

    packet = (
        f_varint(1, CMD) +
        f_varint(2, seq_id) +
        f_varint(3, 5) +
        f_varint(4, 1) +
        b''.join(f_header(k, v) for k, v in frame_headers) +
        f_str(7, "pb") +
        f_bytes(8, request_body)
    )
    return packet, msg_type


def build_video_share_packet(
    conv_id: str,
    item_detail: dict,
    device_id: str,
    sdk_ms_token: str,
    tt_public_key: str  = "",
    tt_client_data: str = "",
    short_id: int       = 1,
    bogus_index: int    = 1,
) -> tuple[bytes, int]:
    client_id    = str(uuid.uuid4())
    seq_id       = int(time.time() * 1000)
    msg_body     = _build_video_share_body(conv_id, short_id, item_detail, client_id)
    request_body = _build_request_body(msg_body, device_id, sdk_ms_token,
                                       tt_public_key, tt_client_data)
    raw_for_sign = (
        f_varint(1, CMD) +
        f_varint(2, seq_id) +
        f_varint(3, 5) +
        f_varint(4, 1) +
        f_str(7, "pb") +
        f_bytes(8, request_body)
    )
    x_bogus = sign_ws(raw_for_sign.hex()[:32], bogus_index)
    frame_headers = [
        ("X-Bogus",         x_bogus),
        ("aid",             "1988"),
        ("app_name",        "tiktok_web"),
        ("channel",         "web"),
        ("device_platform", "web_pc"),
        ("device_id",       device_id),
        ("region",          "CO"),
        ("priority_region", "CO"),
        ("os",              "windows"),
        ("referer",         "https://www.tiktok.com/messages?lang=es-419"),
        ("root_referer",    ""),
        ("cookie_enabled",  "true"),
        ("screen_width",    "1920"),
        ("screen_height",   "1080"),
        ("browser_language","es-ES"),
        ("browser_platform","Win32"),
        ("browser_name",    "Mozilla"),
        ("browser_version", BV),
        ("browser_online",  "true"),
        ("verifyFp",        ""),
        ("app_language",    "es-419"),
        ("webcast_language","es-419"),
        ("tz_name",         "America/Bogota"),
        ("is_page_visible", "true"),
        ("focus_state",     "true"),
        ("is_fullscreen",   "false"),
        ("history_len",     "3"),
        ("user_is_login",   "true"),
        ("data_collection_enabled", "true"),
        ("from_appID",      "1988"),
        ("locale",          "es-419"),
        ("user_agent",      UA),
        ("Web-Sdk-Ms-Token", sdk_ms_token),
    ]
    packet = (
        f_varint(1, CMD) +
        f_varint(2, seq_id) +
        f_varint(3, 5) +
        f_varint(4, 1) +
        b''.join(f_header(k, v) for k, v in frame_headers) +
        f_str(7, "pb") +
        f_bytes(8, request_body)
    )
    return packet, _MSG_TYPE_PLAIN


def build_reaction_packet(
    conv_id: str,
    msg_type: int,
    emoji: str,
    sender_id: str,
    device_id: str,
    sdk_ms_token: str,
    tt_public_key: str  = "",
    tt_client_data: str = "",
    short_id: int       = 1,
    bogus_index: int    = 1,
    remove: bool        = False,
) -> bytes:
    client_id  = str(uuid.uuid4())
    seq_id     = int(time.time() * 1000)
    CMD_DELETE_FRAME  = CMD_UNREACT_FRAME if remove else CMD_REACT_FRAME

    react_body   = _build_reaction_body(conv_id, short_id, msg_type, emoji, sender_id, client_id, remove)
    request_body = _build_reaction_request_body(react_body, device_id, sdk_ms_token,
                                                tt_public_key, tt_client_data)

    raw_for_sign = (
        f_varint(1, CMD_DELETE_FRAME) +
        f_varint(2, seq_id) +
        f_varint(3, 5) +
        f_varint(4, 1) +
        f_str(7, "pb") +
        f_bytes(8, request_body)
    )
    x_bogus = sign_ws(raw_for_sign.hex()[:32], bogus_index)

    frame_headers = [
        ("X-Bogus",         x_bogus),
        ("aid",             "1988"),
        ("app_name",        "tiktok_web"),
        ("channel",         "web"),
        ("device_platform", "web_pc"),
        ("device_id",       device_id),
        ("region",          "CO"),
        ("priority_region", "CO"),
        ("os",              "windows"),
        ("referer",         "https://www.tiktok.com/messages?lang=es-419"),
        ("root_referer",    ""),
        ("cookie_enabled",  "true"),
        ("screen_width",    "1920"),
        ("screen_height",   "1080"),
        ("browser_language","es-ES"),
        ("browser_platform","Win32"),
        ("browser_name",    "Mozilla"),
        ("browser_version", BV),
        ("browser_online",  "true"),
        ("verifyFp",        ""),
        ("app_language",    "es-419"),
        ("webcast_language","es-419"),
        ("tz_name",         "America/Bogota"),
        ("is_page_visible", "true"),
        ("focus_state",     "true"),
        ("is_fullscreen",   "false"),
        ("history_len",     "3"),
        ("user_is_login",   "true"),
        ("data_collection_enabled", "true"),
        ("from_appID",      "1988"),
        ("locale",          "es-419"),
        ("user_agent",      UA),
        ("Web-Sdk-Ms-Token", sdk_ms_token),
    ]

    return (
        f_varint(1, CMD_DELETE_FRAME) +
        f_varint(2, seq_id) +
        f_varint(3, 5) +
        f_varint(4, 1) +
        b''.join(f_header(k, v) for k, v in frame_headers) +
        f_str(7, "pb") +
        f_bytes(8, request_body)
    )


def build_delete_packet(
    conv_id: str,
    msg_type: int,
    device_id: str,
    sdk_ms_token: str,
    tt_public_key: str  = "",
    tt_client_data: str = "",
    short_id: int       = 1,
    bogus_index: int    = 1,
) -> bytes:
    seq_id = int(time.time() * 1000)

    body_const = _MSG_TYPE_QUOTE if (msg_type == _MSG_TYPE_QUOTE) else _MSG_TYPE_PLAIN

    delete_body = (
        f_str(1, conv_id) +
        f_varint(2, body_const) +
        f_varint(3, short_id) +
        f_varint(4, msg_type)
    )
    ctx = [
        ("aid", "1988"), ("app_name", "tiktok_web"), ("channel", "web"),
        ("device_platform", "web_pc"), ("device_id", device_id),
        ("region", "CO"), ("priority_region", "CO"), ("os", "windows"),
        ("referer", "https://www.tiktok.com/messages?lang=es-419"),
        ("root_referer", ""), ("cookie_enabled", "true"),
        ("screen_width", "1920"), ("screen_height", "1080"),
        ("browser_language", "es-ES"), ("browser_platform", "Win32"),
        ("browser_name", "Mozilla"), ("browser_version", BV),
        ("browser_online", "true"), ("verifyFp", ""),
        ("app_language", "es-419"), ("webcast_language", "es-419"),
        ("tz_name", "America/Bogota"), ("is_page_visible", "true"),
        ("focus_state", "true"), ("is_fullscreen", "false"),
        ("history_len", "3"), ("user_is_login", "true"),
        ("data_collection_enabled", "true"), ("from_appID", "1988"),
        ("locale", "es-419"), ("user_agent", UA),
        ("Web-Sdk-Ms-Token", sdk_ms_token),
        ("tt-ticket-guard-public-key", tt_public_key),
        ("tt-ticket-guard-client-data", tt_client_data),
        ("tt-ticket-guard-version", "2"),
        ("tt-ticket-guard-iteration-version", "0"),
        ("tt-ticket-guard-web-version", "1"),
    ]
    request_body = (
        f_varint(1, CMD_DELETE) +
        f_varint(2, CMD_DELETE_FRAME) +
        f_str(3, "1.7.0") +
        f_str(4, "") +
        f_varint(5, 3) +
        f_varint(6, 0) +
        f_str(7, "e465244:feat/call-trace-plugin") +
        f_bytes(8, f_bytes(CMD_DELETE, delete_body) + f_str(2, "deprecated")) +
        f_str(9, device_id) +
        f_str(11, "web") +
        b''.join(f_ctx(k, v) for k, v in ctx) +
        f_varint(18, 1)
    )

    raw_for_sign = (
        f_varint(1, CMD_DELETE_FRAME) +
        f_varint(2, seq_id) +
        f_varint(3, 5) +
        f_varint(4, 1) +
        f_str(7, "pb") +
        f_bytes(8, request_body)
    )
    x_bogus = sign_ws(raw_for_sign.hex()[:32], bogus_index)

    frame_headers = [
        ("X-Bogus", x_bogus), ("aid", "1988"), ("app_name", "tiktok_web"),
        ("channel", "web"), ("device_platform", "web_pc"), ("device_id", device_id),
        ("region", "CO"), ("priority_region", "CO"), ("os", "windows"),
        ("referer", "https://www.tiktok.com/messages?lang=es-419"),
        ("root_referer", ""), ("cookie_enabled", "true"),
        ("screen_width", "1920"), ("screen_height", "1080"),
        ("browser_language", "es-ES"), ("browser_platform", "Win32"),
        ("browser_name", "Mozilla"), ("browser_version", BV),
        ("browser_online", "true"), ("verifyFp", ""),
        ("app_language", "es-419"), ("webcast_language", "es-419"),
        ("tz_name", "America/Bogota"), ("is_page_visible", "true"),
        ("focus_state", "true"), ("is_fullscreen", "false"),
        ("history_len", "3"), ("user_is_login", "true"),
        ("data_collection_enabled", "true"), ("from_appID", "1988"),
        ("locale", "es-419"), ("user_agent", UA),
        ("Web-Sdk-Ms-Token", sdk_ms_token),
    ]

    return (
        f_varint(1, CMD_DELETE_FRAME) +
        f_varint(2, seq_id) +
        f_varint(3, 5) +
        f_varint(4, 1) +
        b''.join(f_header(k, v) for k, v in frame_headers) +
        f_str(7, "pb") +
        f_bytes(8, request_body)
    )
