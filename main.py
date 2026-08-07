import asyncio
import sys
import os

_HERE   = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
_PKG    = os.path.basename(_HERE)

if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

_pkg = __import__(_PKG)


def _list_sessions():
    from importlib import import_module
    return import_module(f"{_PKG}.qrlogin").list_sessions()


async def _run_all():
    from importlib import import_module
    log    = import_module(f"{_PKG}.log")
    qrlogin = import_module(f"{_PKG}.qrlogin")
    LttkClient = _pkg.LttkClient

    bots: dict[str, asyncio.Task] = {}
    loop = asyncio.get_event_loop()

    def _start(username: str):
        if username in bots and not bots[username].done():
            return
        log.info("lttk", f"arrancando sesion: {username}")
        bot = LttkClient(username=username)
        bots[username] = asyncio.create_task(bot.run())

    async def _do_qr():
        log.info("lttk", "iniciando login por QR...")
        try:
            await loop.run_in_executor(None, qrlogin.run)
        except (KeyboardInterrupt, asyncio.CancelledError):
            qrlogin._stop_event.set()
            raise
        except Exception as e:
            log.error("lttk", f"error en QR login: {e}")
            return
        for s in _list_sessions():
            _start(s)

    sessions = _list_sessions()
    if not sessions:
        await _do_qr()
    else:
        for s in sessions:
            _start(s)

    async def _console():
        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            cmd = line.strip().lower()
            if cmd == "add":
                await _do_qr()
            elif cmd == "list":
                if bots:
                    for name, task in bots.items():
                        status = "activo" if not task.done() else f"detenido"
                        log.info("lttk", f"  {name}: {status}")
                else:
                    log.info("lttk", "no hay sesiones activas")
            elif cmd == "stop":
                for task in bots.values():
                    task.cancel()
                break
            elif cmd:
                log.info("lttk", "comandos: add | list | stop")

    async def _watchdog():
        while True:
            await asyncio.sleep(10)
            for name, task in list(bots.items()):
                if task.done():
                    exc = task.exception() if not task.cancelled() else None
                    if exc:
                        log.warn("lttk", f"sesion {name} terminó con error ({exc}), reiniciando...")
                    _start(name)

    await asyncio.gather(_console(), _watchdog(), *bots.values(), return_exceptions=True)


if __name__ == "__main__":
    args = sys.argv[1:]

    if args and args[0] == "cookies":
        path = args[1] if len(args) > 1 else "cookies.json"
        from importlib import import_module
        import json
        qrlogin = import_module(f"{_PKG}.qrlogin")
        log = import_module(f"{_PKG}.log")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                cookies = {c["name"]: c["value"] for c in data if c.get("value")}
            else:
                cookies = data
            if not cookies.get("sessionid"):
                raise ValueError("no se encontro sessionid en el archivo")
        except Exception as e:
            log.error("cookies", str(e))
            sys.exit(1)
        qrlogin._write_cookies(cookies)
        log.ok("cookies", "importado, reinicia el bot para aplicar")

    elif args and args[0] == "browser":
        browser = args[1] if len(args) > 1 else "chrome"
        from importlib import import_module
        browsercookies = import_module(f"{_PKG}.browsercookies")
        qrlogin = import_module(f"{_PKG}.qrlogin")
        log = import_module(f"{_PKG}.log")
        try:
            cookies = browsercookies.get_tiktok_cookies(browser)
        except Exception as e:
            log.error("browser", str(e))
            sys.exit(1)
        qrlogin._write_cookies(cookies)
        log.ok("browser", f"cookies de {browser} importadas, reinicia el bot para aplicar")

    else:
        try:
            asyncio.run(_run_all())
        except KeyboardInterrupt:
            from importlib import import_module
            import_module(f"{_PKG}.qrlogin")._stop_event.set()
