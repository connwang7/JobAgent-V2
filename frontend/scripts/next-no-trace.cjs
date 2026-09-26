/**
 * 构建期 workaround：屏蔽 Next.js 的 `.next/trace` 写入。
 *
 * 背景：在本机环境里 `next build` 会在 `open('.next/trace', 'a')` 上稳定报
 *   uncaughtException [Error: EPERM: operation not permitted, open '...\.next\trace']
 * 且该错误没有调用栈（说明来自 worker 进程），与沙箱无关（关掉沙箱同样报）。
 * 试过：改 `.next` 目录名、反复重试、`dangerouslyDisableSandbox` —— 都在同一处失败。
 *
 * `.next/trace` 只是 Next 的性能追踪（span）输出，仅供 `next build --profile` /
 * trace 上传使用，**不参与产物**，也不影响 `next start` 运行。这里把指向该路径的
 * createWriteStream 换成一个空的可写流，其余 fs 行为一行不改。
 *
 * 用法：NODE_OPTIONS="... --require /tmp/next-no-trace.cjs" next build
 */
'use strict';

const fs = require('fs');
const path = require('path');

function isNextTraceFile(p) {
  if (typeof p !== 'string') return false;
  const abs = path.resolve(p);
  if (path.basename(abs) !== 'trace') return false;
  const parent = path.basename(path.dirname(abs));
  return parent === '.next' || parent.startsWith('.next');
}

const origCreateWriteStream = fs.createWriteStream;
const { Writable } = require('stream');

function makeNullStream() {
  return new Writable({
    write(_chunk, _enc, cb) {
      cb();
    },
  });
}

fs.createWriteStream = function createWriteStream(filePath, options) {
  if (isNextTraceFile(filePath)) {
    return makeNullStream();
  }
  return origCreateWriteStream.call(fs, filePath, options);
};

fs.promises.createWriteStream = fs.createWriteStream;
