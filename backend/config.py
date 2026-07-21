"""
应用配置文件

所有敏感配置通过 .env 文件加载，不硬编码在代码中。
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 从本文件所在目录加载 .env
_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)


def _require(key: str) -> str:
    """获取必需的环境变量，未设置时抛出明确错误"""
    value = os.getenv(key)
    if not value:
        raise ValueError(
            f"缺少必需的环境变量: {key}\n"
            f"请复制 .env.example 为 .env 并填入真实配置\n"
            f"配置文件位置: {_env_path}"
        )
    return value


class Settings:
    # ==================== 数据库配置 ====================
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = _require("DB_PASSWORD")
    DB_NAME: str = os.getenv("DB_NAME", "pocket_accounting")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    # ==================== AI 服务配置（全部从 .env 读取，无硬编码默认值）====================
    AI_API_KEY: str = _require("AI_API_KEY")
    AI_API_BASE: str = _require("AI_API_BASE")
    AI_MODEL: str = _require("AI_MODEL")

    # ==================== 服务器配置 ====================
    APP_TITLE: str = "口袋记账 AI"
    APP_VERSION: str = "1.0.0"

    # CORS 白名单（逗号分隔），默认仅允许本地前端
    CORS_ORIGINS: list = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if origin.strip()
    ]

    # ==================== 安全配置 ====================
    # 速率限制：每分钟最大请求数（单个 IP）
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))

    # 是否启用安全响应头
    SECURITY_HEADERS_ENABLED: bool = os.getenv("SECURITY_HEADERS_ENABLED", "true").lower() == "true"

    # 是否启用速率限制
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"


settings = Settings()
