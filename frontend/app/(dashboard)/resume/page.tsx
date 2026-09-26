'use client';

import { useEffect, useRef, useState } from 'react';
import { api, type ResumeEventItem, type ResumeItem } from '@/lib/api';
import PageHeader, { EmptyState } from '@/components/page-header';
import { formatDateTime, relativeTime } from '@/lib/format';
import {
  IconAlert, IconCheck, IconChevronDown, IconChevronRight, IconFile,
  IconHistory, IconLoader, IconRefresh, IconSearch, IconTrash, IconUpload, IconZap,
} from '@/components/icons';

const STATUS: Record<string, { text: string; cls: string }> = {
  pending: { text: '排队中', cls: 'badge badge-off' },
  parsing: { text: '解析中', cls: 'badge badge-info' },
  ready: { text: '已就绪', cls: 'badge badge-on' },
  failed: { text: '解析失败', cls: 'badge bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-300 border-rose-200 dark:border-rose-900/70' },
};

/** 时间线事件 → 文案与节点色。dot 是时间线左侧的小圆点。 */
const EVENTS: Record<string, { text: string; dot: string; tone: string }> = {
  uploaded: { text: '上传成功', dot: 'bg-brand-400', tone: 'text-ink-700' },
  reparse_requested: { text: '重新解析', dot: 'bg-amber-400', tone: 'text-ink-700' },
  parse_started: { text: '开始解析', dot: 'bg-sky-400', tone: 'text-ink-700' },
  parse_succeeded: { text: '解析成功', dot: 'bg-emerald-500', tone: 'text-emerald-600 dark:text-emerald-400' },
  parse_failed: { text: '解析失败', dot: 'bg-rose-500', tone: 'text-rose-600 dark:text-rose-300' },
};

function eventMeta(event: string) {
  return EVENTS[event] || { text: event, dot: 'bg-ink-300', tone: 'text-ink-600' };
}

function isActive(status: string) {
  return status === 'pending' || status === 'parsing';
}

