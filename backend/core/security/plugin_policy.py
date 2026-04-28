"""
Plugin permission policy helpers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


@dataclass(frozen=True)
class PluginPolicyDecision:
    allowed: bool
    missing_permissions: List[str]
    risk_level: str = "low"


def _is_permission_granted(grants: Dict[str, Any], permission: str) -> bool:
    if grants.get("*") is True:
        return True
    if grants.get(permission) is True:
        return True
    if "." not in permission:
        return False
    parts = permission.split(".")
    for i in range(len(parts) - 1, 0, -1):
        prefix = ".".join(parts[:i]) + ".*"
        if grants.get(prefix) is True:
            return True
    return False


def evaluate_plugin_permissions(
    required_permissions: Iterable[str] | None,
    grants: Dict[str, Any] | None,
) -> PluginPolicyDecision:
    required = [str(p).strip() for p in (required_permissions or []) if str(p).strip()]
    if not required:
        return PluginPolicyDecision(allowed=True, missing_permissions=[], risk_level="low")

    granted = grants or {}
    missing = [perm for perm in required if not _is_permission_granted(granted, perm)]
    risk_level = "low"
    if any(perm.startswith(("net.", "file.write", "shell.", "python.")) for perm in required):
        risk_level = "high"
    elif any(perm.startswith(("file.", "system.")) for perm in required):
        risk_level = "medium"
    return PluginPolicyDecision(
        allowed=(len(missing) == 0),
        missing_permissions=missing,
        risk_level=risk_level,
    )
