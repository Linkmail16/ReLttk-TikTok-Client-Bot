import os
import json
import shutil
import sqlite3
import tempfile

_TIKTOK_KEYS = {"sessionid", "msToken", "ttwid", "tt_csrf_token", "sid_guard", "uid_tt", "uid_tt_ss", "sid_tt", "sid_tt_ss", "store-idc", "store-country-code"}

_CHROMIUM_PATHS = {
    "chrome": os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Network\Cookies"),
    "brave":  os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data\Default\Network\Cookies"),
    "edge":   os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Network\Cookies"),
}

_FIREFOX_PROFILES = os.path.expandvars(r"%APPDATA%\Mozilla\Firefox\Profiles")


_BROWSER_PROCS = {
    "chrome":  "chrome",
    "brave":   "brave",
    "edge":    "msedge",
    "firefox": "firefox",
}

def _read_locked_file(path: str, browser: str) -> bytes:
    try:
        with open(path, "rb") as f:
            return f.read()
    except PermissionError:
        pass

    import subprocess, time
    proc = _BROWSER_PROCS.get(browser)
    if proc:
        subprocess.run(["taskkill", "/F", "/IM", f"{proc}.exe"], capture_output=True)
        time.sleep(1.5)

    try:
        with open(path, "rb") as f:
            return f.read()
    except PermissionError:
        raise PermissionError(f"no se pudo leer el archivo de cookies de {browser}")


def _get_chromium_key(browser: str) -> bytes:
    import base64, ctypes
    cookie_path = _CHROMIUM_PATHS.get(browser) or next(p for p in _CHROMIUM_PATHS.values() if os.path.exists(p))
    local_state_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(cookie_path))), "Local State")
    with open(local_state_path, encoding="utf-8") as f:
        key_b64 = json.load(f)["os_crypt"]["encrypted_key"]
    enc_key = base64.b64decode(key_b64)[5:]
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_char))]
    blob_in  = DATA_BLOB(len(enc_key), ctypes.cast(ctypes.c_char_p(enc_key), ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
    return bytes(blob_out.pbData[:blob_out.cbData])


def _decrypt_chromium(encrypted: bytes, browser: str = "") -> str:
    if not encrypted:
        return ""
    prefix = encrypted[:3]
    if prefix in (b"v10", b"v11"):
        try:
            key = _get_chromium_key(browser)
            from Crypto.Cipher import AES
            nonce = encrypted[3:15]
            ct    = encrypted[15:-16]
            tag   = encrypted[-16:]
            return AES.new(key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ct, tag).decode("utf-8", errors="replace")
        except Exception:
            pass
    elif prefix == b"v20":
        try:
            key = _get_chromium_key(browser)
            from Crypto.Cipher import AES
            inner = encrypted[3:]
            nonce = inner[32:44]
            ct    = inner[44:-16]
            tag   = inner[-16:]
            return AES.new(key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ct, tag).decode("utf-8", errors="replace")
        except Exception:
            pass
    try:
        import ctypes
        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_char))]
        blob_in  = DATA_BLOB(len(encrypted), ctypes.cast(ctypes.c_char_p(encrypted), ctypes.POINTER(ctypes.c_char)))
        blob_out = DATA_BLOB()
        ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
        return bytes(blob_out.pbData[:blob_out.cbData]).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _read_chromium(browser: str) -> dict:
    path = _CHROMIUM_PATHS.get(browser)
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"no se encontro el archivo de cookies de {browser}")

    data = _read_locked_file(path, browser)
    tmp = tempfile.mktemp(suffix=".db")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        conn = sqlite3.connect(f"file:{tmp}?mode=ro&immutable=1", uri=True)
        cur = conn.cursor()
        cur.execute(
            "SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%tiktok.com%'"
        )
        rows = cur.fetchall()
        conn.close()
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass

    cookies = {}
    for name, enc_val in rows:
        if name not in _TIKTOK_KEYS:
            continue
        val = _decrypt_chromium(bytes(enc_val), browser)
        if val:
            cookies[name] = val
    return cookies


def _debug_all_cookies(browser: str) -> dict:
    browser = browser.lower()
    if browser == "firefox":
        profile = None
        for name in os.listdir(_FIREFOX_PROFILES):
            if "default-release" in name:
                profile = os.path.join(_FIREFOX_PROFILES, name)
                break
        db_path = os.path.join(profile, "cookies.sqlite")
        tmp = tempfile.mktemp(suffix=".db")
        shutil.copy2(db_path, tmp)
        try:
            conn = sqlite3.connect(f"file:{tmp}?mode=ro&immutable=1", uri=True)
            cur = conn.cursor()
            cur.execute("SELECT name, value FROM moz_cookies WHERE host LIKE '%tiktok.com%'")
            rows = cur.fetchall()
            conn.close()
        finally:
            try: os.remove(tmp)
            except: pass
        return {name: val for name, val in rows}
    else:
        path = _CHROMIUM_PATHS.get(browser)
        data = _read_locked_file(path, browser)
        tmp = tempfile.mktemp(suffix=".db")
        try:
            with open(tmp, "wb") as f:
                f.write(data)
            conn = sqlite3.connect(f"file:{tmp}?mode=ro&immutable=1", uri=True)
            cur = conn.cursor()
            cur.execute("SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%tiktok.com%'")
            rows = cur.fetchall()
            conn.close()
        finally:
            try: os.remove(tmp)
            except: pass
        return {name: _decrypt_chromium(bytes(enc), browser) for name, enc in rows}


def _read_firefox() -> dict:
    if not os.path.exists(_FIREFOX_PROFILES):
        raise FileNotFoundError("no se encontro el perfil de Firefox")

    profile = None
    for name in os.listdir(_FIREFOX_PROFILES):
        if "default-release" in name:
            profile = os.path.join(_FIREFOX_PROFILES, name)
            break
    if not profile:
        entries = os.listdir(_FIREFOX_PROFILES)
        if entries:
            profile = os.path.join(_FIREFOX_PROFILES, entries[0])
    if not profile:
        raise FileNotFoundError("no se encontro perfil de Firefox")

    db_path = os.path.join(profile, "cookies.sqlite")
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"no se encontro cookies.sqlite en {profile}")

    tmp = tempfile.mktemp(suffix=".db")
    shutil.copy2(db_path, tmp)
    try:
        conn = sqlite3.connect(tmp)
        cur = conn.cursor()
        cur.execute(
            "SELECT name, value FROM moz_cookies WHERE host LIKE '%tiktok.com%'"
        )
        rows = cur.fetchall()
        conn.close()
    finally:
        os.remove(tmp)

    return {name: val for name, val in rows if name in _TIKTOK_KEYS and val}


def get_tiktok_cookies(browser: str) -> dict:
    browser = browser.lower()
    if browser == "firefox":
        cookies = _read_firefox()
    elif browser in _CHROMIUM_PATHS:
        cookies = _read_chromium(browser)
    else:
        raise ValueError(f"navegador no soportado: {browser}. Usa: chrome, brave, edge, firefox")

    if not cookies.get("sessionid"):
        raise RuntimeError(f"no se encontro sessionid de TikTok en {browser} — asegurate de estar logueado en TikTok")

    return cookies
