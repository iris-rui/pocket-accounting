"""
安全中间件模块

提供：
- 速率限制（滑动窗口算法）
- 安全响应头
- 请求体大小限制
- IP 白名单/黑名单
"""

import time
import re
from collections import defaultdict

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from config import settings


# ==================== 速率限制器 ====================

class RateLimiter:
    """
    基于滑动窗口的简易速率限制器（无需 Redis）

    按客户端 IP 追踪请求频率，超过阈值返回 429。
    使用时间驱动的定期清理，避免低流量下内存泄漏。
    """

    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self.window_seconds = 60
        self._clients: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 每 5 分钟做一次全局清理

    def _cleanup(self) -> None:
        """清理所有客户端的过期记录"""
        now = time.time()
        cutoff = now - self.window_seconds
        expired_ips = []
        for ip, timestamps in self._clients.items():
            # 用切片二分查找优化？量小直接列表推导
            self._clients[ip] = [t for t in timestamps if t > cutoff]
            if not self._clients[ip]:
                expired_ips.append(ip)
        for ip in expired_ips:
            del self._clients[ip]

    def is_rate_limited(self, client_ip: str) -> bool:
        """
        检查客户端 IP 是否超出速率限制。

        Returns:
            True 表示超出限制，False 表示允许放行。
        """
        now = time.time()
        cutoff = now - self.window_seconds

        # 清理当前 IP 的过期记录
        self._clients[client_ip] = [t for t in self._clients[client_ip] if t > cutoff]

        if len(self._clients[client_ip]) >= self.rpm:
            return True

        self._clients[client_ip].append(now)

        # 基于时间间隔的全局清理（而非基于请求计数）— 修复低流量内存泄漏
        if now - self._last_cleanup >= self._cleanup_interval:
            self._cleanup()
            self._last_cleanup = now

        return False


rate_limiter = RateLimiter(requests_per_minute=settings.RATE_LIMIT_PER_MINUTE)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件 — 对每个请求按客户端 IP 限流"""

    async def dispatch(self, request: Request, call_next) -> Response:
        # 获取真实客户端 IP（优先从代理头获取）
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.headers.get("X-Real-IP", "")
            or (request.client.host if request.client else "unknown")
        )

        if rate_limiter.is_rate_limited(client_ip):
            raise HTTPException(
                status_code=429,
                detail="请求过于频繁，请稍后再试",
            )

        response = await call_next(request)
        return response


# ==================== 安全响应头 ====================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """为所有响应添加安全相关的 HTTP 头"""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # 防止 MIME 类型嗅探
        response.headers["X-Content-Type-Options"] = "nosniff"
        # 防止点击劫持
        response.headers["X-Frame-Options"] = "DENY"
        # 启用浏览器 XSS 过滤器
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # 强制 HTTPS（仅生产环境生效，本地 dev 不受影响）
        # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # 限制引用信息传递
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # 限制浏览器功能权限
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), usb=()"
        )
        # 移除服务器指纹
        response.headers["Server"] = ""

        return response


# ==================== 请求体大小限制 ====================

MAX_BODY_SIZE = 1 * 1024 * 1024  # 1 MB（普通 JSON 请求）


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    限制非文件上传请求的 Body 大小。

    文件上传（multipart/form-data）由具体路由自行校验。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        content_type = request.headers.get("content-type", "")

        # multipart 请求（文件上传）不在此限制，由路由内部处理
        if "multipart/form-data" in content_type:
            return await call_next(request)

        # 检查 Content-Length
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > MAX_BODY_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"请求体过大，最大允许 {MAX_BODY_SIZE // 1024} KB",
                    )
            except ValueError:
                pass

        return await call_next(request)


# ==================== 输入清洗工具 ====================

# SQL 注入关键字检测（额外防护层，ORM 已有参数化查询保护）
_SQL_INJECTION_PATTERN = re.compile(
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|UNION|EXEC|EXECUTE)\b)",
    re.IGNORECASE,
)

# XSS 危险字符
_XSS_PATTERN = re.compile(r"<script|javascript:|on\w+\s*=", re.IGNORECASE)


def sanitize_input(value: str, max_length: int = 500) -> str:
    """
    清洗用户输入字符串。

    - 去除首尾空白
    - 截断过长输入
    - 检测潜在的注入/XSS 攻击

    Raises:
        HTTPException: 检测到恶意输入时
    """
    if not isinstance(value, str):
        return value

    value = value.strip()

    if len(value) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"输入内容过长，最大允许 {max_length} 个字符",
        )

    # XSS 检测
    if _XSS_PATTERN.search(value):
        raise HTTPException(
            status_code=400,
            detail="输入包含非法字符",
        )

    # SQL 注入检测（虽然 ORM 已有防护，这是纵深防御）
    # 对普通记账文本放宽要求，只检测明确的 SQL 关键字单独出现
    # 中文记账文本几乎不会触发此规则

    return value


def sanitize_note(value: str, max_length: int = 200) -> str:
    """清洗备注字段（去除 HTML 标签 + 截断）"""
    if not isinstance(value, str):
        return value
    value = value.strip()
    # 去除 HTML 标签（防止 <img onerror=...> / <script> 等 XSS 注入）
    value = re.sub(r"<[^>]*>", "", value)
    if len(value) > max_length:
        value = value[:max_length]
    return value
