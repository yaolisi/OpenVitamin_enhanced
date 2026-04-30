from __future__ import annotations

from typing import Dict


_ERROR_MESSAGES: Dict[str, Dict[str, str]] = {
    "http_400": {
        "en": "bad request",
        "zh": "请求不合法",
    },
    "invalid_payload": {
        "en": "payload validation failed",
        "zh": "请求参数校验失败",
    },
    "internal_server_error": {
        "en": "Internal server error",
        "zh": "服务器内部错误",
    },
    "workflow_not_found": {
        "en": "workflow not found",
        "zh": "工作流不存在",
    },
    "workflow_access_denied": {
        "en": "workflow access denied",
        "zh": "无权访问该工作流",
    },
    "workflow_execution_not_found": {
        "en": "workflow execution not found",
        "zh": "工作流执行记录不存在",
    },
    "chat_async_stream_not_supported": {
        "en": "async mode does not support stream=true",
        "zh": "异步模式暂不支持 stream=true",
    },
    "chat_async_job_not_found": {
        "en": "request not found or expired",
        "zh": "请求不存在或已过期",
    },
    "stream_not_found": {
        "en": "stream not found or expired",
        "zh": "流不存在或已过期",
    },
    "stream_resume_disabled": {
        "en": "stream resume is disabled",
        "zh": "断点续传未开启",
    },
    "knowledge_upload_filename_required": {
        "en": "Filename is required",
        "zh": "文件名不能为空",
    },
    "mcp_server_not_found": {
        "en": "MCP server not found",
        "zh": "MCP 服务不存在",
    },
    "skill_create_failed": {
        "en": "Failed to create skill",
        "zh": "创建技能失败",
    },
    "skill_update_failed": {
        "en": "Failed to update skill",
        "zh": "更新技能失败",
    },
}


def _resolve_locale(accept_language: str | None) -> str:
    if not accept_language:
        return "en"
    normalized = accept_language.lower()
    if normalized.startswith("zh") or ",zh" in normalized:
        return "zh"
    return "en"


def localize_error_message(*, code: str, default_message: str, accept_language: str | None) -> str:
    locale = _resolve_locale(accept_language)
    table = _ERROR_MESSAGES.get(code)
    if not table:
        return default_message
    return table.get(locale, default_message)

