#!/usr/bin/env bash
# Live + UAT 探针（TestClient，无需启动 uvicorn）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/backend${PYTHONPATH:+:$PYTHONPATH}"
PHASE="${ENTERPRISE_SUITE_PHASE:-all}"
JSON_OUT="${ENTERPRISE_SUITE_JSON_OUT:-}"
ARGS=(python3 backend/scripts/enterprise_suite_acceptance_gate.py --phase "$PHASE" --inprocess --require-live)
if [[ -n "$JSON_OUT" ]]; then
  ARGS+=(--json-out "$JSON_OUT")
fi
echo "[enterprise-suite-inprocess] phase=$PHASE"
"${ARGS[@]}"
