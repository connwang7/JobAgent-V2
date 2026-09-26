"""全局配置：Pydantic Settings，环境变量注入，不落盘明文。"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# 显式锚定到 backend/.env，而不是依赖"当前工作目录"。
# 否则从仓库根目录启动时会去读 <root>/.env——那里若残留一份 v1 的旧文件，
# Serper / LLM 等配置会静默消失（现象是"功能开关点了没反应"），极难排查。
BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # 应用
    app_name: str = "JobAgent"
    debug: bool = False
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    cors_origins: str = '["http://localhost:3000"]'

    # 数据库
    database_url: str = "mysql+asyncmy://jobagent:jobagent@localhost:3306/jobagent?charset=utf8mb4"
    checkpoint_db_url: str = ""  # 留空复用 database_url

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "job_jd"

    # 对象存储
    storage_backend: Literal["minio", "local"] = "local"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "jobagent"
    minio_secure: bool = False
    local_storage_dir: str = "./.storage"

    # LLM（OpenAI 兼容协议，默认 DashScope）
    llm_api_key: str = ""
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model_planner: str = "qwen-turbo"
    llm_model_worker: str = "qwen-plus"
    llm_model_writer: str = "qwen-max"
    llm_model_critic: str = "deepseek-chat"
    # 「深度思考」开关启用时，worker/synthesizer 换用的推理模型
    llm_model_thinking: str = "deepseek-reasoner"
    critic_api_key: str = ""
    critic_base_url: str = ""

    # Embedding
    tei_endpoint: str = ""
    embedding_model: str = "text-embedding-v3"
    # 专用 Embedding 凭证（推荐单独配置）：不配置时仅当对话 LLM 的 endpoint 是 DashScope
    # 才复用其凭证；第三方中转站大多没有向量模型，盲目复用会每条消息都报 404
    embedding_api_key: str = ""
    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    # 期望的输出维度；0 表示不传该参数（部分服务如 SiliconFlow 的 BGE 模型传了会 400）。
    # 仅用于校验与文档提示，真实维度以服务返回为准（BGE-large-zh-v1.5 = 1024）
    embedding_dimensions: int = 0

    # 工具
    serper_api_key: str = ""
    firecrawl_api_key: str = ""

    # 安全
    kms_master_key: str = "0" * 64  # 32 字节 hex

    @property
    def cors_origin_list(self) -> list[str]:
        import json
        try:
            return json.loads(self.cors_origins)
        except Exception:
            return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
