'use client';

import { api } from '@/lib/api';
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { IconAlert, IconBulb, IconCheck, IconLoader, IconMail, IconX } from './icons';

const SCORE_LABEL: Record<string, string> = {
  relevance: '岗位相关',
  relevance_score: '岗位相关',
  clarity: '表达清晰',
  clarity_score: '表达清晰',
  professionalism: '专业度',
  professionalism_score: '专业度',
  personalization: '针对性',
  personalization_score: '针对性',
  overall: '综合',
  overall_score: '综合',
};

/** 评分可能是 0-1 或 0-10，统一换算成百分比宽度与展示值 */
function normalize(v: any): { pct: number; text: string } {
  const n = Number(v);
  if (!Number.isFinite(n)) return { pct: 0, text: '—' };
  const ratio = n > 1 ? n / 10 : n;
  const pct = Math.max(0, Math.min(100, Math.round(ratio * 100)));
  return { pct, text: n > 1 ? n.toFixed(1) : ratio.toFixed(2) };
}

function scoreColor(pct: number): string {
  if (pct >= 80) return 'from-emerald-400 to-emerald-500';
  if (pct >= 60) return 'from-brand-400 to-brand-500';
  if (pct >= 40) return 'from-amber-400 to-amber-500';
  return 'from-rose-400 to-rose-500';
}

/** HITL 中断确认卡：展示求职信全文 + Critic 评分，用户确认后才落盘 docx */
export default function ConfirmCard({
  payload,
  onResolved,
}: {
  payload: any;
  onResolved: (approved: boolean) => void;
}) {
  const [busy, setBusy] = useState<null | 'approve' | 'reject'>(null);
  const [err, setErr] = useState('');

  const {
    run_id,
    cover_letter,
    critic_scores = {},
    critic_suggestions = [],
    revision_count = 0,
  } = payload || {};

  const scores = Object.entries(critic_scores || {});

  async function decide(approved: boolean) {
    if (!run_id) return;
    setBusy(approved ? 'approve' : 'reject');
    setErr('');
    try {
      await api.approveRun(run_id, approved);
      onResolved(approved);
    } catch (e: any) {
      setErr(e?.message || '操作失败，请重试');
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="card top-accent overflow-hidden animate-fade-up border-tint-line/70 shadow-pop">
      {/* 头部 */}
      <div className="px-5 pt-4 pb-3 flex items-center gap-3 border-b border-ink-100">
        <span className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-accent-500 text-white flex items-center justify-center shadow-glow shrink-0">
          <IconMail size={17} />
        </span>
        <div className="min-w-0">
          <div className="text-[16px] font-semibold text-ink-900">求职信待你确认</div>
          <div className="text-[13.5px] text-ink-400">
            质检通过后才会生成 Word 文档并落盘
            {revision_count > 0 && ` · 已修订 ${revision_count} 轮`}
          </div>
        </div>
        <span className="ml-auto badge badge-info shrink-0">
          <IconAlert size={11} />
          需要人工介入
        </span>
      </div>

      <div className="p-5 space-y-4">
        {/* 质检评分 */}
        {scores.length > 0 && (
          <div>
            <div className="eyebrow mb-2">Critic 质检评分</div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
              {scores.map(([k, v]) => {
                const { pct, text } = normalize(v);
                return (
                  <div key={k} className="rounded-xl border border-ink-100 bg-surface-50 px-3 py-2">
                    <div className="flex items-baseline justify-between">
                      <span className="text-[13px] text-ink-500">{SCORE_LABEL[k] || k}</span>
                      <span className="text-[15px] font-semibold text-ink-800 tabular-nums">{text}</span>
                    </div>
                    <div className="mt-1.5 h-1.5 rounded-full bg-ink-200/70 overflow-hidden">
                      <div
                        className={`h-full rounded-full bg-gradient-to-r ${scoreColor(pct)} transition-all duration-500 ease-smooth`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 修改建议 */}
        {critic_suggestions.length > 0 && (
          <div className="rounded-xl border border-amber-200/80 dark:border-amber-900/60 bg-amber-50/60 dark:bg-amber-950/40 p-3">
            <div className="flex items-center gap-1.5 text-[13.5px] font-medium text-amber-800 dark:text-amber-200 mb-1.5">
              <IconBulb size={13} />
              评审建议（{critic_suggestions.length}）
            </div>
            <ul className="space-y-1">
              {critic_suggestions.map((s: string, i: number) => (
                <li key={i} className="flex gap-2 text-[14px] text-amber-900/90 dark:text-amber-200 leading-snug">
                  <span className="mt-[6px] w-1 h-1 rounded-full bg-amber-500 shrink-0" />
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 正文 */}
        <div>
          <div className="eyebrow mb-2">求职信正文</div>
          <div className="md max-h-80 overflow-y-auto rounded-xl border border-ink-200/80 bg-surface-50 p-4">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{cover_letter || '（空）'}</ReactMarkdown>
          </div>
        </div>

        {err && (
          <p className="flex items-center gap-1.5 text-[14.5px] text-rose-600 dark:text-rose-300">
            <IconAlert size={13} />
            {err}
          </p>
        )}

        {/* 操作 */}
        <div className="flex flex-wrap gap-2 pt-1">
          <button className="btn-grad" disabled={!!busy} onClick={() => decide(true)}>
            {busy === 'approve' ? <IconLoader size={15} /> : <IconCheck size={15} />}
            {busy === 'approve' ? '生成中…' : '确认并生成文档'}
          </button>
          <button className="btn-ghost" disabled={!!busy} onClick={() => decide(false)}>
            {busy === 'reject' ? <IconLoader size={15} /> : <IconX size={15} />}
            放弃草稿
          </button>
        </div>
      </div>
    </div>
  );
}
