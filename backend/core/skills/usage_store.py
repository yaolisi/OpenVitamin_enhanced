"""
技能使用频次持久化：用于按用户/会话推荐技能。

存储：backend/data/skill_usage.json（与 platform.db 同目录）
结构：{ "version": 1, "users": { "<user_id>": { "<skill_id>": <count> } } }
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Tuple

from log import logger

from core.knowledge.knowledge_base_store import KnowledgeBaseStore

_FILE_LOCK = threading.RLock()
_STORE_PATH: Path | None = None


def _default_path() -> Path:
    return KnowledgeBaseStore.default_db_path().parent / "skill_usage.json"


def get_skill_usage_path() -> Path:
    global _STORE_PATH
    if _STORE_PATH is None:
        _STORE_PATH = _default_path()
    return _STORE_PATH


def set_skill_usage_path_for_tests(path: Path | None) -> None:
    """测试注入路径。"""
    global _STORE_PATH
    _STORE_PATH = path


def _read_raw(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {"version": 1, "users": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"[SkillUsageStore] Corrupt {path}, resetting: {e}")
        return {"version": 1, "users": {}}


def _write_raw(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record_skill_use(user_id: str, skill_id: str) -> None:
    """将一次成功使用记入该用户的计数。"""
    if not user_id or not skill_id:
        return
    path = get_skill_usage_path()
    with _FILE_LOCK:
        data = _read_raw(path)
        users = data.setdefault("users", {})
        bucket: Dict[str, int] = users.setdefault(user_id, {})
        bucket[skill_id] = int(bucket.get(skill_id, 0)) + 1
        _write_raw(path, data)


def get_user_skill_counts(user_id: str) -> Dict[str, int]:
    """返回该用户各技能使用次数（降序不保证，仅原始映射）。"""
    if not user_id:
        return {}
    path = get_skill_usage_path()
    with _FILE_LOCK:
        data = _read_raw(path)
        users = data.get("users") or {}
        raw = users.get(user_id) or {}
        return {k: int(v) for k, v in raw.items() if int(v) > 0}


def top_skills_for_user(user_id: str, limit: int = 20) -> List[Tuple[str, int]]:
    """按使用次数降序返回 (skill_id, count)。"""
    counts = get_user_skill_counts(user_id)
    if not counts:
        return []
    items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return items[: max(0, limit)]

