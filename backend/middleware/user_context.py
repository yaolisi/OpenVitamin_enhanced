"""
User Context Middleware
用于在每个请求中统一注入 user_id 到 request.state
"""
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send
from fastapi import Request as FastAPIRequest
from core.utils.user_context import get_user_id, DEFAULT_USER_ID


class UserContextMiddleware:
    """
    用户上下文中间件（纯 ASGI，避免 BaseHTTPMiddleware 嵌套过深导致流式响应兼容性问题）

    在每个请求的 request.state 中注入 user_id，
    后续可以通过 request.state.user_id 或 get_user_id(request) 获取
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        request.state.user_id = get_user_id(request)

        await self.app(scope, receive, send)


def get_current_user(request: FastAPIRequest) -> str:
    """
    获取当前用户 ID（FastAPI 依赖注入）
    
    从 request.state.user_id 获取，与 UserContextMiddleware 注入的值一致
    如果没有则回退到 DEFAULT_USER_ID
    """
    return getattr(request.state, "user_id", None) or DEFAULT_USER_ID
