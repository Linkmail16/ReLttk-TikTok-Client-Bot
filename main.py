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
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        from importlib import import_module
        run = import_module(f"{_PKG}.qrlogin").run
        run()
    else:
        LttkClient = _pkg.LttkClient

        async def main():
            bot = LttkClient()
            await bot.run()

        asyncio.run(main())
