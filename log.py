import os
import sys

_NO_COLOR = not sys.stdout.isatty() or os.environ.get("NO_COLOR")

_R  = "" if _NO_COLOR else "\033[0m"
_DIM = "" if _NO_COLOR else "\033[2m"

_CYAN    = "" if _NO_COLOR else "\033[96m"
_GREEN   = "" if _NO_COLOR else "\033[92m"
_YELLOW  = "" if _NO_COLOR else "\033[93m"
_RED     = "" if _NO_COLOR else "\033[91m"
_BLUE    = "" if _NO_COLOR else "\033[94m"
_MAGENTA = "" if _NO_COLOR else "\033[95m"
_WHITE   = "" if _NO_COLOR else "\033[97m"
_BOLD    = "" if _NO_COLOR else "\033[1m"


def _tag(color: str, tag: str) -> str:
    return f"{color}{_BOLD}[{tag}]{_R}"


def info(tag: str, msg: str):
    print(f"{_tag(_CYAN, tag)} {msg}")

def ok(tag: str, msg: str):
    print(f"{_tag(_GREEN, tag)} {_GREEN}{msg}{_R}")

def warn(tag: str, msg: str):
    print(f"{_tag(_YELLOW, tag)} {_YELLOW}{msg}{_R}")

def error(tag: str, msg: str):
    print(f"{_tag(_RED, tag)} {_RED}{msg}{_R}")

def msg(ts: str, sender: str, group: str, text: str):
    ts_part     = f"{_DIM}[{ts}]{_R}"
    group_part  = f" {_MAGENTA}[{group}]{_R}" if group else ""
    sender_part = f"{_BOLD}{sender}{_R}"
    print(f"{ts_part}{group_part} {sender_part}: {text}")

def reaction(ts: str, sender: str, action: str, emoji: str):
    ts_part = f"{_DIM}[{ts}]{_R}"
    print(f"{ts_part} {_BOLD}{sender}{_R}: [{_YELLOW}{action} {emoji}{_R}]")

def plugin(tag: str, action: str, name: str):
    color = _GREEN if action == "nuevo" else _RED if action == "eliminado" else _YELLOW
    print(f"{_tag(_CYAN, tag)} plugin {color}{action}{_R}: {name}")
