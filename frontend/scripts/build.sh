#!/usr/bin/env sh
# 生产构建（带 .next/trace 屏蔽）。
#
# 为什么不是直接 `next build`：
#   本机上 `next build` 会在 `open('.next/trace', 'a')` 上稳定抛
#   `uncaughtException [Error: EPERM: operation not permitted, open '...\.next\trace']`
#   （错误没有调用栈 → 来自 worker 进程；关掉沙箱、改目录名、反复重试都无效）。
#   `.next/trace` 只是性能追踪产物，不参与产物、不影响 `next start`，
#   所以用 `scripts/next-no-trace.cjs` 把指向它的 createWriteStream 换成空流。
#   注意必须走 NODE_OPTIONS：Next 的构建 worker 是子进程，只有环境变量能传下去
#   （`node -r` 只作用于主进程，worker 仍会失败）。
#
# 用法：sh scripts/build.sh        （等价于 next build，只是绕开这个 EPERM）
set -e
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJ"
NODE_OPTIONS="$NODE_OPTIONS --require $PROJ/scripts/next-no-trace.cjs" \
  exec node "$PROJ/node_modules/next/dist/bin/next" build "$@"
