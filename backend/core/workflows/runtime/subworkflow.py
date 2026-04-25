"""
Sub-workflow runtime helpers.

Provide deterministic mapping/validation utilities for sub-workflow node execution.
"""

from __future__ import annotations

from typing import Any, Dict

from execution_kernel.engine.context import GraphContext


def _read_path_from_payload(payload: Any, path: str) -> Any:
    current = payload
    for key in [p for p in str(path or "").split(".") if p]:
        if isinstance(current, dict) and key in current:
            current = current[key]
            continue
        raise ValueError(f"path not found: {path}")
    return current


def resolve_mapping_value(rule: Any, context: GraphContext, node_input: Dict[str, Any]) -> Any:
    """
    Resolve a mapping rule into concrete value.

    Supported forms:
    - {"type":"const","value":...}
    - {"type":"expression","value":"${input.foo}"}
    - {"type":"path","from":"input.foo"} / "global.foo" / "nodes.a.output.bar"
    - string expression "${...}"
    - other literals (returned as-is)
    """
    if isinstance(rule, dict):
        rtype = str(rule.get("type") or "").strip().lower()
        if rtype == "const":
            return rule.get("value")
        if rtype in {"expression", "expr"}:
            expr = str(rule.get("value") or "").strip()
            return context.resolve(expr) if expr else None
        if rtype == "path":
            source = str(rule.get("from") or "").strip()
            return resolve_mapping_path(source, context, node_input)
        # Backward compatible: raw {"value": ...}
        if "value" in rule and len(rule.keys()) == 1:
            return rule.get("value")
        return rule

    if isinstance(rule, str):
        text = rule.strip()
        if text.startswith("${") and text.endswith("}"):
            return context.resolve(text)
        if text.startswith("input.") or text.startswith("global.") or text.startswith("nodes."):
            return resolve_mapping_path(text, context, node_input)
        return rule

    return rule


def resolve_mapping_path(source: str, context: GraphContext, node_input: Dict[str, Any]) -> Any:
    source = str(source or "").strip()
    if not source:
        return None

    if source == "input":
        return dict(node_input or {})
    if source.startswith("input."):
        return _read_path_from_payload(node_input or {}, source[len("input."):])
    if source.startswith("global.") or source.startswith("nodes."):
        return context.resolve("${" + source + "}")
    raise ValueError(f"unsupported mapping source: {source}")


def build_child_input(
    input_mapping: Dict[str, Any],
    context: GraphContext,
    node_input: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(input_mapping, dict) or not input_mapping:
        return dict(node_input or {})
    output: Dict[str, Any] = {}
    for target_key, rule in input_mapping.items():
        output[str(target_key)] = resolve_mapping_value(rule, context, node_input)
    return output


def apply_output_mapping(
    child_output: Dict[str, Any],
    output_mapping: Dict[str, Any],
) -> Dict[str, Any]:
    child = dict(child_output or {})
    if not isinstance(output_mapping, dict) or not output_mapping:
        return child
    mapped: Dict[str, Any] = {}
    for parent_key, source in output_mapping.items():
        if isinstance(source, str):
            src = source.strip()
            if src.startswith("output."):
                src = src[len("output."):]
            mapped[str(parent_key)] = _read_path_from_payload(child, src) if src else None
        else:
            mapped[str(parent_key)] = source
    return mapped
