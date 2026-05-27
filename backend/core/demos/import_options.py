"""一键导入选项。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from core.demos.platform_bundle_import import ProgressCallback


@dataclass
class ImportRunOptions:
    publish_workflows: bool = False
    wait_document_index: bool = True
    conflict_strategy: str = "skip"
    run_publish_gate: bool = True
    on_progress: Optional[ProgressCallback] = None
