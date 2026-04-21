"""
Execution Kernel Heavy Integration Test Runner
重型集成用例入口：显式开启 heavy 测试。
"""

import asyncio
import os
import sys

from test_execution_kernel_integration import main as run_main


if __name__ == "__main__":
    os.environ["EXEC_KERNEL_RUN_HEAVY_INTEGRATION"] = "1"
    success = asyncio.run(run_main())
    sys.exit(0 if success else 1)
