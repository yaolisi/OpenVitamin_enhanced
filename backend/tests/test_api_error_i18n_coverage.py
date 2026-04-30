from __future__ import annotations

import re
from pathlib import Path

from api.error_i18n import _ERROR_MESSAGES


def test_error_i18n_covers_core_api_error_codes() -> None:
    root = Path(__file__).resolve().parents[1]
    targets = [
        root / "api" / "agents.py",
        root / "api" / "tools.py",
        root / "api" / "events.py",
        root / "api" / "rag_trace.py",
        root / "api" / "skills.py",
        root / "api" / "mcp.py",
        root / "api" / "knowledge.py",
        root / "api" / "workflows.py",
        root / "api" / "chat.py",
    ]
    code_re = re.compile(r'code\\s*=\\s*"([a-z0-9_]+)"')

    found_codes: set[str] = set()
    for path in targets:
        found_codes.update(code_re.findall(path.read_text(encoding="utf-8")))

    missing = sorted(code for code in found_codes if code not in _ERROR_MESSAGES)
    assert missing == []

