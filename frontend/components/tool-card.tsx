'use client';

/** 工具调用 / 节点事件卡片：展示脱敏参数摘要 */
import { agentIcon, agentLabel } from './icons';

export default function ToolCard({
  agent,
  tool,
  argsDigest,
  at,
  kind = 'tool',
}: {
  agent: string;
  tool: string;
  argsDigest?: string;
  at?: string;
  /** tool = 工具调用；start = 节点启动 */
  kind?: 'tool' | 'start';
}) {
  const Icon = agentIcon(agent);
  const isStart = kind === 'start';

  return (
    <div
      className={`group flex items-start gap-2.5 px-3 py-2.5 rounded-xl border transition-colors animate-slide-in-right ${
        isStart
          ? 'border-ink-100 bg-surface-50'
          : 'border-tint-line bg-tint/50 hover:bg-tint'
      }`}
    >
      <span
        className={`mt-[1px] w-6 h-6 shrink-0 rounded-lg flex items-center justify-center ${
          isStart ? 'bg-surface-0 text-ink-400 border border-ink-100' : 'bg-surface-0 text-tint-fg border border-tint-line'
        }`}
      >
        <Icon size={13} />
      </span>

      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[14.5px] font-medium text-ink-800">{agentLabel(agent)}</span>
          {isStart ? (
            <span className="text-[12.5px] text-ink-400">节点启动</span>
          ) : (
            <code className="font-mono text-[12.5px] px-1.5 py-[1px] rounded bg-surface-0 text-tint-fg border border-tint-line">
              {tool}
            </code>
          )}
        </span>

        {argsDigest && (
          <span className="block mt-1 text-[13px] text-ink-400 leading-snug break-words">
            {argsDigest}
          </span>
        )}
      </span>

      {at && (
        <span className="shrink-0 text-[12.5px] text-ink-300 tabular-nums mt-[2px]">{at}</span>
      )}
    </div>
  );
}
