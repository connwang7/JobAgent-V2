'use client';

/**
 * 思考过程折叠块（对标 DeepSeek / R1 交互）。
 *
 * 生命周期：
 *   1. 收到首个 `thinking` 事件 → 展开、显示「思考中…（n 秒）」并自动滚到底；
 *   2. 收到 `thinking_done`（或首个 token 到达）→ 冻结计时并自动折叠为
 *      「已深度思考（用时 n 秒）」；
 *   3. 用户可随时手动展开/折叠；若思考期间用户手动折叠，则不再自动展开。
 *
 * 耗时优先用前端实测的秒数（更贴近用户感知），后端 `elapsed_ms` 作为兜底。
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { IconBrain, IconChevronDown, IconClock } from './icons';

export default function ThinkingBlock({
  text,
  done,
  elapsedMs,
}: {
  text: string;
  done: boolean;
  elapsedMs?: number;
}) {
  const startedAt = useRef<number>(Date.now());
  const [frozenSec, setFrozenSec] = useState<number | null>(null);
  const [tick, setTick] = useState(0);
  const [open, setOpen] = useState(true);
  const bodyRef = useRef<HTMLDivElement>(null);

  // done 那一刻冻结耗时，之后标题不再跳动。
  // 优先用调用方传入的 elapsedMs（历史消息重挂载时它就是准确值），否则用前端实测。
  useEffect(() => {
    if (!done || frozenSec !== null) return;
    const fromCaller = elapsedMs && elapsedMs > 0
      ? Math.max(1, Math.round(elapsedMs / 1000))
      : 0;
    const measured = Math.max(0, Math.round((Date.now() - startedAt.current) / 1000));
    setFrozenSec(fromCaller || measured || 1);
  }, [done, elapsedMs, frozenSec]);

  // 思考中：每 200ms 刷新一次秒数
  useEffect(() => {
    if (done) return;
    const t = window.setInterval(() => setTick((n) => n + 1), 200);
    return () => window.clearInterval(t);
  }, [done]);

  // 思考中：自动吸附到底部（阅读最新的推理内容）
  useEffect(() => {
    if (done || !open) return;
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [text, done, open, tick]);

  // 结束时自动折叠
  useEffect(() => {
    if (done) setOpen(false);
  }, [done]);

  const liveSec = useMemo(
    () => Math.max(0, Math.round((Date.now() - startedAt.current) / 1000)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [tick, done],
  );
  // 历史消息首帧 frozenSec 还没算出来时，直接用传入的 elapsedMs，避免闪一下「0 秒」
  const secs =
    frozenSec ??
    (done && elapsedMs && elapsedMs > 0
      ? Math.max(1, Math.round(elapsedMs / 1000))
      : liveSec);

  return (
    <div
      className={`rounded-xl border transition-colors duration-200 mb-2.5 overflow-hidden ${
        done ? 'border-ink-200/80 bg-surface-100' : 'border-tint-line bg-tint/70'
      }`}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left group"
        aria-expanded={open}
      >
        <span
          className={`shrink-0 ${done ? 'text-ink-400' : 'text-tint-fg animate-breathe'}`}
        >
          <IconBrain size={16} />
        </span>

        <span
          className={`text-[14.5px] font-medium ${
            done ? 'text-ink-500' : 'thinking-sheen'
          }`}
        >
          {done ? '已深度思考' : '模型正在思考'}
        </span>

        {!done && (
          <span className="flex items-end gap-[3px] h-3 mb-[3px]">
            <i className="w-1 h-1 rounded-full bg-brand-400 animate-bounce-dot" />
            <i
              className="w-1 h-1 rounded-full bg-brand-400 animate-bounce-dot"
              style={{ animationDelay: '0.15s' }}
            />
            <i
              className="w-1 h-1 rounded-full bg-brand-400 animate-bounce-dot"
              style={{ animationDelay: '0.3s' }}
            />
          </span>
        )}

        <span className="inline-flex items-center gap-1 text-[13.5px] text-ink-400 tabular-nums">
          <IconClock size={12} />
          {secs} 秒
        </span>

        <span
          className={`ml-auto shrink-0 text-ink-400 transition-transform duration-200 ${
            open ? 'rotate-180' : ''
          }`}
        >
          <IconChevronDown size={15} />
        </span>
      </button>

      {open && (
        <div className="px-3 pb-3 animate-slide-down">
          <div
            ref={bodyRef}
            className="thinking-text max-h-72 overflow-y-auto pl-3 border-l-2 border-tint-line/80"
          >
            {text || '正在推理…'}
            {!done && <span className="caret" />}
          </div>
          {!done && (
            <div className="mt-2 flex items-center gap-1.5 text-[13px] text-ink-400">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse-soft" />
              模型正在推演，正式回答会紧接着流式输出
            </div>
          )}
        </div>
      )}
    </div>
  );
}
