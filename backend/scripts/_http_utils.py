from __future__ import annotations

import json
import time
from typing import Any
from urllib import error, request


def build_request_headers(api_key: str, api_key_header: str = "X-Api-Key") -> dict[str, str]:
    headers: dict[str, str] = {}
    key = str(api_key or "").strip()
    if key:
        headers[str(api_key_header or "X-Api-Key").strip()] = key
    return headers


def _with_headers(req: request.Request, request_headers: dict[str, str] | None) -> request.Request:
    for k, v in (request_headers or {}).items():
        req.add_header(k, v)
    return req


def http_get_json(
    url: str,
    timeout: float = 20.0,
    request_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    req = _with_headers(request.Request(url, method="GET"), request_headers)
    with request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    data = json.loads(raw.decode("utf-8", errors="replace") or "{}")
    return data if isinstance(data, dict) else {}


def http_post_json(
    url: str,
    payload: dict[str, Any],
    timeout: float = 30.0,
    request_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    req = _with_headers(req, request_headers)
    with request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    data = json.loads(raw.decode("utf-8", errors="replace") or "{}")
    return data if isinstance(data, dict) else {}


def http_post_json_with_status(
    url: str,
    payload: dict[str, Any],
    timeout: float = 30.0,
    request_headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any], float]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    req = _with_headers(req, request_headers)
    started = time.perf_counter()
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            code = int(getattr(resp, "status", 200))
    except error.HTTPError as exc:
        code = int(exc.code or 500)
        raw = exc.read() or b"{}"
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    try:
        parsed = json.loads(raw.decode("utf-8", errors="replace") or "{}")
        if not isinstance(parsed, dict):
            parsed = {"raw": parsed}
    except Exception:
        parsed = {"raw": raw.decode("utf-8", errors="replace")}
    return code, parsed, elapsed_ms
