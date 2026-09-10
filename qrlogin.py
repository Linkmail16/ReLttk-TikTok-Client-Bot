import http.cookiejar
import json
import os
import sys
import threading
import time

try:
    from . import log as _log
except ImportError:
    import log as _log

_stop_event = threading.Event()
import urllib.parse
import urllib.request


                                                                               
_AID       = "1459"
_UA        = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
_VERIFY_FP = "verify_mplnlgno_s07vIKFn_2ii8_43lR_800G_hibLVGVaQnut"
_REGION    = "CO"
_LANG      = "es-419"

_SESSION_DIR    = os.path.join(os.path.dirname(__file__), "sesion")
_SEED_MS_TOKEN  = "n8VdIat8AnERg_j9aNTiWJAHodoWYeC4bFBiz8RqtURuz_RdFacc_r5w85R1o2oGXsqaWRvXDZkdq6u4ywHT8DMXuJ5XapDs70Tjl_Fz-rnvfNEUDfvlJglps5crqgNnRtxhw4Ez"

_SHARK_EXTRA_TMPL = (
    '{{"aid":{aid},"app_name":"Tik_Tok_Login","channel":"tiktok_web",'
    '"device_platform":"web_pc","device_id":"{did}","region":"{region}",'
    '"priority_region":"","os":"windows","referer":"","cookie_enabled":true,'
    '"screen_width":1680,"screen_height":1050,"browser_language":"{lang}",'
    '"browser_platform":"Win32","browser_name":"Mozilla",'
    '"browser_version":"5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",'
    '"browser_online":true,"verifyFp":"{vfp}","app_language":"{lang}",'
    '"webcast_language":"{lang}","tz_name":"America/Bogota",'
    '"is_page_visible":true,"focus_state":true,"is_fullscreen":false,'
    '"history_len":3,"user_is_login":false,"data_collection_enabled":false}}'
)


def _sign(query: str) -> str:
    from importlib import import_module
    sign_full = import_module(f"{_pkg_name()}.core.signer_client").sign_full
    qs = query.rstrip("&").removesuffix("msToken=").rstrip("&")
    signed, x_gnarly = sign_full(qs, ua=_UA)
    return f"{signed}&X-Gnarly={urllib.parse.quote(x_gnarly, safe='')}"


def _shark_extra(did: str) -> str:
    raw = _SHARK_EXTRA_TMPL.format(
        aid=_AID, did=did, region=_REGION, lang=_LANG, vfp=_VERIFY_FP
    )
    return urllib.parse.quote(raw)


def _base_params(did: str) -> str:
    return (
        f"next=https%3A%2F%2Fwww.tiktok.com"
        f"&multi_login=1"
        f"&did={did}"
        f"&locale={_LANG}"
        f"&app_language={_LANG.split('-')[0]}"
        f"&aid={_AID}"
        f"&account_sdk_source=web"
        f"&sdk_version=2.1.12-tiktok"
        f"&language={_LANG}"
        f"&verifyFp={_VERIFY_FP}"
        f"&target_aid="
        f"&standalone_aid="
        f"&shark_extra={_shark_extra(did)}"
    )


def _fetch_ms_token(did: str) -> str:
    query = (
        f"aid=1988&app_language={_LANG}&app_name=tiktok_web"
        f"&browser_language={_LANG}&browser_name=Mozilla&browser_online=true"
        f"&browser_platform=Win32"
        f"&browser_version=5.0%20%28Windows%20NT%2010.0%3B%20Win64%3B%20x64%29%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Chrome%2F148.0.0.0%20Safari%2F537.36"
        f"&channel=tiktok_web&cookie_enabled=true&data_collection_enabled=false"
        f"&device_id={did}&device_platform=web_pc"
        f"&focus_state=true&from_page=&history_len=2"
        f"&is_fullscreen=false&is_page_visible=true&os=windows"
        f"&priority_region=&referer=&region={_REGION}"
        f"&screen_height=900&screen_width=1440"
        f"&tz_name=America%2FBogota&user_is_login=false"
        f"&webcast_language={_LANG}&msToken="
    )
    for attempt in range(2):
        try:
            signed = _sign(query)
            url = f"https://web-sg.tiktok.com/passport/web/store_region/?{signed}"
            req = urllib.request.Request(url, headers={
                "User-Agent":                _UA,
                "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language":           "es-419,es;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cookie":                    f"msToken={_SEED_MS_TOKEN}",
                "sec-ch-ua":                 '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
                "sec-ch-ua-mobile":          "?0",
                "sec-ch-ua-platform":        '"Windows"',
                "sec-fetch-dest":            "document",
                "sec-fetch-mode":            "navigate",
                "sec-fetch-site":            "none",
                "sec-fetch-user":            "?1",
                "upgrade-insecure-requests": "1",
                "pragma":                    "no-cache",
                "cache-control":             "no-cache",
            })
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    raw_headers = resp.headers
            except urllib.error.HTTPError as e:
                raw_headers = e.headers
            for line in str(raw_headers).splitlines():
                if line.lower().startswith("set-cookie:"):
                    part = line[len("set-cookie:"):].strip().split(";")[0].strip()
                    if part.startswith("msToken=") and len(part) > len("msToken="):
                        return part[len("msToken="):]
            return ""
        except Exception as e:
            _log.error("qrlogin", f"store_region intento {attempt + 1}/2 fallo: {e}")
    return ""


