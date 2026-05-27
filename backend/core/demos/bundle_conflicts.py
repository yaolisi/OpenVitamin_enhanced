"""Bundle 导入冲突检测与策略。"""
from __future__ import annotations

from typing import Any, Literal, Optional

from core.agent_runtime.definition import get_agent_registry
from core.skills.store import get_skill_store

ConflictStrategy = Literal["skip", "duplicate"]


def detect_import_conflicts(
    bundle: dict[str, Any],
    *,
    tenant_id: str,
    user_id: str = "default",
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    skill_store = get_skill_store()
    for spec in bundle.get("skills") or []:
        if not isinstance(spec, dict):
            continue
        sid = str(spec.get("skill_id") or "").strip()
        if sid and skill_store.get(sid):
            conflicts.append(
                {
                    "kind": "skill",
                    "key": sid,
                    "bundle_key": spec.get("bundle_key"),
                    "message": f"Skill already exists: {sid}",
                }
            )
    agent_registry = get_agent_registry()
    existing_names = {a.name.lower() for a in agent_registry.list_agents()}
    for spec in bundle.get("agents") or []:
        if not isinstance(spec, dict):
            continue
        name = str(spec.get("name") or "").strip().lower()
        if name and name in existing_names:
            conflicts.append(
                {
                    "kind": "agent",
                    "key": name,
                    "bundle_key": spec.get("bundle_key"),
                    "message": f"Agent name already exists: {spec.get('name')}",
                }
            )
    return conflicts


def apply_skill_conflict_strategy(
    spec: dict[str, Any],
    *,
    strategy: ConflictStrategy,
    id_map: dict[str, str],
) -> Optional[str]:
    """返回已有 skill id（skip）或 None（继续创建）。"""
    from core.skills.store import get_skill_store

    store = get_skill_store()
    desired = str(spec.get("skill_id") or "").strip()
    bkey = str(spec.get("bundle_key") or "")
    if strategy == "skip" and desired and store.get(desired):
        id_map[bkey] = desired
        return desired
    if strategy == "duplicate" and desired:
        spec = dict(spec)
        spec.pop("skill_id", None)
    return None
