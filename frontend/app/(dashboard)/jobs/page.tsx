'use client';

import { useState } from 'react';
import { api } from '@/lib/api';
import PageHeader, { EmptyState } from '@/components/page-header';
import {
  IconAlert, IconBriefcase, IconCheck, IconGlobe, IconLayers, IconLoader,
  IconSearch, IconTarget,
} from '@/components/icons';

/** 匹配度 → 渐变条颜色（沿用 A 股习惯外的通用语义：高=绿、中=品牌蓝、低=琥珀） */
function scoreTone(score: number): string {
  const p = score * 100;
  if (p >= 80) return 'from-emerald-400 to-emerald-500';
  if (p >= 60) return 'from-brand-400 to-brand-500';
  if (p >= 40) return 'from-amber-400 to-amber-500';
  return 'from-rose-400 to-rose-500';
}

export default function JobsPage() {
  const [keyword, setKeyword] = useState('大模型');
  const [location, setLocation] = useState('北京');
  const [jobs, setJobs] = useState<any[]>([]);
  const [matches, setMatches] = useState<any[]>([]);
  const [loading, setLoading] = useState<'' | 'search' | 'match'>('');
  const [err, setErr] = useState('');
  const [searched, setSearched] = useState(false);

  async function search() {
    if (!keyword.trim()) return;
    setLoading('search');
    setErr('');
    try {
      setJobs(await api.searchJobs(keyword.trim(), location.trim()));
      setSearched(true);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading('');
    }
  }

  async function loadMatches() {
    setLoading('match');
    setErr('');
    try {
      setMatches(await api.matches());
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading('');
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-[1140px] px-8 py-8 space-y-5">
        <PageHeader
          icon={IconBriefcase}
          title="岗位中心"
          desc="关键词检索实时岗位，或基于简历画像做 RAG 人岗匹配排序"
        />

        {/* 检索栏 */}
        <section className="card p-4">
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="relative flex-1">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-300">
                <IconSearch size={15} />
              </span>
              <input
                className="input pl-9"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && search()}
                placeholder="关键词，如：大模型 / 算法工程师"
              />
            </div>
            <div className="relative sm:w-44">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-300">
                <IconGlobe size={15} />
              </span>
              <input
                className="input pl-9"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && search()}
                placeholder="城市"
              />
            </div>
            <button className="btn-grad shrink-0" onClick={search} disabled={!!loading}>
              {loading === 'search' ? <IconLoader size={15} /> : <IconSearch size={15} />}
              检索岗位
            </button>
            <button className="btn-ghost shrink-0" onClick={loadMatches} disabled={!!loading}>
              {loading === 'match' ? <IconLoader size={15} /> : <IconTarget size={15} />}
              人岗匹配
            </button>
          </div>

          {err && (
            <p className="mt-3 flex items-start gap-1.5 text-[14px] text-rose-600 dark:text-rose-300">
              <IconAlert size={13} className="mt-[2px] shrink-0" />
              <span className="leading-snug">{err}</span>
            </p>
          )}
        </section>

        {/* 搜索结果 */}
        <section className="card overflow-hidden">
          <div className="px-5 py-3.5 border-b border-ink-100 flex items-center gap-2">
            <span className="section-title">检索结果</span>
            {searched && <span className="badge badge-off tabular-nums">{jobs.length}</span>}
            {searched && jobs.length > 0 && (
              <span className="ml-auto text-[13px] text-ink-400">
                {keyword} · {location || '不限城市'}
              </span>
            )}
          </div>

          {!searched ? (
            <EmptyState
              icon={IconSearch}
              title="还没有检索结果"
              desc="输入关键词与城市后点击「检索岗位」；也可直接在会话工作台让 Agent 帮你找"
            />
          ) : jobs.length === 0 ? (
            <EmptyState icon={IconBriefcase} title="没有匹配的岗位" desc="换个关键词或城市再试一次" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[14.5px]">
                <thead className="bg-surface-50">
                  <tr className="text-left text-ink-500">
                    <th className="px-5 py-2.5 font-medium">职位</th>
                    <th className="px-3 py-2.5 font-medium">公司</th>
                    <th className="px-3 py-2.5 font-medium">地点</th>
                    <th className="px-3 py-2.5 font-medium">薪资</th>
                    <th className="px-5 py-2.5 font-medium text-right">链接</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {jobs.map((j) => (
                    <tr key={j.id} className="hover:bg-surface-50 transition-colors">
                      <td className="px-5 py-3 font-medium text-ink-800">{j.title}</td>
                      <td className="px-3 py-3 text-ink-600">{j.company}</td>
                      <td className="px-3 py-3 text-ink-600">{j.location}</td>
                      <td className="px-3 py-3 text-ink-600 tabular-nums">{j.salary_text || '—'}</td>
                      <td className="px-5 py-3 text-right">
                        {j.url ? (
                          <a
                            className="inline-flex items-center gap-1 text-tint-fg font-medium hover:text-tint-fg"
                            href={j.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            查看
                          </a>
                        ) : (
                          <span className="text-ink-300">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* 匹配排行 */}
        {matches.length > 0 && (
          <section className="card overflow-hidden animate-fade-up">
            <div className="px-5 py-3.5 border-b border-ink-100 flex items-center gap-2.5">
              <span className="w-8 h-8 rounded-xl bg-tint text-tint-fg flex items-center justify-center">
                <IconLayers size={15} />
              </span>
              <span className="section-title">RAG 匹配排行</span>
              <span className="badge badge-info tabular-nums">{matches.length}</span>
            </div>

            <ul className="divide-y divide-ink-100">
              {matches.map((m, i) => {
                const pct = Math.round((m.overall_score || 0) * 100);
                const covered = m.skill_match?.covered || [];
                const missing = m.skill_gaps?.missing || m.skill_match?.missing || [];
                return (
                  <li key={i} className="px-5 py-4 hover:bg-surface-50 transition-colors">
                    <div className="flex items-center gap-3">
                      <span className="w-6 h-6 shrink-0 rounded-lg bg-surface-100 text-ink-500 text-[13px] font-semibold flex items-center justify-center tabular-nums">
                        {i + 1}
                      </span>
                      <span className="min-w-0 flex-1 text-[15px] font-medium text-ink-800 truncate">
                        {m.job?.title}
                        <span className="text-ink-400 font-normal"> · {m.job?.company}</span>
                      </span>
                      <span className="shrink-0 text-[15px] font-semibold text-ink-800 tabular-nums">
                        {pct}%
                      </span>
                    </div>

                    <div className="mt-2 ml-9 h-1.5 rounded-full bg-ink-200/70 overflow-hidden">
                      <div
                        className={`h-full rounded-full bg-gradient-to-r ${scoreTone(m.overall_score || 0)} transition-all duration-500 ease-smooth`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>

                    <div className="mt-2.5 ml-9 flex flex-wrap gap-x-4 gap-y-1 text-[13.5px]">
                      {covered.length > 0 && (
                        <span className="inline-flex items-start gap-1 text-emerald-600 dark:text-emerald-300">
                          <IconCheck size={12} className="mt-[2px] shrink-0" />
                          <span>已覆盖：{covered.join('、')}</span>
                        </span>
                      )}
                      {missing.length > 0 && (
                        <span className="inline-flex items-start gap-1 text-amber-600 dark:text-amber-300">
                          <IconAlert size={12} className="mt-[2px] shrink-0" />
                          <span>差距：{missing.join('、')}</span>
                        </span>
                      )}
                    </div>

                    {m.experience_match?.note && (
                      <p className="mt-1 ml-9 text-[13px] text-ink-400 leading-snug">
                        {m.experience_match.note}
                      </p>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}
