"""Celery 应用：backend 与 worker 共用同一镜像（代码一致，入口不同）。"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "jobagent",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.tasks.parse_resume",
        "app.workers.tasks.embed_jobs",
        "app.workers.tasks.deep_research",
        "app.workers.tasks.render_letter",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,          # 单任务硬上限 30min
    task_soft_time_limit=1500,
    broker_connection_retry_on_startup=True,

    # ---- 生产者侧快速失败 ------------------------------------------------
    # broker 连不上时，kombu 默认会反复重连（实测要 ~108s 才抛错）。
    # 如果这个 publish 发生在 async 端点里，会把整个事件循环冻住。
    # 现在：客户端里先做 TCP 预检（见 dispatch.py），这里再把重试彻底关掉做双保险。
    task_publish_retry=False,
    broker_connection_max_retries=0,
    broker_connection_timeout=2,
    broker_transport_options={
        "socket_connect_timeout": 2,
        "socket_timeout": 2,
        "retry_on_timeout": False,
        "max_retries": 0,
    },
    result_backend_transport_options={
        "socket_connect_timeout": 2,
        "socket_timeout": 2,
        "retry_on_timeout": False,
        "max_retries": 0,
    },
)
