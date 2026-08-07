import urllib.request
import json

_BASE = "http://72.61.78.8:5050"


def _post(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{_BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def sign_bogus(params: str, ua: str = "") -> str:
    body: dict = {"params": params}
    if ua:
        body["ua"] = ua
    return _post("/bogus", body)["result"]


def sign_gnarly(query_string: str, body: str = "", ua: str = "") -> str:
    payload: dict = {"query_string": query_string, "body": body}
    if ua:
        payload["ua"] = ua
    return _post("/gnarly", payload)["result"]


def sign_ws(stub_hex: str, bogus_index: int = 1) -> str:
    return _post("/bogus_ws", {"stub_hex": stub_hex, "bogus_index": bogus_index})["result"]


def sign_full(params: str, body: str = "", ua: str = "") -> tuple[str, str]:
    payload: dict = {"params": params, "body": body}
    if ua:
        payload["ua"] = ua
    resp = _post("/sign", payload)
    return resp["params"], resp["x_gnarly"]
