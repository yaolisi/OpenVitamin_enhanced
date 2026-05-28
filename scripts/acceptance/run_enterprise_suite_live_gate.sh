#!/usr/bin/env bash
# 对已运行网关执行 Live 探针（需 ENTERPRISE_SUITE_LIVE_URL 或默认 127.0.0.1:8000）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/backend${PYTHONPATH:+:$PYTHONPATH}"
BASE="${ENTERPRISE_SUITE_LIVE_URL:-http://127.0.0.1:8000}"
PHASE="${ENTERPRISE_SUITE_PHASE:-all}"
JSON_OUT="${ENTERPRISE_SUITE_JSON_OUT:-}"
ARGS=(python3 backend/scripts/enterprise_suite_acceptance_gate.py --phase "$PHASE" --live --live-base-url "$BASE" --require-live)
if [[ -n "$JSON_OUT" ]]; then
  ARGS+=(--json-out "$JSON_OUT")
fi
echo "[enterprise-suite-live] base=$BASE phase=$PHASE (includes UAT live probes)"
"${ARGS[@]}"
