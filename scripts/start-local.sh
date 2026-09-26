#!/usr/bin/env bash
# JobAgent v2 本地一键启动（不依赖 Docker）
# 用法：
#   ./scripts/start-local.sh            # 启动后端 + 前端
#   ./scripts/start-local.sh backend    # 只启动后端
#   ./scripts/start-local.sh frontend   # 只启动前端
#
# 若依赖装在别的解释器里，先指定：export PYTHON_BIN=/path/to/python
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 选择解释器：PYTHON_BIN > backend/.venv > 常见托管环境 > 系统 python
pick_python() {
  if [ -n "${PYTHON_BIN:-}" ]; then echo "$PYTHON_BIN"; return; fi
  for c in \
    "$ROOT/backend/.venv/Scripts/python.exe" \
    "$ROOT/backend/.venv/bin/python" \
    "$HOME/.workbuddy/binaries/python/envs/jobagent/Scripts/python.exe" \
    "$(command -v python3 || true)" \
    "$(command -v python || true)"
  do
    [ -n "$c" ] && [ -x "$c" ] && { echo "$c"; return; }
  done
  echo "python"
}
PY="$(pick_python)"

# 依赖自检：缺依赖直接给出安装命令，避免起一半报错
if [ "$1" != "frontend" ]; then
  if ! "$PY" -c "import fastapi, langgraph, sqlalchemy" >/dev/null 2>&1; then
    echo "✗ 当前解释器缺少后端依赖：$PY"
    echo "  安装：cd backend && $PY -m pip install -e ."
    echo "  或指定已装依赖的解释器：PYTHON_BIN=/path/to/python $0"
    exit 1
  fi
fi

start_backend() {
  echo "==> 后端 http://127.0.0.1:8000  (接口文档 /api/docs)"
  cd "$ROOT/backend"
  PYTHONPATH=. exec "$PY" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
}

start_frontend() {
  echo "==> 前端 http://localhost:3000"
  cd "$ROOT/frontend"
  [ -d node_modules ] || { echo "首次运行，安装前端依赖…"; npm install; }
  exec npm run dev
}

case "${1:-all}" in
  backend)  start_backend ;;
  frontend) start_frontend ;;
  all)
    ( start_backend > "$ROOT/.backend.log" 2>&1 & )
    echo "后端日志: $ROOT/.backend.log"
    sleep 3
    start_frontend
    ;;
  *) echo "用法: $0 [all|backend|frontend]"; exit 1 ;;
esac
