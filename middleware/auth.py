"""
鉴权中间件

提供 API 鉴权功能。
"""

import os
from typing import Optional

from fastapi import Request, HTTPException


# 配置
GATEWAY_SECRET = os.getenv("GATEWAY_SECRET", "")

# 公开端点（不需要鉴权）
PUBLIC_ENDPOINTS = {
    "/",
    "/docs",
    "/openapi.json",
    "/redoc",
}

# OAuth 端点
OAUTH_ENDPOINTS = {
    "/.well-known/oauth-authorization-server",
    "/oauth/register",
    "/oauth/authorize",
    "/oauth/token",
}


async def verify_auth(request: Request) -> Optional[str]:
    """
    验证请求鉴权

    参数：
        request: FastAPI 请求对象

    返回：
        验证通过返回 token/key，未设置密钥返回 None

    异常：
        验证失败抛出 HTTPException 401
    """
    # 未设置密钥，跳过鉴权
    if not GATEWAY_SECRET:
        return None

    path = request.url.path

    # 公开端点，跳过鉴权
    if path in PUBLIC_ENDPOINTS:
        return None

    # OAuth 端点，跳过鉴权
    if any(path.startswith(ep) for ep in OAUTH_ENDPOINTS):
        return None

    # 健康检查，跳过鉴权
    if path == "/":
        return None

    # 检查 X-Gateway-Key header
    gateway_key = request.headers.get("X-Gateway-Key")
    if gateway_key == GATEWAY_SECRET:
        return gateway_key

    # 检查 Authorization header (Bearer token)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if token == GATEWAY_SECRET:
            return token

    # 验证失败
    raise HTTPException(
        status_code=401,
        detail={
            "error": {
                "message": "Unauthorized: Invalid or missing credentials",
                "type": "authentication_error",
            }
        },
    )
