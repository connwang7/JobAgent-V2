'use client';

import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api } from '@/lib/api';
import PageHeader, { EmptyState } from '@/components/page-header';
import { formatDateTime } from '@/lib/format';
import {
  IconAlert, IconCheck, IconCheckCircle, IconDownload, IconEye, IconLoader,
  IconMail, IconRefresh, IconX,
} from '@/components/icons';

const STATUS: Record<string, { text: string; cls: string }> = {
  draft: { text: '草稿', cls: 'badge badge-off' },
  awaiting_confirm: { text: '待确认', cls: 'badge bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-900/70' },
  confirmed: { text: '已确认', cls: 'badge badge-on' },
  archived: { text: '已归档', cls: 'badge badge-off' },
};

export default function LettersPage() {
  const [letters, setLetters] = useState<any[]>([]);
  const [detail, setDetail] = useState<any>(null);
  const [busy, setBusy] = useState('');
  const [err, setErr] = useState('');

  const load = async () => {
    try {
      setLetters(await api.listLetters());
    } catch (e: any) {
      setErr(e.message);
    }
  };
  useEffect(() => { load(); }, []);

  async function confirm(id: string, approved: boolean) {
    setBusy(id + (approved ? ':ok' : ':no'));
    setErr('');
    try {
      await api.confirmLetter(id, approved);
      setDetail(null);
      await load();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy('');
    }
  }

  async function download(id: string) {
    setBusy(id + ':dl');
    setErr('');
    try {
      const { url } = await api.downloadUrl(id);
      window.open(url, '_blank');
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy('');
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-[1000px] px-8 py-8 space-y-5">
        <PageHeader
          icon={IconMail}
          title="求职信管理"
          desc="草稿在会话中生成并通过质检，确认后才会落盘为 Word 文档"
        >
          <button className="btn-ghost" onClick={load}>
            <IconRefresh size={14} />
            刷新
          </button>
        </PageHeader>

        {err && (
          <p className="flex items-start gap-1.5 text-[14px] text-rose-600 dark:text-rose-300">
            <IconAlert size={13} className="mt-[2px] shrink-0" />
            <span className="leading-snug">{err}</span>
          </p>
        )}

        {/* 列表 */}
        <section className="card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-ink-100 flex items-center gap-2">
            <span className="section-title">求职信版本</span>
            <span className="badge badge-off tabular-nums">{letters.length}</span>
          </div>

          {letters.length === 0 ? (
            <EmptyState
              icon={IconMail}
              title="还没有求职信"
              desc="在会话工作台里让 Agent 针对某个岗位写一封，生成后可在这里确认与下载"
            />
          ) : (
            <ul className="divide-y divide-ink-100">
              {letters.map((l) => {
                const st = STATUS[l.status] || { text: l.status, cls: 'badge badge-off' };
                return (
                  <li
                    key={l.id}
                    className="px-5 py-3.5 flex items-center gap-3 hover:bg-surface-50 transition-colors"
                  >
                    <span className="w-8 h-8 shrink-0 rounded-xl bg-surface-100 text-ink-500 flex items-center justify-center font-mono text-[13px] font-semibold">
                      v{l.version}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-2">
                        <span className={`${st.cls} shrink-0`}>{st.text}</span>
                      </span>
                      <span className="block text-[13px] text-ink-400 mt-1">
                        {formatDateTime(l.created_at)}
                      </span>
                    </span>

                    <button className="btn-ghost shrink-0" onClick={() => setDetail(l)}>
                      <IconEye size={14} />
                      查看
                    </button>
                    {l.status === 'awaiting_confirm' && (
                      <button
                        className="btn-grad shrink-0"
                        disabled={!!busy}
                        onClick={() => confirm(l.id, true)}
                      >
                        {busy === l.id + ':ok' ? <IconLoader size={14} /> : <IconCheck size={14} />}
                        确认
                      </button>
                    )}
                    {l.status === 'confirmed' && (
                      <button
                        className="btn-ghost shrink-0"
                        disabled={!!busy}
                        onClick={() => download(l.id)}
                      >
                        {busy === l.id + ':dl' ? <IconLoader size={14} /> : <IconDownload size={14} />}
                        下载
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {/* 详情 */}
        {detail && (
          <section className="card overflow-hidden animate-fade-up">
            <div className="px-5 py-3.5 border-b border-ink-100 flex items-center gap-2.5">
              <span className="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-500 to-accent-500 text-white flex items-center justify-center">
                <IconMail size={15} />
              </span>
              <span className="section-title">求职信详情</span>
              <span className={`${(STATUS[detail.status] || { cls: 'badge badge-off' }).cls}`}>
                {(STATUS[detail.status] || { text: detail.status }).text}
              </span>
              <button className="btn-icon ml-auto" onClick={() => setDetail(null)} title="关闭">
                <IconX size={15} />
              </button>
            </div>

            <div className="p-5 space-y-4">
              {detail.critic_score?.scores && (
                <div>
                  <div className="eyebrow mb-2">质检评分</div>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(detail.critic_score.scores).map(([k, v]) => (
                      <span key={k} className="badge badge-info font-mono">
                        {k}: {String(v)}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="md max-h-96 overflow-y-auto rounded-xl border border-ink-200/80 bg-surface-50 p-4">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {detail.content || '（空）'}
                </ReactMarkdown>
              </div>

              {detail.status === 'awaiting_confirm' && (
                <div className="flex flex-wrap gap-2">
                  <button
                    className="btn-grad"
                    disabled={!!busy}
                    onClick={() => confirm(detail.id, true)}
                  >
                    {busy === detail.id + ':ok' ? <IconLoader size={15} /> : <IconCheckCircle size={15} />}
                    确认并生成文档
                  </button>
                  <button
                    className="btn-ghost"
                    disabled={!!busy}
                    onClick={() => confirm(detail.id, false)}
                  >
                    放弃草稿
                  </button>
                </div>
              )}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
