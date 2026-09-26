'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState, useSyncExternalStore } from 'react';
import { auth } from '@/lib/auth';
import { api, Profile } from '@/lib/api';
import { useSessionStore } from '@/lib/store';
import { relativeTime } from '@/lib/format';
import { initTheme, setThemeMode, getThemeMode, subscribeTheme, THEME_OPTIONS } from '@/lib/theme';
import type { ThemeMode } from '@/lib/theme';
import {
  Logo, IconChat, IconFile, IconBriefcase, IconMail, IconLogout,
  IconPlus, IconTrash, IconHistory, IconAlert, IconSettings,
  IconChevronRight, IconSun, IconMoon, IconMonitor,
} from '@/components/icons';

// 系统设置不再占主导航位，统一收进底部「用户卡片 → 设置」
const NAV = [
  { href: '/', label: '会话工作台', desc: 'Agent 实时执行', Icon: IconChat },
  { href: '/resume', label: '简历中心', desc: '上传与画像', Icon: IconFile },
  { href: '/jobs', label: '岗位中心', desc: '检索与匹配', Icon: IconBriefcase },
  { href: '/letters', label: '求职信管理', desc: '草稿与下载', Icon: IconMail },
];

const THEME_ICON: Record<ThemeMode, React.ComponentType<{ size?: number; className?: string }>> = {
  light: IconSun,
  dark: IconMoon,
  system: IconMonitor,
};

