'use client';

/** Planner 任务 DAG 可视化：展示各节点 pending / running / done 状态 */
import {
  agentIcon, agentLabel, IconCheck, IconLoader, IconTarget,
} from './icons';

export interface PlanStep {
  id: string;
  agent: string;
  description: string;
  depends_on: string[];
}

export default function PlanView({
  steps,
  completed,
  running,
  failed = false,
}: {
  steps: PlanStep[];
  completed: string[];
  /** 当前正在执行的节点名（agent_start 的 node） */
  running?: string;
  failed?: boolean;
}) {
  if (!steps.length) return null;

  const statusOf = (id: string, agent: string): 'done' | 'running' | 'pending' => {
    if (completed.includes(id)) return 'done';
    if (running && agent === running) return 'running';
    return 'pending';
  };

  const doneCount = steps.filter((s) => statusOf(s.id, s.agent) === 'done').length;
  const pct = Math.round((doneCount / steps.length) * 100);

  return (
    <div className="card overflow-hidden">
      <div className="px-4 py-3 border-b border-ink-100 flex items-center gap-2.5">
        <span className="w-7 h-7 rounded-lg bg-tint text-tint-fg flex items-center justify-center shrink-0">
          <IconTarget size={15} />
        </span>
        <span className="section-title">执行计划</span>
        <span className="badge badge-info tabular-nums">
          {doneCount}/{steps.length}
        </span>
        <span className="ml-auto text-[13px] text-ink-400 tabular-nums">{pct}%</span>
      </div>

      {/* 进度条 */}
      <div className="h-1 bg-surface-100">
        <div
          className={`h-full rounded-r-full transition-all duration-500 ease-smooth ${
            failed
              ? 'bg-rose-400'
              : 'bg-gradient-to-r from-brand-500 to-accent-500'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>

      <ol className="p-2 space-y-0.5">
        {steps.map((s, i) => {
          const st = statusOf(s.id, s.agent);
          const Icon = agentIcon(s.agent);
          return (
            <li
              key={s.id}
              className="flex items-start gap-2.5 px-2 py-2 rounded-lg hover:bg-surface-50 transition-colors"
            >
              {/* 状态圆点 */}
              <span
                className={`mt-[3px] w-[18px] h-[18px] shrink-0 rounded-full flex items-center justify-center text-[12.5px] font-semibold transition-colors ${
                  st === 'done'
                    ? 'bg-emerald-500 text-white'
                    : st === 'running'
                    ? 'bg-tint text-tint-fg ring-2 ring-brand-500/25'
                    : 'bg-surface-100 text-ink-400'
                }`}
              >
                {st === 'done' ? (
                  <IconCheck size={11} />
                ) : st === 'running' ? (
                  <IconLoader size={11} />
                ) : (
                  i + 1
                )}
              </span>

              <span
                className={`mt-[2px] w-[18px] h-[18px] shrink-0 flex items-center justify-center ${
                  st === 'pending' ? 'text-ink-300' : 'text-tint-fg'
                }`}
              >
                <Icon size={15} />
              </span>

              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2">
                  <span
                    className={`text-[15px] font-medium ${
                      st === 'pending' ? 'text-ink-500' : 'text-ink-800'
                    }`}
                  >
                    {agentLabel(s.agent)}
                  </span>
                  {st === 'running' && (
                    <span className="badge badge-info animate-pulse-soft">执行中</span>
                  )}
                  {s.depends_on?.length > 0 && (
                    <span className="ml-auto text-[12.5px] text-ink-300 shrink-0">
                      依赖 {s.depends_on.join(' · ')}
                    </span>
                  )}
                </span>
                {s.description && (
                  <span className="block text-[13.5px] text-ink-400 leading-snug mt-0.5">
                    {s.description}
                  </span>
                )}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