export default function ResumePage() {
  const [resumes, setResumes] = useState<ResumeItem[]>([]);
  const [profile, setProfile] = useState<any>(null);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const [uploading, setUploading] = useState(false);
  const [drag, setDrag] = useState(false);

  // 单条删除的两步确认：先点「删除」把该行切成确认态，避免误删
  const [confirmDel, setConfirmDel] = useState<number | null>(null);
  const [clearing, setClearing] = useState(false);      // 清空确认面板是否展开
  const [busy, setBusy] = useState(false);              // 删除请求进行中

  // 操作历史（时间线）：同一时刻只展开一行
  const [openId, setOpenId] = useState<number | null>(null);
  const [timeline, setTimeline] = useState<ResumeEventItem[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineErr, setTimelineErr] = useState('');
  const openIdRef = useRef<number | null>(null);
  openIdRef.current = openId;

  const load = async () => {
    try {
      setResumes(await api.listResumes());
    } catch (e: any) {
      setErr(e.message);
    }
  };
  useEffect(() => { void load(); }, []);

  // 有仍在解析的版本就轮询状态：否则用户会一直看到「解析中」，
  // 只有手动刷新才知道已经 ready / failed（之前就是这么丢状态的）。
  useEffect(() => {
    if (!resumes.some((r) => isActive(r.status))) return;
    const t = window.setInterval(() => {
      void load();
      // 时间线开着时一并刷新，用户能实时看到「开始解析 → 解析成功」
      if (openIdRef.current != null) void fetchTimeline(openIdRef.current, true);
    }, 5000);
    return () => window.clearInterval(t);
  }, [resumes]);

  async function fetchTimeline(id: number, quiet = false) {
    if (!quiet) {
      setTimelineLoading(true);
      setTimeline([]);
    }
    setTimelineErr('');
    try {
      const r = await api.resumeEvents(id);
      setTimeline(r.events);
    } catch (e: any) {
      if (!quiet) setTimelineErr(e.message);
    } finally {
      if (!quiet) setTimelineLoading(false);
    }
  }

  function toggleTimeline(id: number) {
    if (openId === id) {
      setOpenId(null);
      return;
    }
    setOpenId(id);
    void fetchTimeline(id);
  }

  async function upload(file: File) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setErr('仅支持 PDF 格式');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setErr('文件超过 10MB 限制');
      return;
    }
    setUploading(true);
    setErr('');
    setMsg('上传中…');
    try {
      const r = await api.uploadResume(file);
      setMsg(`已上传（v${r.version}），正在解析…`);
      await load();
      // 解析由后台任务执行，稍后自动刷新一次状态；失败要说清楚原因
      window.setTimeout(async () => {
        const list = await api.listResumes().catch(() => []);
        const latest = (list as ResumeItem[]).find((x) => x.id === r.id);
        if (latest && latest.status === 'failed') {
          setMsg('');
          setErr(`解析失败：${latest.error || '未知原因'}。请到「设置 → 大模型接入」配置 Key 后点「重新解析」`);
        }
        void load();
      }, 6000);
    } catch (e: any) {
      setErr(e.message);
      setMsg('');
    } finally {
      setUploading(false);
    }
  }

  async function view(id: number) {
    try {
      setProfile(await api.resumeProfile(id));
    } catch (e: any) {
      setErr(e.message);
    }
  }

  /** 重新解析：配好大模型 Key（或任务被中断）后的补救入口，不用重传文件 */
  async function reparse(id: number) {
    setErr('');
    setMsg('已重新提交解析，稍候自动刷新…');
    try {
      await api.reparseResume(id);
      await load();
      if (openIdRef.current === id) void fetchTimeline(id, true);
      window.setTimeout(async () => {
        await load();
        if (openIdRef.current === id) void fetchTimeline(id, true);
      }, 6000);
    } catch (e: any) {
      setErr(e.message);
      setMsg('');
    }
  }

  /** 删除单个版本：对象存储 + 解析结果 + 操作历史一起删，不可恢复 */
  async function remove(r: ResumeItem) {
    setBusy(true);
    setErr('');
    setMsg('');
    try {
      const res = await api.deleteResume(r.id);
      // 打开着的时间线 / 画像属于被删的那一份，一起收掉
      if (openIdRef.current === r.id) setOpenId(null);
      if (profile?.resume_id === r.id) setProfile(null);
      setConfirmDel(null);
      setMsg(res.object_deleted
        ? `已删除 v${res.version}（含文件与解析结果）`
        : `已删除 v${res.version} 记录（文件此前已不存在）`);
      await load();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  /** 一键清空：全部版本一次性删除，不可恢复 */
  async function clearAll() {
    setBusy(true);
    setErr('');
    setMsg('');
    try {
      const res = await api.clearResumes();
      setOpenId(null);
      setProfile(null);
      setClearing(false);
      setConfirmDel(null);
      setMsg(`已清空 ${res.deleted} 个简历版本（含文件与解析结果）`);
      await load();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-[1000px] px-8 py-8 space-y-5">
        <PageHeader
          icon={IconFile}
          title="简历中心"
          desc="上传 PDF 后自动解析为结构化画像，供岗位匹配与求职信撰写使用"
        />

        {/* 上传区 */}
        <label
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            const f = e.dataTransfer.files?.[0];
            if (f) upload(f);
          }}
          className={`card border-dashed flex flex-col items-center justify-center text-center px-6 py-10 cursor-pointer transition-all duration-200 ease-smooth ${
            drag ? 'border-brand-400 bg-tint/60' : 'hover:border-brand-300 hover:bg-surface-50'
          }`}
        >
          <input
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
            disabled={uploading}
          />
          <span
            className={`w-12 h-12 rounded-2xl flex items-center justify-center mb-3 transition-colors ${
              uploading ? 'bg-tint-2 text-tint-fg' : 'bg-surface-100 text-ink-400'
            }`}
          >
            {uploading ? <IconLoader size={20} /> : <IconUpload size={20} />}
          </span>
          <p className="text-[15.5px] font-medium text-ink-800">
            {uploading ? '正在上传并解析…' : '拖拽 PDF 到此处，或点击选择文件'}
          </p>
          <p className="mt-1 text-[13.5px] text-ink-400">支持 PDF · 单文件 ≤ 10MB · 自动版本管理</p>
        </label>

        {(msg || err) && (
          <div
            className={`flex items-start gap-2 rounded-xl border px-3.5 py-2.5 text-[14.5px] animate-fade-up ${
              err ? 'border-rose-200 dark:border-rose-900/70 bg-rose-50/70 dark:bg-rose-950/45 text-rose-700 dark:text-rose-300'
                  : 'border-tint-line bg-tint/60 text-tint-fg'
            }`}
          >
            {err
              ? <IconAlert size={14} className="mt-[1px] shrink-0" />
              : <IconCheck size={14} className="mt-[1px] shrink-0" />}
            <span className="leading-snug">{err || msg}</span>
          </div>
        )}

        {/* 版本列表 */}
        <section className="card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-ink-100 flex items-center gap-2">
            <span className="section-title">简历版本</span>
            <span className="badge badge-off tabular-nums">{resumes.length}</span>
            {resumes.length > 0 && (
              <button
                className="btn-danger ml-auto"
                onClick={() => setClearing((v) => !v)}
                disabled={busy}
              >
                <IconTrash size={14} />
                清空全部
              </button>
            )}
          </div>

          {/* 一键清空的二次确认：明确说清楚删多少、删什么 */}
          {clearing && resumes.length > 0 && (
            <div className="px-5 py-3 border-b border-rose-200 dark:border-rose-900/70 bg-rose-50/70 dark:bg-rose-950/40 flex items-start gap-2.5 animate-fade-up">
              <IconAlert size={15} className="mt-[2px] shrink-0 text-rose-600 dark:text-rose-300" />
              <div className="min-w-0 flex-1">
                <p className="text-[14.5px] font-medium text-rose-700 dark:text-rose-300">
                  确定清空全部 {resumes.length} 个简历版本？
                </p>
                <p className="mt-1 text-[13.5px] leading-snug text-rose-600/90 dark:text-rose-300/80">
                  将删除全部 PDF 文件、解析出的结构化画像与操作历史，且无法恢复。
                  已生成的会话和求职信会保留，但不再关联任何简历。
                </p>
                <div className="mt-2.5 flex items-center gap-2">
                  <button className="btn-danger" onClick={clearAll} disabled={busy}>
                    {busy ? <IconLoader size={14} /> : <IconTrash size={14} />}
                    确认清空
                  </button>
                  <button className="btn-ghost" onClick={() => setClearing(false)} disabled={busy}>
                    取消
                  </button>
                </div>
              </div>
            </div>
          )}

          {resumes.length === 0 ? (
            <EmptyState
              icon={IconFile}
              title="还没有上传简历"
              desc="上传第一份简历，系统会自动解析技能、经验年限与经历亮点"
            />
          ) : (
            <ul className="divide-y divide-ink-100">
              {resumes.map((r) => {
                const st = STATUS[r.status] || { text: r.status, cls: 'badge badge-off' };
                const open = openId === r.id;
                const asking = confirmDel === r.id;
                return (
                  <li key={r.id} className="hover:bg-surface-50 transition-colors">
                    <div className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <span className="w-8 h-8 shrink-0 rounded-xl bg-surface-100 text-ink-500 flex items-center justify-center font-mono text-[13px] font-semibold">
                          v{r.version}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block text-[15px] font-medium text-ink-800 truncate">
                            {r.filename}
                          </span>
                          <span className="block text-[13px] text-ink-400 mt-0.5">
                            {formatDateTime(r.created_at)}
                            <span className="ml-1.5 text-ink-300">·</span>
                            <span className="ml-1.5">{relativeTime(r.created_at)}</span>
                          </span>
                        </span>
                        <span className={`${st.cls} shrink-0`}>{st.text}</span>

                        {r.status !== 'ready' && !asking && (
                          <button
                            className="btn-ghost shrink-0"
                            onClick={() => reparse(r.id)}
                            title="重新提交解析（配好大模型 Key 后无需重传文件）"
                          >
                            <IconRefresh size={14} />
                            重新解析
                          </button>
                        )}
                        <button className="btn-ghost shrink-0" onClick={() => view(r.id)}>
                          <IconSearch size={14} />
                          画像
                        </button>
                        <button
                          className={`btn-ghost shrink-0 ${open ? 'text-brand-600 bg-tint' : ''}`}
                          onClick={() => toggleTimeline(r.id)}
                          aria-expanded={open}
                          title="查看该版本的操作时间线"
                        >
                          <IconHistory size={14} />
                          操作历史
                          {open ? <IconChevronDown size={13} /> : <IconChevronRight size={13} />}
                        </button>
                        {!asking && (
                          <button
                            className="btn-icon shrink-0 text-ink-400 hover:text-rose-600 dark:hover:text-rose-400"
                            onClick={() => { setConfirmDel(r.id); setClearing(false); }}
                            title="删除该版本"
                            aria-label={`删除 v${r.version}`}
                          >
                            <IconTrash size={15} />
                          </button>
                        )}
                      </div>

                      {r.error && (
                        <p className="mt-2 ml-11 flex items-start gap-1.5 text-[13px] text-rose-600 dark:text-rose-300 leading-snug">
                          <IconAlert size={13} className="mt-[2px] shrink-0" />
                          <span className="min-w-0 break-words">{r.error}</span>
                        </p>
                      )}

                      {/* 单条删除的二次确认，就地展开不打弹窗 */}
                      {asking && (
                        <div className="mt-2.5 ml-11 rounded-xl border border-rose-200 dark:border-rose-900/70 bg-rose-50/70 dark:bg-rose-950/40 px-3.5 py-2.5 flex items-start gap-2.5 animate-fade-up">
                          <IconAlert size={14} className="mt-[2px] shrink-0 text-rose-600 dark:text-rose-300" />
                          <div className="min-w-0 flex-1">
                            <p className="text-[14px] font-medium text-rose-700 dark:text-rose-300">
                              删除 v{r.version}？文件、解析画像与操作历史都会一并删除，无法恢复。
                            </p>
                            <div className="mt-2 flex items-center gap-2">
                              <button className="btn-danger" onClick={() => remove(r)} disabled={busy}>
                                {busy ? <IconLoader size={13} /> : <IconTrash size={13} />}
                                确认删除
                              </button>
                              <button
                                className="btn-ghost"
                                onClick={() => setConfirmDel(null)}
                                disabled={busy}
                              >
                                取消
                              </button>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* 操作历史时间线 */}
                      {open && (
                        <div className="mt-3 ml-11 rounded-xl border border-ink-100 bg-surface-50 px-4 py-3 animate-fade-up">
                          {timelineLoading ? (
                            <p className="flex items-center gap-2 text-[13.5px] text-ink-400">
                              <IconLoader size={13} />
                              正在读取操作历史…
                            </p>
                          ) : timelineErr ? (
                            <p className="flex items-start gap-1.5 text-[13.5px] text-rose-600 dark:text-rose-300">
                              <IconAlert size={13} className="mt-[2px] shrink-0" />
                              <span>{timelineErr}</span>
                            </p>
                          ) : timeline.length === 0 ? (
                            <p className="text-[13.5px] text-ink-400">
                              暂无操作记录（该版本上传于时间线功能上线前，可点「重新解析」补记）
                            </p>
                          ) : (
                            <ol className="relative space-y-3 pl-4">
                              {/* 竖线：最后一个节点不画到底 */}
                              <span
                                className="absolute left-[3px] top-1.5 bottom-1.5 w-px bg-ink-200"
                                aria-hidden="true"
                              />
                              {timeline.map((e) => {
                                const m = eventMeta(e.event);
                                return (
                                  <li key={e.id} className="relative">
                                    <span
                                      className={`absolute -left-4 top-[6px] w-[7px] h-[7px] rounded-full ring-2 ring-surface-50 ${m.dot}`}
                                      aria-hidden="true"
                                    />
                                    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                                      <span className={`text-[14px] font-medium ${m.tone}`}>{m.text}</span>
                                      <span className="text-[12.5px] text-ink-400 tabular-nums">
                                        {formatDateTime(e.created_at)}
                                      </span>
                                    </div>
                                    {e.detail && (
                                      <p
                                        className={`mt-0.5 text-[13px] leading-snug break-words ${
                                          e.event === 'parse_failed'
                                            ? 'text-rose-600 dark:text-rose-300'
                                            : 'text-ink-500'
                                        }`}
                                      >
                                        {e.detail}
                                      </p>
                                    )}
                                  </li>
                                );
                              })}
                            </ol>
                          )}
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {/* 画像 */}
        {profile && (
          <section className="card overflow-hidden animate-fade-up">
            <div className="px-5 py-3.5 border-b border-ink-100 flex items-center gap-2.5">
              <span className="w-8 h-8 rounded-xl bg-tint text-tint-fg flex items-center justify-center">
                <IconZap size={15} />
              </span>
              <span className="section-title">结构化画像</span>
              {profile.profile?.experience_years != null && (
                <span className="ml-auto badge badge-info">
                  经验 {profile.profile.experience_years} 年
                </span>
              )}
            </div>

            <div className="p-5 space-y-4">
              {(profile.profile?.skills || []).length > 0 && (
                <div>
                  <div className="eyebrow mb-2">技能标签</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(profile.profile.skills as string[]).map((s) => (
                      <span
                        key={s}
                        className="px-2.5 py-1 rounded-lg bg-tint text-tint-fg text-[13.5px] font-medium border border-tint-line"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {(profile.profile?.highlights || []).length > 0 && (
                <div>
                  <div className="eyebrow mb-2">经历亮点</div>
                  <ul className="space-y-1.5">
                    {(profile.profile.highlights as string[]).map((h, i) => (
                      <li key={i} className="flex gap-2 text-[14.5px] text-ink-600 leading-snug">
                        <span className="mt-[7px] w-1 h-1 rounded-full bg-brand-400 shrink-0" />
                        <span>{h}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {profile.raw_analysis && (
                <details className="rounded-xl border border-ink-100 bg-surface-50">
                  <summary className="px-3.5 py-2.5 cursor-pointer text-[14px] font-medium text-ink-600 select-none">
                    查看原始解析文本
                  </summary>
                  <pre className="px-3.5 pb-3.5 whitespace-pre-wrap text-[13.5px] leading-relaxed text-ink-500 font-mono">
                    {profile.raw_analysis}
                  </pre>
                </details>
              )}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