def _shorten_url(opener, index_url: str, did: str) -> str:
    target = (
        index_url
        + "&app_type=m"
        + "&next_url=https%3A%2F%2Fwww.tiktok.com%2Fpassport%2Fweb%2Fscan_qrcode%2F%3Fclient_secret%3DC8Z2F87E"
    )
    params = (
        "aid=1988&app_language=es-419&app_name=tiktok_web"
        "&browser_language=es-419&browser_name=Mozilla&browser_online=true"
        "&browser_platform=Win32"
        f"&browser_version={urllib.parse.quote(_UA)}"
        "&channel=tiktok_web&cookie_enabled=true&data_collection_enabled=false"
        f"&device_id={did}&device_platform=web_pc"
        "&focus_state=true&from_page=&history_len=3"
        "&is_fullscreen=false&is_page_visible=true&os=windows"
        "&priority_region=&referer=&region=CO"
        "&safe_token=true&screen_height=1050&screen_width=1680"
        "&tz_name=America%2FBogota&user_is_login=false"
        f"&verifyFp={_VERIFY_FP}&webcast_language=es-419"
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
    })
    with opener.open(req, timeout=10) as resp:
        data = json.loads(resp.read())
    if data.get("code") != 0:
        raise RuntimeError(f"shorten fallo: {data}")
    entries = data.get("data", [])
    if not entries:
        raise RuntimeError("shorten: respuesta vacia")
    return entries[0]["short_url"]


def _print_qr(url: str):
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except ImportError:
        _log.warn("qrlogin", "instala qrcode: pip install qrcode")
        _log.info("qrlogin", f"URL: {url}")