function useThemeMode(): ThemeMode {
  return useSyncExternalStore(
    (cb) => subscribeTheme(cb),
    () => getThemeMode(),
    () => 'system' as ThemeMode,
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [email, setEmail] = useState('');
  const [profile, setProfile] = useState<Profile | null>(null);
  const themeMode = useThemeMode();

  const sessions = useSessionStore((s) => s.sessions);
  const currentId = useSessionStore((s) => s.currentId);
  const ready = useSessionStore((s) => s.ready);
  const generating = useSessionStore((s) => s.generating);
  const error = useSessionStore((s) => s.error);

  useEffect(() => {
    initTheme();
    if (!auth.isAuthed) {
      router.replace('/auth');
      return;
    }
    // JWT 的 sub 是用户 id，payload 里没有邮箱 → 首屏先用缓存，真值走 /me/profile
    setEmail(auth.emailCache);
    void useSessionStore.getState().init();
    api
      .getProfile()
      .then((p) => {
        setProfile(p);
        setEmail(p.email || '');
        auth.setEmailCache(p.email || '');
      })
      .catch(() => {
        /* 资料接口失败不阻塞主流程，展示缓存/占位即可 */
      });
  }, [router]);

  // 在设置页改了昵称后，回到对话页要同步（用自定义事件解耦，避免多加一层全局 store）
  useEffect(() => {
    const onProfileChanged = (e: Event) => {
      const detail = (e as CustomEvent<{ nickname: string }>).detail;
      if (detail) setProfile((p) => (p ? { ...p, nickname: detail.nickname } : p));
    };
    window.addEventListener('ja:profile', onProfileChanged as EventListener);
    return () => window.removeEventListener('ja:profile', onProfileChanged as EventListener);
  }, []);

  const logout = () => {
    auth.clear();
    useSessionStore.getState().reset();
    router.replace('/auth');
  };

  const onNewSession = () => {
    if (generating) return;
    // 只切到"草稿态"，不立刻建库；首次发送消息时才真正创建会话
    useSessionStore.getState().startDraft();
    if (pathname !== '/') router.push('/');
  };

  const onSelect = (id: string) => {
    if (generating || id === currentId) return;
    useSessionStore.getState().select(id);
    if (pathname !== '/') router.push('/');
  };

  const onDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (generating) return;
    if (!confirm('删除这条对话及其全部消息？此操作不可撤销。')) return;
    await useSessionStore.getState().remove(id);
  };

  const displayName = profile?.nickname || (email ? email.split('@')[0] : '未登录');
  const settingsActive = pathname === '/settings';

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ---------------- 侧栏 ---------------- */}
      <aside className="w-[252px] shrink-0 flex flex-col bg-surface-0 border-r border-ink-200/80">
        {/* 品牌 */}
        <div className="h-[68px] shrink-0 px-5 flex items-center gap-2.5 border-b border-ink-100">
          <Logo size={32} className="shrink-0 drop-shadow-[0_2px_6px_rgba(99,102,241,0.35)]" />
          <div className="leading-tight">
            <div className="text-[16px] font-semibold tracking-tight text-ink-900">JobAgent</div>
            <div className="text-[12.5px] text-ink-400 tracking-wide">多智能体求职助手</div>
          </div>
        </div>

        {/* 主导航 */}
        <nav className="shrink-0 px-3 py-3 space-y-1">
          {NAV.map(({ href, label, desc, Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`group relative flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-150 ease-smooth ${
                  active
                    ? 'bg-tint text-tint-fg shadow-[inset_0_0_0_1px_rgba(99,102,241,0.14)]'
                    : 'text-ink-600 hover:bg-surface-100 hover:text-ink-800'
                }`}
              >
                <span
                  className={`absolute left-0 top-1/2 -translate-y-1/2 w-[3px] rounded-r-full bg-gradient-to-b from-brand-500 to-accent-500 transition-all duration-200 ${
                    active ? 'h-6 opacity-100' : 'h-0 opacity-0'
                  }`}
                />
                <span
                  className={`shrink-0 transition-colors ${
                    active ? 'text-tint-fg' : 'text-ink-400 group-hover:text-ink-600'
                  }`}
                >
                  <Icon size={20} />
                </span>
                <span className="min-w-0">
                  <span className="block text-[15px] font-medium leading-tight truncate">{label}</span>
                  <span
                    className={`block text-[12.5px] leading-tight truncate ${
                      active ? 'text-tint-fg/80' : 'text-ink-400'
                    }`}
                  >
                    {desc}
                  </span>
                </span>
              </Link>
            );
          })}
        </nav>

        {/* 对话历史 */}
        <div className="flex-1 min-h-0 flex flex-col border-t border-ink-100">
          <div className="shrink-0 px-4 pt-3.5 pb-2 flex items-center gap-2">
            <span className="text-ink-400">
              <IconHistory size={15} />
            </span>
            <span className="text-[13.5px] font-semibold text-ink-700 tracking-tight">对话历史</span>
            {sessions.length > 0 && (
              <span className="badge badge-off tabular-nums">{sessions.length}</span>
            )}
            <button
              type="button"
              onClick={onNewSession}
              disabled={generating}
              title="新建会话"
              className="ml-auto w-6 h-6 rounded-lg flex items-center justify-center text-ink-400 hover:bg-surface-100 hover:text-tint-fg transition-colors disabled:opacity-40 disabled:pointer-events-none"
            >
              <IconPlus size={14} />
            </button>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto px-2.5 pb-3 space-y-0.5">
            {/* 草稿态：尚未落库的新会话 */}
            {!currentId && (
              <div className="flex items-center gap-2.5 px-2.5 py-2 rounded-xl bg-tint shadow-[inset_0_0_0_1px_rgba(99,102,241,0.14)]">
                <span className="w-1.5 h-1.5 rounded-full bg-brand-500 shrink-0" />
                <span className="text-[13.5px] font-medium text-tint-fg truncate">新会话</span>
                <span className="ml-auto text-[12.5px] text-tint-fg/80 shrink-0">未开始</span>
              </div>
            )}

            {ready && sessions.length === 0 && currentId === '' && (
              <p className="px-2.5 py-3 text-[12.5px] text-ink-400 leading-relaxed">
                还没有历史对话。
                <br />
                发送第一条消息后会自动保存到这里。
              </p>
            )}

            {!ready && <p className="px-2.5 py-2 text-[12.5px] text-ink-400">加载中…</p>}

            {sessions.map((s) => {
              const active = s.id === currentId;
              return (
                <div
                  key={s.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelect(s.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') onSelect(s.id);
                  }}
                  title={generating ? '生成中，暂不能切换会话' : s.title}
                  className={`group relative flex items-start gap-2 px-2.5 py-2 rounded-xl cursor-pointer transition-colors ${
                    active ? 'bg-tint' : 'hover:bg-surface-100'
                  } ${generating && !active ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  {active && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-gradient-to-b from-brand-500 to-accent-500" />
                  )}
                  <span className={`mt-[3px] shrink-0 ${active ? 'text-tint-fg' : 'text-ink-300'}`}>
                    {active && generating ? (
                      <span className="block w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse-soft" />
                    ) : (
                      <span className="block w-1.5 h-1.5 rounded-full bg-current opacity-60" />
                    )}
                  </span>

                  <span className="min-w-0 flex-1">
                    <span
                      className={`block text-[13.5px] leading-snug truncate ${
                        active ? 'font-medium text-tint-fg' : 'text-ink-700'
                      }`}
                    >
                      {s.title || '未命名会话'}
                    </span>
                    <span className="block text-[12.5px] text-ink-400 mt-0.5">
                      {relativeTime(s.updated_at || s.created_at)}
                    </span>
                  </span>

                  <button
                    type="button"
                    title="删除这条对话"
                    onClick={(e) => onDelete(e, s.id)}
                    disabled={generating}
                    className="shrink-0 mt-[1px] w-6 h-6 rounded-lg flex items-center justify-center text-ink-300 opacity-0 group-hover:opacity-100 hover:text-rose-500 hover:bg-surface-0 transition-all disabled:hidden"
                  >
                    <IconTrash size={13} />
                  </button>
                </div>
              );
            })}

            {error && (
              <p className="px-2.5 py-2 flex items-start gap-1.5 text-[12.5px] text-rose-600 dark:text-rose-300">
                <IconAlert size={12} className="mt-[2px] shrink-0" />
                <span className="leading-snug">{error}</span>
              </p>
            )}
          </div>
        </div>

        {/* ---------------- 底部：用户卡片 → 设置 ---------------- */}
        <div className="shrink-0 p-3 border-t border-ink-100 space-y-1.5">
          {/* 主题快捷切换（唯一入口；详细设置在「设置 → 外观」） */}
          <div className="flex items-center gap-0.5 p-0.5 rounded-xl bg-surface-100 border border-ink-100">
            {THEME_OPTIONS.map(({ value, label }) => {
              const Icon = THEME_ICON[value];
              const on = themeMode === value;
              return (
                <button
                  key={value}
                  type="button"
                  title={label}
                  aria-pressed={on}
                  onClick={() => setThemeMode(value)}
                  className={`flex-1 h-7 rounded-lg flex items-center justify-center gap-1 text-[12.5px] font-medium transition-all duration-150 ease-smooth ${
                    on
                      ? 'bg-surface-0 text-tint-fg shadow-card'
                      : 'text-ink-400 hover:text-ink-700'
                  }`}
                >
                  <Icon size={14} />
                  <span className="hidden xl:inline">{label}</span>
                </button>
              );
            })}
          </div>

          {/* 用户卡片：点击进入统一设置页 */}
          <Link
            href="/settings"
            title="打开设置"
            className={`group flex items-center gap-2.5 px-2.5 py-2 rounded-xl border transition-all duration-150 ease-smooth ${
              settingsActive
                ? 'bg-tint border-tint-line'
                : 'bg-surface-50 border-ink-100 hover:bg-surface-100 hover:border-ink-200'
            }`}
          >
            <span className="w-8 h-8 shrink-0 rounded-lg bg-gradient-to-br from-brand-500 to-accent-500 text-white text-[13px] font-semibold flex items-center justify-center">
              {(displayName || 'U').slice(0, 1).toUpperCase()}
            </span>
            <span className="min-w-0 flex-1 leading-tight">
              <span
                className={`block text-[13px] font-medium truncate ${
                  settingsActive ? 'text-tint-fg' : 'text-ink-700'
                }`}
              >
                {displayName}
              </span>
              <span className="block text-[12.5px] text-ink-400 truncate">{email || '—'}</span>
            </span>
            <span
              className={`shrink-0 flex items-center gap-1 ${
                settingsActive ? 'text-tint-fg' : 'text-ink-400 group-hover:text-ink-600'
              }`}
            >
              <IconSettings size={15} />
            </span>
            <IconChevronRight
              size={13}
              className={`shrink-0 ${settingsActive ? 'text-tint-fg' : 'text-ink-300 group-hover:text-ink-500'}`}
            />
          </Link>

          <button
            className="w-full btn-ghost justify-start text-ink-500 hover:text-ink-800 border-transparent hover:border-ink-200"
            onClick={logout}
          >
            <IconLogout size={16} />
            退出登录
          </button>
        </div>
      </aside>

      {/* ---------------- 内容 ---------------- */}
      <main className="flex-1 min-w-0 overflow-hidden">{children}</main>
    </div>
  );
}
