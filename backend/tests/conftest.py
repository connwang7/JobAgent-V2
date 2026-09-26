"""测试环境：把 cwd 指向 backend，避免依赖缺失时导入失败影响核心逻辑单测。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 单测不连接外部服务
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("STORAGE_BACKEND", "local")
