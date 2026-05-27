#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/backend"
cd "${BACKEND_DIR}"

if [[ ! -f main.py ]]; then
  echo >&2 "run-backend.sh: missing main.py (${BACKEND_DIR})"
  exit 1
fi

# 本机 / 内网多用户：本地账号登录与注册（可在 backend/.env 或环境中覆盖）
export LOCAL_AUTH_ENABLED="${LOCAL_AUTH_ENABLED:-true}"
export LOCAL_AUTH_ALLOW_REGISTRATION="${LOCAL_AUTH_ALLOW_REGISTRATION:-true}"
# 设为 true 时，未登录无法调用 API（本地 Cookie 或 OIDC / API Key 均可）
# export AUTH_REQUIRE_LOGIN=true

# 检查是否安装了 conda
if command -v conda &> /dev/null; then
    echo "检测到 Conda，正在使用环境 'ai-inference-platform' 启动..."
    # 使用 conda run 可以绕过 shell init 问题，直接在指定环境下运行命令
    # 使用 exec 让当前进程被真实后端进程替换，便于 run-all.sh 通过 PID/进程组正确停止
    exec conda run -n ai-inference-platform --no-capture-output python3 main.py
else
    echo "未检测到 Conda，尝试使用系统 python3 启动..."
    if ! command -v python3 &> /dev/null; then
        echo "错误: 未找到 python3" >&2
        exit 1
    fi
    exec python3 main.py
fi