def _write_cookies(cookies: dict, username: str = "_temp"):
    os.makedirs(_SESSION_DIR, exist_ok=True)
    path = os.path.join(_SESSION_DIR, f"{username}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2)
    return path


def load_session(username: str) -> dict:
    path = os.path.join(_SESSION_DIR, f"{username}.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def list_sessions() -> list[str]:
    try:
        return [
            f[:-5] for f in os.listdir(_SESSION_DIR) if f.endswith(".json")
        ]
    except FileNotFoundError:
        return []


def _pkg_name() -> str:
    return os.path.basename(os.path.dirname(os.path.abspath(__file__)))


def run(did: str | None = None):
    if did is None:
        try:
            from importlib import import_module
            _cfg = import_module(f"{_pkg_name()}.config")
            did = getattr(_cfg, "DEVICE_ID", None) or None
        except Exception:
            pass
    if not did:
        import random
        did = str(random.randint(7_000_000_000_000_000_000, 7_999_999_999_999_999_999))
        _log.info("qrlogin", f"DEVICE_ID: {did}")

    _stop_event.clear()

    while not _stop_event.is_set():
        cookies = _try_login(did)
        if cookies is not None:
            break
        if not _stop_event.is_set():
            _log.info("qrlogin", "reiniciando...")

    if _stop_event.is_set():
        return

    sessionid = cookies.get("sessionid", "")
    if not sessionid:
        _log.warn("qrlogin", "advertencia: no se encontro sessionid")
        _log.warn("qrlogin", f"cookies recibidas: {list(cookies.keys())}")
        return

    _log.ok("qrlogin", f"sesion obtenida: {sessionid[:8]}...")

    username = f"session_{sessionid[:8]}"
    try:
        from importlib import import_module
        _api = import_module(f"{_pkg_name()}.core.api")
        uid = _api.get_own_user_id(cookies=cookies)
        profiles = _api.get_user_profiles([uid], cookies=cookies)
        if profiles:
            username = profiles[0].get("unique_id") or username
    except Exception as e:
        _log.warn("qrlogin", f"no se pudo obtener username ({e}), usando '{username}'")

    path = _write_cookies(cookies, username)
    _log.ok("qrlogin", f"sesion guardada: {path}")


def _handle_2fa(opener, passport_ticket: str) -> bool:
    base = (
        f"aid={_AID}"
        f"&pseudo_id=PID00000000000000000"
        f"&passport_ticket={urllib.parse.quote(passport_ticket)}"
        f"&mix_mode=0"
        f"&fixed_mix_mode=0"
    )
    url = f"https://web-sg.tiktok.com/passport/aaas/authenticate/"
    csrf = ""
    for h in opener.handlers:
        if hasattr(h, "cookiejar"):
            csrf = next((c.value for c in h.cookiejar if c.name == "tt_csrf_token"), "")
            break

    def _post(extra: str):
        body = (base + "&" + extra).encode()
        req = urllib.request.Request(url, data=body, method="POST", headers={
            "User-Agent":    _UA,
            "Content-Type":  "application/x-www-form-urlencoded",
            "Referer":       "https://www.tiktok.com/login/qrcode",
            "Accept":        "application/json, text/javascript",
            "x-tt-passport-csrf-token": csrf,
        })
        with opener.open(req, timeout=15) as resp:
            return json.loads(resp.read())

    try:
        r = _post("challenge_type=2&action=3")
        if r.get("message") != "success":
            _log.error("qrlogin", f"2FA: error enviando código: {r}")
            return False
        _log.ok("qrlogin", "2FA: código enviado al email/teléfono registrado")
    except Exception as e:
        _log.error("qrlogin", f"2FA: error en action=3: {e}")
        return False

    code = input("[qrlogin] ingresa el código de verificación: ").strip()
    if not code:
        _log.error("qrlogin", "2FA: código vacío, cancelando")
        return False

    hex_code = code.encode().hex()
    try:
        r = _post(f"challenge_type=2&action=4&mix_mode=1&fixed_mix_mode=1&code={urllib.parse.quote(hex_code)}")
        if r.get("message") != "success":
            _log.error("qrlogin", f"2FA: código incorrecto: {r}")
            return False
        _log.ok("qrlogin", "2FA: verificación exitosa")
        return True
    except Exception as e:
        _log.error("qrlogin", f"2FA: error en action=4: {e}")
        return False


def _try_login(did: str) -> dict | None:
                                        
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

                                                                 
    req = urllib.request.Request("https://www.tiktok.com/login/qrcode", headers={
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-419,es;q=0.9",
        "Referer": "https://www.tiktok.com/",
    })
    try:
        opener.open(req, timeout=10)
    except Exception as e:
        _log.warn("qrlogin", f"advertencia cargando pagina inicial: {e}")

                      
    _log.info("qrlogin", "obteniendo codigo QR...")
    data = None
    for attempt in range(2):
        try:
            query = _base_params(did)
            signed = _sign(query)
            url = f"https://www.tiktok.com/passport/web/get_qrcode/?{signed}"
            req = urllib.request.Request(url, headers={
                "User-Agent": _UA,
                'accept': 'application/json, text/javascript',
    'accept-language': 'es-US,es-419;q=0.9,es;q=0.8',
    'priority': 'u=1, i',
    'referer': 'https://www.tiktok.com/login/qrcode',
    'sec-ch-ua': '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'tt-ticket-guard-iteration-version': '0',
    'tt-ticket-guard-public-key': 'BMfZl+/keYLdE+lGmdH2V5xBmDxCWi6+lFeuJstXEoPl4z3HmiUGTI6FHz+FeeI6t3ECvg+mzHxgnYTCpeg6uFU=',
    'tt-ticket-guard-version': '2',
    'tt-ticket-guard-web-version': '1',
    'x-mssdk-info': '6RS5jcr8H1p2U88fAP6qdtyxugcCwojZasVZpsm8R6hfT.cuZpdWxgjWeBlYW1158N1b2XgdCeI-8wlueeFxhibS.bM6YzULZvif1N-OLWaIMDT.zHb2ACxf4sul8YW6cA-UsCsM78sIOi477HaCVvW94Fizl2VPCDvB.9D33rsTYhFPB1vz059XYpnPHz1neIuEe-zi.ElxvyHVZX7hPZpqny3Wh1GIHKy15x.YUmwPQwepc3Mdad8NgFxNYIk04r4sHhCDFKiHcQQi-Iw1ukcanlXT5OZH5Iz8aW1xBSRtfNocOrCe4vZmV1AZMpMqPa0rNijrj-3HGJWq7CdyzgKolf4nN3LjbOCat.RLNSgGS079yLxEJ5homy5J-jhswBmkwlKKknz3lGd46BO.pDZqVILfF13njnnsu550COo4lz.lmr9DOuWIVIBeb8xuQRJqfwYO.WRHi4I-UJ-8dCPicngGAFyrzkJ7dKX-VIRVGstKE07VcjZZ-1XLsZaxiOF9jL-cu6bqZyW32mtRGYd0gtmcMGY-Pq7AF292e4St0d4BkkY8iZTBbKd.dflYfbgThmrg5YvUqDnz6PwtVs7cXG3SNYW8fVVd9dSh5XdAMVZLyzNnDKr2-OmgLyJVAVsz7vlGAPSbXSZiLCxCwsfPKkDJJJd1pCNKXexWDoeViVWYHxaqAOQXZK16DTloF5fc2WwxWT5dzBJwScPUhW.6q4mAZwL3TBv09ztVETJCGWaFg8kY2lE1fFZvIZTgLsyw7a-aLas4PBsGwnF.SJvGyCjsZsznU9x5Gq8RpmNLMXZtY4zvs7g88lngZNe8ZrPGfJcvFdsZRaNikWxBgqGhyddBHe6DqavvsEOnYp9IJwnTX3oaw3j6AeiwLcAbD9Sp3lwzVZrvUGUSJqFjTIW76.Ww3HeJEogBh8WGg9trg2OXjnSxhoDFeHwr27AtVH9BtdfjOUpV9qZJdm2qE0Sh0RnNEa4NcqVuGPdyUXAShVKjgK7huXFNZy0mAE8yHlmVdDBHfCTlGrlyjgtjKbOMEtmzDDtld4rFzG3tWSPs-7MSDxz2tYgeOMCb-qzC3rE5eEh5AcTsgbFBmcYd.LjI5yXv9O5ugUv2LZSFeFCMmNzwYZ1IstpE18Ibfqa2ltbQZj56rOSJAHp6IEnFrjljrz7xZunHMW0FlBWF2SE110Tt0Sofnutv2Mwjzh8hFqishjEm-di8WVZI9WATr1BAAEZgsCXy5u6uRdnoDCl.3DD6Z8Gp5OxGL4m4ovtXy4rXO-Z0Qu4nCNHIeTlQq.i9VeJ-AfeGrBLluqe1duaF95f1hNUwGeZKCFqP3j1e1qqLxCsbsO5UfSbdTuRY.sSciidTY-Vu4-H.p4DmElgFmDp.5-sQV1sWWDNaaPIPGOIE7XTYC2MeeQrawhrk94AppKJxvnegNSIEC-F.yp0wQd7Y.pai6KSV4rLfzNM-6MKnaGk9iljsTZngqeLNHIydh2-Q0Pfz6ErQzgWp5aWhhTjU4TAWcu6lfKVuLSRXnaowhcsx9DB7deLyNs.FVOx1K07vYkzwcrvqBbgJytcvqdaGaS5n-c3pj5ezRZ5gR2t.-cqBNuY1EvNelHiXmC.Au5x2FoD2ObRYqKkf5N.vsXWdNsZl-2vHW61H859zdMdEbJ7dsItaJJdFhHY3T9SvUH17MWeq1VtkKKQ6EnqCt0DnnSYUhgYqbVD-WBgDQj-564sDybz2f-xHCgfUSo83uNWubdBCr-cQikyFY.q6wyy5u07DGqJGMdlS9EhREDUZ1Ldb00l1pRY9J8gWkYcTk-sStLeUkvq13fn63yxshT6JHHnby3Y6DeNjITZmpJ-W6BjFunraxcmne67sk1tF7ZPSBhnJAL6sJmrw2x.68foHiG9vW6lUuvESCrDpGVQH3kDUngEeVwvqsYhoclDW6IlPVn2QD1KJJ.4mSDC5qxoAB8RwAqTuedy0c2xzBWEGaVQwGkWr11uulv2M0l6pa01cLJKxBvhbdYdbPvFZZ5sYIqz6K6XOSUpAQ4nlzfFP8k-icXuvuYlWhSl5Wo2zmrFMNRoUIMe6R7qD4YCQbn5dGevUY-TESkJOnZ4rvQLzh188R4kaLDyb1SW.xmLoeuMfjNbWN2LLjmHa36GQYEqMqWfrCbC1x-PRWEw0eVNmqNOFrpIQY20U5XbzvyhclJdoHMm.v-2YwDVGa-OlETHrtxx-Rwsvm9S6o-eu9ukknucfARt1TUeJn6eZ9WuuCZ-IqFwEJzB7BmL6CvWyCJFkeqUVvoMuHmZtXXmTY7LYqpoE1fHLfIMbtfzTzQeXOr6K5MsjzwUaszROpy9yUp8LwZ77iVeY7hs9mYQ.tiH4m-asSQG5HssKkbMoisKLwvHUr.nALH5i-5t9gcAec2sO5wiyupIkm5mxNMNBonuUMUq.NccklU4JeqNJSWI7y8niDp43U5H1lUpbwsFot59hEwDhOtGX81J-4a9y4fV.wtfdJN2rV2MRMrgxX..qWX231tphH9Oy-YNyshbd5B.AKBzEC1E3Nwit9-QrWFvMrSOKnBUpDfpRMe9boI-JP5TFXjqtppi6K3-x2V6qVYYiD9A0Lgyn-T.R07DR4363vd8lrd9v6gyfsrGeomMtnwzE6DQKI3cJwcxAAMHsYbSkqI-g1DFdI43RkpwoSLDWd1c9PK8573Y8hbigYmnC7b9WA.lNbpqNQEm8YPNJEgaArZ.XGt3mZrWB2hIqXDh993pglilE1bAK7YhwbRMWFzfjYlW30j6gvj-iPMxPwyWrLpb3XJJI8ljPNs33yej39b4bdoNsmwz97rxwWmTIrTNKa0l2lUgBkyHERug5DKlRR.7kf5bUQwvtEZAAB8GkUtLS5YZ0Oo6eht.95toiYnCGgGcfiWLma6-WHf-GKs0cfFx5FmNUKryyUG-68aVJz495KfOkyHlFHM9DEZEHVbGuz3mPA9pCnyJNXAcLsI-3YT9mGC9NMeEx.rt2PZmVT5jabpkL1Ln9UQllIslJP5Y8cM7bpmEG960neT-rCcG74Rn0avZaLZXw1H2AcVEfe62ZXs63FLHF-zm4eesHQgaGUNyzM.d.F2FWrEGRWvtwpe5i-q1fS87S4nSuPG-b0XlxJ65O6c1xC5ba8krUwPt3zuu1ed7h5GM4lRABWpK3T5b894qvWwa8XPXjIVanZb10ne8-z7PFmaSScVO1qSGvzLg.Pmdr1brYKTltBJ20Ijph9ZKwwK.IGpfX.0Xn5lOrlwrMFf9SDrX9JLJsYyPhMrZsox8JhZJG1FN7nijIy0H2RguJZX7vg5cuSOxi3dZEtA0HusAcbGM6-P8NAF1lh4YiZZKbPyJaaKD2q-KtOBoh.xWDFAT9krBdHkVeWZYjHLeaM1uCPwx1uF.iFpAfC0NuKcKhrJIm-QPzRTGjDLaMqvSuuhCY3RDLE75SmwlCoMeX4gO5tgcO6c7Wrw-FGC6pJMzixSLwRUkCdy52N5Dedse2iQo8qH0N8wV1leUC.T2mjWscV5-LoLy1.nr7LobAl2CQcMHbA8cUVqzHipczyxBu8DiwPh3dMSSoduTmxCkkzH97kw62gwMhNsaUv6ssQQwC7X4lmkZMPWdA5slIu49QXL2F3jYDA5IUYHX14puF-ZhNZe9LS17V30OKm3SGd6Zi0kvOK1JuJbWFjC7CwWuetbdnut1VhbBkw0B2VT8sBNIxezApqRpfjhvN4mvILcDvMuUq4l.plJI=',
    'x-tt-passport-csrf-token': '',
            })
            with opener.open(req, timeout=10) as resp:
                data = json.loads(resp.read())
            break
        except Exception as e:
            _log.error("qrlogin", f"get_qrcode intento {attempt + 1}/2 fallo: {e}")
            if attempt == 1:
                return None

    if data is None or data.get("message") != "success":
        raise RuntimeError(f"get_qrcode fallo: {data}")

    token = data["data"]["token"]
    index_url = data["data"]["qrcode_index_url"]

                    
    try:
        short_url = _shorten_url(opener, index_url, did)
    except Exception as e:
        _log.warn("qrlogin", f"no se pudo acortar URL ({e}), usando URL original")
        short_url = index_url

    _log.info("qrlogin", "escanea este QR con TikTok:\n")
    _print_qr(short_url)
    print()

    ms_token = _fetch_ms_token(did) or next((c.value for c in jar if c.name == "msToken"), "")

                
    status_shown = set()
    cookies = {}
    try:
        while not _stop_event.is_set():
            query = f"{_base_params(did)}&token={urllib.parse.quote(token)}"
            signed = _sign(query)
            url = f"https://web-sg.tiktok.com/passport/web/check_qrconnect/?{signed}"
            req = urllib.request.Request(url, headers={
                "User-Agent": _UA,
                'accept': 'application/json, text/javascript',
    'accept-language': 'es-US,es-419;q=0.9,es;q=0.8',
    'priority': 'u=1, i',
    'referer': 'https://www.tiktok.com/login/qrcode',
    'sec-ch-ua': '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'tt-ticket-guard-iteration-version': '0',
    'tt-ticket-guard-public-key': 'BMfZl+/keYLdE+lGmdH2V5xBmDxCWi6+lFeuJstXEoPl4z3HmiUGTI6FHz+FeeI6t3ECvg+mzHxgnYTCpeg6uFU=',
    'tt-ticket-guard-version': '2',
    'tt-ticket-guard-web-version': '1',
    'x-mssdk-info': '6RS5jcr8H1p2U88fAP6qdtyxugcCwojZasVZpsm8R6hfT.cuZpdWxgjWeBlYW1158N1b2XgdCeI-8wlueeFxhibS.bM6YzULZvif1N-OLWaIMDT.zHb2ACxf4sul8YW6cA-UsCsM78sIOi477HaCVvW94Fizl2VPCDvB.9D33rsTYhFPB1vz059XYpnPHz1neIuEe-zi.ElxvyHVZX7hPZpqny3Wh1GIHKy15x.YUmwPQwepc3Mdad8NgFxNYIk04r4sHhCDFKiHcQQi-Iw1ukcanlXT5OZH5Iz8aW1xBSRtfNocOrCe4vZmV1AZMpMqPa0rNijrj-3HGJWq7CdyzgKolf4nN3LjbOCat.RLNSgGS079yLxEJ5homy5J-jhswBmkwlKKknz3lGd46BO.pDZqVILfF13njnnsu550COo4lz.lmr9DOuWIVIBeb8xuQRJqfwYO.WRHi4I-UJ-8dCPicngGAFyrzkJ7dKX-VIRVGstKE07VcjZZ-1XLsZaxiOF9jL-cu6bqZyW32mtRGYd0gtmcMGY-Pq7AF292e4St0d4BkkY8iZTBbKd.dflYfbgThmrg5YvUqDnz6PwtVs7cXG3SNYW8fVVd9dSh5XdAMVZLyzNnDKr2-OmgLyJVAVsz7vlGAPSbXSZiLCxCwsfPKkDJJJd1pCNKXexWDoeViVWYHxaqAOQXZK16DTloF5fc2WwxWT5dzBJwScPUhW.6q4mAZwL3TBv09ztVETJCGWaFg8kY2lE1fFZvIZTgLsyw7a-aLas4PBsGwnF.SJvGyCjsZsznU9x5Gq8RpmNLMXZtY4zvs7g88lngZNe8ZrPGfJcvFdsZRaNikWxBgqGhyddBHe6DqavvsEOnYp9IJwnTX3oaw3j6AeiwLcAbD9Sp3lwzVZrvUGUSJqFjTIW76.Ww3HeJEogBh8WGg9trg2OXjnSxhoDFeHwr27AtVH9BtdfjOUpV9qZJdm2qE0Sh0RnNEa4NcqVuGPdyUXAShVKjgK7huXFNZy0mAE8yHlmVdDBHfCTlGrlyjgtjKbOMEtmzDDtld4rFzG3tWSPs-7MSDxz2tYgeOMCb-qzC3rE5eEh5AcTsgbFBmcYd.LjI5yXv9O5ugUv2LZSFeFCMmNzwYZ1IstpE18Ibfqa2ltbQZj56rOSJAHp6IEnFrjljrz7xZunHMW0FlBWF2SE110Tt0Sofnutv2Mwjzh8hFqishjEm-di8WVZI9WATr1BAAEZgsCXy5u6uRdnoDCl.3DD6Z8Gp5OxGL4m4ovtXy4rXO-Z0Qu4nCNHIeTlQq.i9VeJ-AfeGrBLluqe1duaF95f1hNUwGeZKCFqP3j1e1qqLxCsbsO5UfSbdTuRY.sSciidTY-Vu4-H.p4DmElgFmDp.5-sQV1sWWDNaaPIPGOIE7XTYC2MeeQrawhrk94AppKJxvnegNSIEC-F.yp0wQd7Y.pai6KSV4rLfzNM-6MKnaGk9iljsTZngqeLNHIydh2-Q0Pfz6ErQzgWp5aWhhTjU4TAWcu6lfKVuLSRXnaowhcsx9DB7deLyNs.FVOx1K07vYkzwcrvqBbgJytcvqdaGaS5n-c3pj5ezRZ5gR2t.-cqBNuY1EvNelHiXmC.Au5x2FoD2ObRYqKkf5N.vsXWdNsZl-2vHW61H859zdMdEbJ7dsItaJJdFhHY3T9SvUH17MWeq1VtkKKQ6EnqCt0DnnSYUhgYqbVD-WBgDQj-564sDybz2f-xHCgfUSo83uNWubdBCr-cQikyFY.q6wyy5u07DGqJGMdlS9EhREDUZ1Ldb00l1pRY9J8gWkYcTk-sStLeUkvq13fn63yxshT6JHHnby3Y6DeNjITZmpJ-W6BjFunraxcmne67sk1tF7ZPSBhnJAL6sJmrw2x.68foHiG9vW6lUuvESCrDpGVQH3kDUngEeVwvqsYhoclDW6IlPVn2QD1KJJ.4mSDC5qxoAB8RwAqTuedy0c2xzBWEGaVQwGkWr11uulv2M0l6pa01cLJKxBvhbdYdbPvFZZ5sYIqz6K6XOSUpAQ4nlzfFP8k-icXuvuYlWhSl5Wo2zmrFMNRoUIMe6R7qD4YCQbn5dGevUY-TESkJOnZ4rvQLzh188R4kaLDyb1SW.xmLoeuMfjNbWN2LLjmHa36GQYEqMqWfrCbC1x-PRWEw0eVNmqNOFrpIQY20U5XbzvyhclJdoHMm.v-2YwDVGa-OlETHrtxx-Rwsvm9S6o-eu9ukknucfARt1TUeJn6eZ9WuuCZ-IqFwEJzB7BmL6CvWyCJFkeqUVvoMuHmZtXXmTY7LYqpoE1fHLfIMbtfzTzQeXOr6K5MsjzwUaszROpy9yUp8LwZ77iVeY7hs9mYQ.tiH4m-asSQG5HssKkbMoisKLwvHUr.nALH5i-5t9gcAec2sO5wiyupIkm5mxNMNBonuUMUq.NccklU4JeqNJSWI7y8niDp43U5H1lUpbwsFot59hEwDhOtGX81J-4a9y4fV.wtfdJN2rV2MRMrgxX..qWX231tphH9Oy-YNyshbd5B.AKBzEC1E3Nwit9-QrWFvMrSOKnBUpDfpRMe9boI-JP5TFXjqtppi6K3-x2V6qVYYiD9A0Lgyn-T.R07DR4363vd8lrd9v6gyfsrGeomMtnwzE6DQKI3cJwcxAAMHsYbSkqI-g1DFdI43RkpwoSLDWd1c9PK8573Y8hbigYmnC7b9WA.lNbpqNQEm8YPNJEgaArZ.XGt3mZrWB2hIqXDh993pglilE1bAK7YhwbRMWFzfjYlW30j6gvj-iPMxPwyWrLpb3XJJI8ljPNs33yej39b4bdoNsmwz97rxwWmTIrTNKa0l2lUgBkyHERug5DKlRR.7kf5bUQwvtEZAAB8GkUtLS5YZ0Oo6eht.95toiYnCGgGcfiWLma6-WHf-GKs0cfFx5FmNUKryyUG-68aVJz495KfOkyHlFHM9DEZEHVbGuz3mPA9pCnyJNXAcLsI-3YT9mGC9NMeEx.rt2PZmVT5jabpkL1Ln9UQllIslJP5Y8cM7bpmEG960neT-rCcG74Rn0avZaLZXw1H2AcVEfe62ZXs63FLHF-zm4eesHQgaGUNyzM.d.F2FWrEGRWvtwpe5i-q1fS87S4nSuPG-b0XlxJ65O6c1xC5ba8krUwPt3zuu1ed7h5GM4lRABWpK3T5b894qvWwa8XPXjIVanZb10ne8-z7PFmaSScVO1qSGvzLg.Pmdr1brYKTltBJ20Ijph9ZKwwK.IGpfX.0Xn5lOrlwrMFf9SDrX9JLJsYyPhMrZsox8JhZJG1FN7nijIy0H2RguJZX7vg5cuSOxi3dZEtA0HusAcbGM6-P8NAF1lh4YiZZKbPyJaaKD2q-KtOBoh.xWDFAT9krBdHkVeWZYjHLeaM1uCPwx1uF.iFpAfC0NuKcKhrJIm-QPzRTGjDLaMqvSuuhCY3RDLE75SmwlCoMeX4gO5tgcO6c7Wrw-FGC6pJMzixSLwRUkCdy52N5Dedse2iQo8qH0N8wV1leUC.T2mjWscV5-LoLy1.nr7LobAl2CQcMHbA8cUVqzHipczyxBu8DiwPh3dMSSoduTmxCkkzH97kw62gwMhNsaUv6ssQQwC7X4lmkZMPWdA5slIu49QXL2F3jYDA5IUYHX14puF-ZhNZe9LS17V30OKm3SGd6Zi0kvOK1JuJbWFjC7CwWuetbdnut1VhbBkw0B2VT8sBNIxezApqRpfjhvN4mvILcDvMuUq4l.plJI=',
    'x-tt-passport-csrf-token': '',
                "Cookie":     f"msToken={ms_token}",
            })
            try:
                resp = urllib.request.urlopen(req, timeout=10)
                resp_body = resp.read()
                raw_headers = resp.headers
            except urllib.error.HTTPError as e:
                raw_headers = e.headers
                resp_body = e.read()
            except KeyboardInterrupt:
                raise
            except Exception as e:
                _log.error("qrlogin", f"error en check_qrconnect: {e}")
                time.sleep(2)
                continue

            for line in str(raw_headers).splitlines():
                if line.lower().startswith("set-cookie:"):
                    part = line[len("set-cookie:"):].strip().split(";")[0].strip()
                    if part.startswith("msToken=") and len(part) > len("msToken="):
                        ms_token = part[len("msToken="):]

            data = json.loads(resp_body)

            if data.get("message") != "success":
                err_code = data.get("data", {}).get("error_code", 0)
                if err_code == 2135:
                    passport_ticket = ""
                    for line in str(raw_headers).splitlines():
                        if "x-tt-verify-idv-decision-conf" in line.lower():
                            import json as _json2
                            try:
                                conf_str = line.split(":", 1)[1].strip()
                                conf = _json2.loads(conf_str)
                                passport_ticket = conf.get("passport_ticket", "")
                            except Exception:
                                pass
                    if not passport_ticket:
                        _log.error("qrlogin", "2FA requerida pero no se pudo obtener passport_ticket")
                        _stop_event.wait(3)
                        continue
                    _log.warn("qrlogin", "2FA requerida (verificación de identidad)")
                    ok = _handle_2fa(opener, passport_ticket)
                    if not ok:
                        return None
                    continue
                _log.error("qrlogin", f"{data.get('data', {}).get('description', data)}, reintentando...")
                _stop_event.wait(3)
                continue

            d = data["data"]
            status = d.get("status", "")

            if status not in status_shown:
                if status == "new":
                    _log.info("qrlogin", "esperando escaneo...")
                elif status == "scanned":
                    _log.ok("qrlogin", "escaneado - acepta en tu telefono...")
                elif status == "expired":
                    _log.warn("qrlogin", "QR expirado.")
                    return None
                status_shown.add(status)

            if status == "confirmed":
                for line in str(raw_headers).splitlines():
                    if line.lower().startswith("set-cookie:"):
                        cookie_part = line[len("set-cookie:"):].strip().split(";")[0].strip()
                        if "=" in cookie_part:
                            k, v = cookie_part.split("=", 1)
                            if v:
                                cookies[k.strip()] = v.strip()
                return cookies

            _stop_event.wait(2)
    except KeyboardInterrupt:
        _stop_event.set()
        _log.warn("qrlogin", "cancelado.")
        return None

    return None


if __name__ == "__main__":
    run()
