#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TARGET_DIR="frontend/src"
BASELINE_FILE="scripts/i18n-hardcoded-baseline.txt"
UPDATE_BASELINE="${1:-}"
if [[ ! -d "$TARGET_DIR" ]]; then
  echo >&2 "check-frontend-i18n-hardcoded.sh: missing ${TARGET_DIR}"
  exit 1
fi

echo "[i18n-scan] checking frontend hardcoded UI strings..."

TEMPLATE_TEXT_PATTERN='>\s*[^<{]*[\x{4E00}-\x{9FFF}][^<{]*<'
ATTRIBUTE_TEXT_PATTERN='(?:title|aria-label|placeholder)=["'"'"'][^"'"'"']*[\x{4E00}-\x{9FFF}][^"'"'"']*["'"'"']'

TMP_CURRENT="$(mktemp)"
trap 'rm -f "$TMP_CURRENT"' EXIT

rg --pcre2 --glob '!frontend/src/i18n/locales/**' --glob '*.vue' -n "$TEMPLATE_TEXT_PATTERN|$ATTRIBUTE_TEXT_PATTERN" "$TARGET_DIR" \
  | awk -F: '{print $1 ":" $2}' \
  | sort -u > "$TMP_CURRENT"

if [[ "$UPDATE_BASELINE" == "--update-baseline" ]]; then
  cp "$TMP_CURRENT" "$BASELINE_FILE"
  echo "[i18n-scan] baseline updated: $BASELINE_FILE"
  exit 0
fi

if [[ ! -f "$BASELINE_FILE" ]]; then
  echo >&2 "[i18n-scan] baseline missing: $BASELINE_FILE"
  echo >&2 "[i18n-scan] run: bash scripts/check-frontend-i18n-hardcoded.sh --update-baseline"
  exit 2
fi

TMP_NEW="$(mktemp)"
trap 'rm -f "$TMP_CURRENT" "$TMP_NEW"' EXIT
comm -13 "$BASELINE_FILE" "$TMP_CURRENT" > "$TMP_NEW"

if [[ -s "$TMP_NEW" ]]; then
  echo >&2 "[i18n-scan] found new hardcoded UI strings:"
  while IFS= read -r item; do
    echo >&2 "  - $item"
  done < "$TMP_NEW"
  echo >&2 "[i18n-scan] if this is intentional, update baseline with --update-baseline."
  exit 2
fi

echo "[i18n-scan] OK"
