import asyncio
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
_PKG = os.path.basename(_HERE)

if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

_pkg = __import__(_PKG)

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
        LttkClient = _pkg.LttkClient
        async def _main():
            bot = LttkClient()
            await bot.run()
        asyncio.run(_main())
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
        log.ok("browser", f"cookies de {browser} importadas, ejecuta sin argumentos para iniciar el bot")
    else:
        LttkClient = _pkg.LttkClient

        async def main():
            bot = LttkClient()
            await bot.run()

        asyncio.run(main())
