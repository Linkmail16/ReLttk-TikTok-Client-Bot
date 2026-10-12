import urllib.parse

_UA_DEFAULT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36"
)

_SIGN_OPTS = dict(
    envcode=1, canvas=411533585, ubcode=8,
    version='5.3.2', scm_version='2.0.0.561',
)

_req_counter = {"total": 0, "enc": 0}


def _next_req_counts() -> tuple[int, int]:
    _req_counter["total"] += 1
    _req_counter["enc"] += 1
    return _req_counter["total"], _req_counter["enc"]


def _get_signers():
    from ..signers.xdynosaur import pack as _a
    from ..signers.xgnarly import pack as _b
    return _a, _b


def _get_bogus():
    from ..signers.bogus import Signer
    return Signer


def sign_full(params: str, body: str = "", ua: str = "") -> tuple[str, str]:
    _a, _b = _get_signers()
    _ua = ua or _UA_DEFAULT
    total_reqs, enc_reqs = _next_req_counts()
    opts = dict(_SIGN_OPTS, total_reqs=total_reqs, enc_reqs=enc_reqs)
    dyno = _a(qs=params, body=body, ua=_ua, **opts)
    gnarly_qs = params + "&msToken=&X-Dynosaur=" + urllib.parse.quote(dyno, safe='') + "&X-Bogus=1"
    gnarly = _b(qs=gnarly_qs, body=body, ua=_ua, **opts)
    signed = params + "&msToken=&X-Dynosaur=" + urllib.parse.quote(dyno, safe='') + "&X-Bogus=1"
    return signed, gnarly


def sign_bogus(params: str, ua: str = "") -> str:
    return _get_bogus().sign(params, ua or _UA_DEFAULT)


def sign_gnarly(query_string: str, body: str = "", ua: str = "") -> str:
    _, _b = _get_signers()
    total_reqs, enc_reqs = _next_req_counts()
    opts = dict(_SIGN_OPTS, total_reqs=total_reqs, enc_reqs=enc_reqs)
    return _b(qs=query_string, body=body, ua=ua or _UA_DEFAULT, **opts)


def sign_ws(stub_hex: str, bogus_index: int = 1) -> str:
    return _get_bogus().sign_ws(stub_hex, bogus_index)
