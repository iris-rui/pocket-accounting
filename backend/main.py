"""
口袋记账 AI — FastAPI 后端入口

所有金额以 Decimal 类型处理，杜绝浮点数精度问题。
路由已按模块拆分到 routers/ 目录。
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database import SessionLocal, init_db
from seed import seed_defaults
from security import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    RequestSizeLimitMiddleware,
)

# ---------- 路由模块 ----------
from routers.categories import router as categories_router
from routers.accounts import router as accounts_router
from routers.transactions import router as transactions_router
from routers.ai import router as ai_router
from routers.ai_advice import router as ai_advice_router
from routers.budgets import router as budgets_router
from routers.stats import router as stats_router

# ---------- 日志 ----------
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pocket-accounting")


# ---------- 生命周期 ----------
@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_defaults(db)
    finally:
        db.close()
    yield


# ---------- 创建应用 ----------
app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description="AI 驱动的毒舌记账助手 🦘",
    lifespan=lifespan,
)

# ---------- 中间件（按优先级从外到内排列）----------
if settings.SECURITY_HEADERS_ENABLED:
    app.add_middleware(SecurityHeadersMiddleware)
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# ---------- 注册路由 ----------
app.include_router(categories_router)
app.include_router(accounts_router)
app.include_router(transactions_router)
app.include_router(ai_router)
app.include_router(ai_advice_router)
app.include_router(budgets_router)
app.include_router(stats_router)


# ---------- 全局异常处理 ----------
@app.exception_handler(Exception)
async def global_exception_handler(_request: Request, exc: Exception):
    logger.error(
        f"未处理异常: {type(exc).__name__} | "
        f"路径: {_request.method} {_request.url.path} | "
        f"客户端: {_request.client.host if _request.client else 'unknown'}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"message": "服务器内部错误，请稍后重试", "success": False},
    )


# ---------- 健康检查 ----------
@app.get("/api/health", tags=["系统"])
def health_check():
    return {"status": "ok", "time": datetime.now().isoformat()}


# ---------- 入口 ----------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
