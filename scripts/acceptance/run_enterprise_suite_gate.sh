#!/usr/bin/env bash
# 开箱企业套件自动对标门禁（Phase 0–2 自动 P0 探针）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/backend${PYTHONPATH:+:$PYTHONPATH}"
PHASE="${ENTERPRISE_SUITE_PHASE:-phase0}"
JSON_OUT="${ENTERPRISE_SUITE_JSON_OUT:-}"
ARGS=(python3 backend/scripts/enterprise_suite_acceptance_gate.py --phase "$PHASE")
if [[ -n "$JSON_OUT" ]]; then
  ARGS+=(--json-out "$JSON_OUT")
fi
echo "[enterprise-suite-gate] phase=$PHASE"
"${ARGS[@]}"
