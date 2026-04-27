#!/usr/bin/env python3
"""
连续批处理配置快照与回滚工具。

子命令：
1) snapshot: 拉取当前 /api/system/config 并保存快照
2) rollback: 从快照恢复 continuousBatch* 配置
"""
from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any

try:
    from scripts._http_utils import build_request_headers, http_get_json, http_post_json_with_status
except Exception:
    from _http_utils import build_request_headers, http_get_json, http_post_json_with_status  # type: ignore[no-redef]


CB_KEYS = (
    "continuousBatchEnabled",
    "continuousBatchWaitMs",
    "continuousBatchMaxSize",
)


def _now_str() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.localtime())


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _fetch_config(base_url: str, timeout: float, headers: dict[str, str]) -> dict[str, Any]:
    return http_get_json(f"{base_url.rstrip('/')}/api/system/config", timeout=timeout, request_headers=headers)


def _extract_cb_payload(config_resp: dict[str, Any]) -> dict[str, Any]:
    settings = config_resp.get("settings", {}) if isinstance(config_resp, dict) else {}
    if not isinstance(settings, dict):
        settings = {}
    payload: dict[str, Any] = {}
    for k in CB_KEYS:
        if k in settings:
            payload[k] = settings.get(k)
    return payload


def _save_json(path: str, data: dict[str, Any]) -> None:
    _ensure_parent(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2))


def _load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("快照文件格式错误：根节点必须是 object")
    return data


def _apply_config(base_url: str, payload: dict[str, Any], timeout: float, headers: dict[str, str]) -> tuple[int, dict[str, Any]]:
    code, body, _ = http_post_json_with_status(
        f"{base_url.rstrip('/')}/api/system/config",
        payload,
        timeout=timeout,
        request_headers=headers,
    )
    if not isinstance(body, dict):
        body = {"raw": body}
    return int(code), body


def cmd_snapshot(args: argparse.Namespace) -> int:
    headers = build_request_headers(api_key=args.api_key, api_key_header=args.api_key_header)
    config_resp = _fetch_config(args.base_url, args.timeout_seconds, headers)
    cb_payload = _extract_cb_payload(config_resp)
    snap = {
        "created_at_epoch": time.time(),
        "created_at_local": _now_str(),
        "base_url": args.base_url,
        "continuous_batch_payload": cb_payload,
        "raw_system_config": config_resp,
    }
    output = args.output_file
    if not output:
        output = f"backend/data/benchmarks/grid/rollback-snapshot-{_now_str()}.json"
    output_abs = os.path.abspath(output)
    _save_json(output_abs, snap)
    print(f"[rollback] snapshot saved: {output_abs}")
    print(json.dumps(cb_payload, ensure_ascii=False))
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    headers = build_request_headers(api_key=args.api_key, api_key_header=args.api_key_header)
    snap = _load_json(os.path.abspath(args.snapshot_file))
    payload = snap.get("continuous_batch_payload")
    if not isinstance(payload, dict) or not payload:
        raise ValueError("快照中缺少 continuous_batch_payload")

    # 只回滚连续批处理相关键，避免影响其他系统配置
    rollback_payload = {k: payload.get(k) for k in CB_KEYS if k in payload}
    if not rollback_payload:
        raise ValueError("快照里没有可回滚的 continuousBatch* 键")

    code, body = _apply_config(args.base_url, rollback_payload, args.timeout_seconds, headers)
    print(f"[rollback] apply status={code}")
    print(json.dumps(body, ensure_ascii=False))
    if code < 200 or code >= 300:
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="连续批处理配置快照与回滚")
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--timeout-seconds", type=float, default=20.0)
    p.add_argument("--api-key", default="")
    p.add_argument("--api-key-header", default="X-Api-Key")

    sub = p.add_subparsers(dest="command", required=True)

    p_snap = sub.add_parser("snapshot", help="保存当前 continuousBatch 配置快照")
    p_snap.add_argument(
        "--output-file",
        default="",
        help="快照输出路径；为空时自动生成到 backend/data/benchmarks/grid/",
    )

    p_rb = sub.add_parser("rollback", help="使用快照回滚 continuousBatch 配置")
    p_rb.add_argument("--snapshot-file", required=True, help="snapshot 生成的快照文件路径")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "snapshot":
        return cmd_snapshot(args)
    if args.command == "rollback":
        return cmd_rollback(args)
    parser.error(f"unsupported command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
