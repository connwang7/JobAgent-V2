'use client';

import { useEffect, useMemo, useState } from 'react';
import { api, LLM_ROLES, LLMConfig, LLMTestResult, Profile } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { setThemeMode, subscribeTheme, getThemeMode, THEME_OPTIONS } from '@/lib/theme';
import type { ThemeMode } from '@/lib/theme';
import {
  IconAlert, IconBrain, IconCheck, IconCheckCircle, IconChat, IconDatabase,
  IconFile, IconGlobe, IconKey, IconLayers, IconLoader, IconLock, IconMail,
  IconMoon, IconPalette, IconPencil, IconRefresh, IconSearch, IconShield,
  IconSparkles, IconSun, IconMonitor, IconTarget, IconUser, IconWrench,
  IconX, IconZap,
} from '@/components/icons';

/* --------------------------------------------------------------- 常量 / 配置 */

const BASE_URL_PRESETS: {
  label: string;
  hint: string;
  url: string;
  models: Record<string, string>;
}[] = [
  {
    label: '阿里云百炼',
    hint: 'DashScope 兼容模式',
    url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: {
      planner: 'qwen-turbo', worker: 'qwen-plus', writer: 'qwen-max',
      critic: 'qwen-plus', thinking: 'qwen-plus',
    },
  },
  {
    label: 'DeepSeek',
    hint: '原生推理模型',
    url: 'https://api.deepseek.com/v1',
    models: {
      planner: 'deepseek-chat', worker: 'deepseek-chat', writer: 'deepseek-chat',
      critic: 'deepseek-reasoner', thinking: 'deepseek-reasoner',
    },
  },
  {
    label: 'OpenAI',
    hint: '官方端点',
    url: 'https://api.openai.com/v1',
    models: {
      planner: 'gpt-4o-mini', worker: 'gpt-4o-mini', writer: 'gpt-4o',
      critic: 'gpt-4o-mini', thinking: 'o4-mini',
    },
  },
  {
    label: '智谱 GLM',
    hint: 'open.bigmodel.cn',
    url: 'https://open.bigmodel.cn/api/paas/v4',
    models: {
      planner: 'glm-4-flash', worker: 'glm-4-flash', writer: 'glm-4-plus',
      critic: 'glm-4-flash', thinking: 'glm-4-plus',
    },
  },
];

const ROLE_ICON: Record<string, any> = {
  planner: IconTarget,
  worker: IconWrench,
  writer: IconMail,
  critic: IconShield,
  thinking: IconBrain,
};

const THEME_ICON: Record<ThemeMode, any> = {
  light: IconSun,
  dark: IconMoon,
  system: IconMonitor,
};

type TabKey = 'account' | 'appearance' | 'model' | 'preferences';

const TABS: { key: TabKey; label: string; desc: string; Icon: any }[] = [
  { key: 'account', label: '账号信息', desc: '资料 · 数据概览 · 密码', Icon: IconUser },
  { key: 'appearance', label: '外观', desc: '白天 / 夜晚 / 跟随系统', Icon: IconPalette },
  { key: 'model', label: '大模型接入', desc: '密钥 · 端点 · 模型分层', Icon: IconZap },
  { key: 'preferences', label: '求职偏好', desc: '城市 · 行业 · 薪资', Icon: IconTarget },
];

/* ------------------------------------------------------------------- 小组件 */

function Badge({ on, children, tone = 'auto' }: {
  on?: boolean;
  children: React.ReactNode;
  tone?: 'auto' | 'info';
}) {
  const cls = tone === 'info' ? 'badge badge-info' : on ? 'badge badge-on' : 'badge badge-off';
  return (
    <span className={cls}>
      {on && tone === 'auto' && <IconCheck size={10} />}
      {children}
    </span>
  );
}

function StatusTile({ icon: Icon, label, value, ok, hint }: {
  icon: any;
  label: string;
  value: string;
  ok: boolean;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-ink-100 bg-surface-0 px-3 py-2.5">
      <div className="flex items-center gap-1.5">
        <span className={ok ? 'text-emerald-500 dark:text-emerald-400' : 'text-ink-300'}>
          <Icon size={13} />
        </span>
        <span className="text-[13px] text-ink-500">{label}</span>
        <span className={`ml-auto w-1.5 h-1.5 rounded-full ${ok ? 'bg-emerald-500' : 'bg-ink-300'}`} />
      </div>
      <div className={`mt-1 text-[14.5px] font-medium truncate ${ok ? 'text-ink-800' : 'text-ink-400'}`}
           title={value}>
        {value}
      </div>
      {hint && <div className="mt-0.5 text-[12.5px] text-ink-400 truncate">{hint}</div>}
    </div>
  );
}

function Section({ icon: Icon, title, desc, right, children }: {
  icon: any;
  title: string;
  desc?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="card overflow-hidden">
      <div className="px-5 py-4 flex items-center gap-3 border-b border-ink-100">
        <span className="w-8 h-8 rounded-xl bg-tint text-tint-fg flex items-center justify-center shrink-0">
          <Icon size={16} />
        </span>
        <div className="min-w-0">
          <h2 className="section-title">{title}</h2>
          {desc && <p className="text-[13.5px] text-ink-400 mt-0.5">{desc}</p>}
        </div>
        {right && <div className="ml-auto shrink-0">{right}</div>}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function Stat({ icon: Icon, label, value }: { icon: any; label: string; value: number }) {
  return (
    <div className="rounded-xl border border-ink-100 bg-surface-50 px-3.5 py-3">
      <div className="flex items-center gap-1.5 text-ink-400">
        <Icon size={13} />
        <span className="text-[12.5px]">{label}</span>
      </div>
      <div className="mt-1 text-[21px] font-semibold tabular-nums text-ink-900 leading-none">
        {value}
      </div>
    </div>
  );
}

/* --------------------------------------------------------------------- 页面 */

export default function SettingsPage() {
  const [tab, setTab] = useState<TabKey>('account');

  // ---- 账号 ----
  const [profile, setProfile] = useState<Profile | null>(null);
  const [nickname, setNickname] = useState('');
  const [savingName, setSavingName] = useState(false);
  const [pwd, setPwd] = useState({ old_password: '', new_password: '', confirm: '' });
  const [savingPwd, setSavingPwd] = useState(false);

  // ---- 外观 ----
  const [themeMode, setThemeState] = useState<ThemeMode>('system');
  useEffect(() => {
    setThemeState(getThemeMode());
    return subscribeTheme(() => setThemeState(getThemeMode()));
  }, []);

  // ---- 大模型 / 工具 ----
  const [prefs, setPrefs] = useState({ city: '', industry: '', salary_range: '', work_type: '' });
  const [cfg, setCfg] = useState<LLMConfig | null>(null);
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [models, setModels] = useState<Record<string, string>>({});
  const [serper, setSerper] = useState('');
  const [firecrawl, setFirecrawl] = useState('');
  const [toast, setToast] = useState<{ text: string; ok: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<LLMTestResult | null>(null);

  const loadProfile = async () => {
    try {
      const p = await api.getProfile();
      setProfile(p);
      setNickname(p.nickname || '');
    } catch {
      /* 静默：账号区会显示占位 */
    }
  };

  const refresh = async () => {
    const c = await api.getLLMConfig();
    setCfg(c);
    setBaseUrl(c.base_url || '');
    setModels({ ...c.model_pref });
  };

  useEffect(() => {
    void loadProfile();
    api.getPreferences().then(setPrefs).catch(() => {});
    refresh().catch((e) => setToast({ text: e.message, ok: false }));
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 4200);
    return () => window.clearTimeout(t);
  }, [toast]);

  const flash = (text: string, ok = true) => setToast({ text, ok });

  const activePreset = useMemo(
    () => BASE_URL_PRESETS.find((p) => p.url === baseUrl.trim())?.label,
    [baseUrl],
  );

  /* ---------------- 账号操作 ---------------- */

  async function saveNickname() {
    const name = nickname.trim();
    if (!name) return flash('昵称不能为空', false);
    if (name === (profile?.nickname || '')) return flash('昵称未变化');
    setSavingName(true);
    try {
      const r = await api.putProfile({ nickname: name });
      setProfile((p) => (p ? { ...p, nickname: r.nickname } : p));
      // 通知侧栏刷新展示（自定义事件，避免再多一层全局 store）
      window.dispatchEvent(new CustomEvent('ja:profile', { detail: { nickname: r.nickname } }));
      flash('昵称已更新');
    } catch (e: any) {
      flash(e.message, false);
    } finally {
      setSavingName(false);
    }
  }

  async function changePassword() {
    if (!pwd.old_password || !pwd.new_password) return flash('请填写原密码与新密码', false);
    if (pwd.new_password.length < 8) return flash('新密码至少 8 位', false);
    if (pwd.new_password !== pwd.confirm) return flash('两次输入的新密码不一致', false);
    setSavingPwd(true);
    try {
      await api.changePassword(pwd.old_password, pwd.new_password);
      setPwd({ old_password: '', new_password: '', confirm: '' });
      flash('密码已修改，下次登录请使用新密码');
    } catch (e: any) {
      flash(e.message, false);
    } finally {
      setSavingPwd(false);
    }
  }

  /* ---------------- 模型 / 偏好操作 ---------------- */

  async function savePrefs() {
    setBusy(true);
    try {
      await api.putPreferences(prefs);
      flash('求职偏好已保存，并同时沉淀为长期记忆');
    } catch (e: any) {
      flash(e.message, false);
    } finally {
      setBusy(false);
    }
  }

  async function saveSvc() {
    setBusy(true);
    setTestResult(null);
    try {
      // 模型覆盖只提交与系统默认不同的项，留空 = 用系统默认
      const pref: Record<string, string> = {};
      for (const r of LLM_ROLES) {
        const v = (models[r.key] || '').trim();
        if (v && v !== cfg?.defaults?.[r.key]) pref[r.key] = v;
      }
      const payload: any = { model_pref: pref };
      if (apiKey) payload.api_key = apiKey;
      if (baseUrl.trim()) payload.base_url = baseUrl.trim();
      if (serper) payload.serper_api_key = serper;
      if (firecrawl) payload.firecrawl_api_key = firecrawl;

      const c = await api.putLLMConfig(payload);
      setCfg(c);
      setApiKey(''); setSerper(''); setFirecrawl('');
      setModels({ ...c.model_pref });
      flash('配置已保存并立即生效（无需重启）。密钥加密存储，不会回显明文');
    } catch (e: any) {
      flash(e.message, false);
    } finally {
      setBusy(false);
    }
  }

  async function testConn() {
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await api.testLLMConfig());
    } catch (e: any) {
      setTestResult({ ok: false, model: '', base_url: '', latency_ms: 0, reply: '', error: e.message });
    } finally {
      setTesting(false);
    }
  }

  async function clearAll() {
    if (!confirm('清除用户级全部密钥与模型覆盖？将回落到服务端 .env 配置。')) return;
    setBusy(true);
    try {
      const c = await api.clearLLMConfig();
      setCfg(c); setModels({}); setBaseUrl(''); setTestResult(null);
      flash('已清除用户级配置，回落服务端默认');
    } catch (e: any) {
      flash(e.message, false);
    } finally {
      setBusy(false);
    }
  }

  const keyOk = !!cfg?.api_key_set;
  const displayName = profile?.nickname || (profile?.email ? profile.email.split('@')[0] : '未设置');

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-[1080px] px-8 py-8">
        {/* 页头 */}
        <header className="flex items-end gap-3 flex-wrap">
          <div>
            <h1 className="text-[21px] font-semibold tracking-tight text-ink-900 flex items-center gap-2">
              <IconPalette size={19} className="text-tint-fg" />
              设置
            </h1>
            <p className="mt-1 text-[14.5px] text-ink-400">
              账号资料、界面外观、大模型接入与求职偏好
            </p>
          </div>
          <div className="ml-auto flex items-center gap-1.5">
            <Badge on={profile?.is_active}>{profile?.is_active ? '账号正常' : '账号异常'}</Badge>
            <Badge on={keyOk} tone="info">{keyOk ? '模型已就绪' : '模型未配置'}</Badge>
          </div>
        </header>

        {/* 主体：左侧分栏 + 右侧内容 */}
        <div className="mt-6 grid grid-cols-1 md:grid-cols-[196px_1fr] gap-5 items-start">
          {/* 分栏导航 */}
          <nav className="md:sticky md:top-0 card p-1.5 space-y-0.5">
            {TABS.map(({ key, label, desc, Icon }) => {
              const on = tab === key;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setTab(key)}
                  className={`w-full text-left flex items-start gap-2.5 px-2.5 py-2 rounded-xl transition-all duration-150 ease-smooth ${
                    on
                      ? 'bg-tint text-tint-fg shadow-[inset_0_0_0_1px_rgba(99,102,241,0.14)]'
                      : 'text-ink-600 hover:bg-surface-100 hover:text-ink-800'
                  }`}
                >
                  <span className={`mt-[2px] shrink-0 ${on ? 'text-tint-fg' : 'text-ink-400'}`}>
                    <Icon size={16} />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-[14.5px] font-medium leading-tight">{label}</span>
                    <span className={`block text-[12.5px] leading-tight mt-0.5 truncate ${on ? 'text-tint-fg/80' : 'text-ink-400'}`}>
                      {desc}
                    </span>
                  </span>
                </button>
              );
            })}
          </nav>

          {/* 内容区 */}
          <div className="space-y-5 min-w-0">
            {/* ================= 账号信息 ================= */}
            {tab === 'account' && (
              <>
                <Section icon={IconUser} title="账号信息" desc="邮箱为登录凭证，昵称仅用于界面展示">
                  <div className="flex items-center gap-4 flex-wrap">
                    <span className="w-14 h-14 shrink-0 rounded-2xl bg-gradient-to-br from-brand-500 to-accent-500 text-white text-[20px] font-semibold flex items-center justify-center shadow-glow">
                      {(displayName || 'U').slice(0, 1).toUpperCase()}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="text-[16px] font-medium text-ink-900 truncate">{displayName}</div>
                      <div className="text-[13.5px] text-ink-400 truncate flex items-center gap-1.5 mt-0.5">
                        <IconMail size={13} />
                        {profile?.email || '—'}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-[12.5px] text-ink-400">注册时间</div>
                      <div className="text-[13.5px] text-ink-600 tabular-nums">
                        {profile?.created_at ? formatDateTime(profile.created_at) : '—'}
                      </div>
                    </div>
                  </div>

                  <div className="mt-5">
                    <label className="label">
                      昵称 <span className="label-hint">最长 64 个字符</span>
                    </label>
                    <div className="flex items-center gap-2">
                      <div className="relative flex-1">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-300">
                          <IconPencil size={15} />
                        </span>
                        <input
                          className="input pl-9"
                          placeholder="给自己起个名字"
                          maxLength={64}
                          value={nickname}
                          onChange={(e) => setNickname(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') void saveNickname();
                          }}
                        />
                      </div>
                      <button
                        className="btn shrink-0"
                        onClick={saveNickname}
                        disabled={savingName || nickname.trim() === (profile?.nickname || '')}
                      >
                        {savingName ? <IconLoader size={15} /> : <IconCheck size={15} />}
                        保存
                      </button>
                    </div>
                  </div>
                </Section>

                <Section icon={IconDatabase} title="数据概览" desc="当前账号下的资产统计">
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
                    <Stat icon={IconChat} label="会话" value={profile?.stats?.sessions ?? 0} />
                    <Stat icon={IconFile} label="简历" value={profile?.stats?.resumes ?? 0} />
                    <Stat icon={IconMail} label="求职信" value={profile?.stats?.letters ?? 0} />
                    <Stat icon={IconBrain} label="长期记忆" value={profile?.stats?.memories ?? 0} />
                  </div>
                </Section>

                <Section
                  icon={IconLock}
                  title="修改密码"
                  desc="修改后当前登录态仍有效，下次登录请使用新密码"
                >
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div>
                      <label className="label">原密码</label>
                      <input
                        className="input"
                        type="password"
                        autoComplete="current-password"
                        value={pwd.old_password}
                        onChange={(e) => setPwd({ ...pwd, old_password: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="label">
                        新密码 <span className="label-hint">至少 8 位</span>
                      </label>
                      <input
                        className="input"
                        type="password"
                        autoComplete="new-password"
                        value={pwd.new_password}
                        onChange={(e) => setPwd({ ...pwd, new_password: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="label">确认新密码</label>
                      <input
                        className="input"
                        type="password"
                        autoComplete="new-password"
                        value={pwd.confirm}
                        onChange={(e) => setPwd({ ...pwd, confirm: e.target.value })}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') void changePassword();
                        }}
                      />
                    </div>
                  </div>
                  {pwd.new_password && pwd.confirm && pwd.new_password !== pwd.confirm && (
                    <p className="mt-2.5 flex items-center gap-1.5 text-[13px] text-rose-600 dark:text-rose-300">
                      <IconAlert size={13} />
                      两次输入的新密码不一致
                    </p>
                  )}
                  <button className="btn mt-4" onClick={changePassword} disabled={savingPwd}>
                    {savingPwd ? <IconLoader size={15} /> : <IconLock size={15} />}
                    修改密码
                  </button>
                </Section>
              </>
            )}

            {/* ================= 外观 ================= */}
            {tab === 'appearance' && (
              <Section
                icon={IconPalette}
                title="界面背景"
                desc="选择白天或夜晚模式；「跟随系统」会随操作系统外观自动切换。选择保存在本地浏览器"
                right={<Badge on tone="info">{THEME_OPTIONS.find((o) => o.value === themeMode)?.label}</Badge>}
              >
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {THEME_OPTIONS.map(({ value, label, desc }) => {
                    const Icon = THEME_ICON[value];
                    const on = themeMode === value;
                    return (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setThemeMode(value)}
                        aria-pressed={on}
                        className={`text-left rounded-2xl border p-3 transition-all duration-200 ease-smooth ${
                          on
                            ? 'border-brand-400 bg-tint shadow-[0_0_0_3px_rgba(99,102,241,0.10)]'
                            : 'border-ink-200 bg-surface-0 hover:border-tint-line hover:bg-surface-50'
                        }`}
                      >
                        {/* 预览图 */}
                        <span
                          className={`block h-[68px] rounded-xl border overflow-hidden relative ${
                            value === 'dark' ? 'border-night-700' : 'border-ink-200'
                          }`}
                          style={{
                            background:
                              value === 'dark'
                                ? 'linear-gradient(160deg,#131a26,#0b0f16)'
                                : value === 'light'
                                  ? 'linear-gradient(160deg,#ffffff,#f1f5f9)'
                                  : 'linear-gradient(100deg,#ffffff 0%,#ffffff 48%,#131a26 52%,#0b0f16 100%)',
                          }}
                        >
                          <span
                            className={`absolute left-2 top-2 h-2.5 w-12 rounded-full ${
                              value === 'dark' ? 'bg-night-700' : 'bg-ink-200'
                            }`}
                          />
                          <span
                            className={`absolute left-2 top-6 h-2 w-20 rounded-full ${
                              value === 'dark' ? 'bg-night-700' : 'bg-ink-100'
                            }`}
                          />
                          <span
                            className={`absolute left-2 bottom-2 h-3.5 w-16 rounded-md ${
                              value === 'dark' ? 'bg-night-700' : 'bg-ink-100'
                            }`}
                          />
                          <span
                            className="absolute right-2 top-2 w-5 h-5 rounded-lg bg-gradient-to-br from-brand-500 to-accent-500"
                          />
                        </span>

                        <span className="flex items-center gap-2 mt-2.5">
                          <span className={on ? 'text-tint-fg' : 'text-ink-500'}>
                            <Icon size={16} />
                          </span>
                          <span className={`text-[14.5px] font-medium ${on ? 'text-tint-fg' : 'text-ink-700'}`}>
                            {label}
                          </span>
                          {on && (
                            <span className="ml-auto text-tint-fg">
                              <IconCheckCircle size={15} />
                            </span>
                          )}
                        </span>
                        <span className="block text-[12.5px] text-ink-400 leading-snug mt-1">{desc}</span>
                      </button>
                    );
                  })}
                </div>

                <div className="mt-4 rounded-xl border border-ink-100 bg-surface-50 px-3.5 py-3">
                  <div className="flex items-start gap-2 text-[13px] text-ink-500 leading-relaxed">
                    <IconSparkles size={14} className="mt-[2px] shrink-0 text-tint-fg" />
                    <span>
                      深色模式下所有面板、图表与代码块都会自动换色，无需逐项设置。
                      若页面出现「先白后黑」的闪烁，刷新一次即可（首屏脚本已内置防闪烁）。
                    </span>
                  </div>
                </div>
              </Section>
            )}

            {/* ================= 大模型接入 ================= */}
            {tab === 'model' && (
              <>
                {/* 配置总览 */}
                {cfg && (
                  <div className="card p-4 grid grid-cols-2 lg:grid-cols-4 gap-2.5">
                    <StatusTile
                      icon={IconKey} label="大模型 Key" ok={cfg.api_key_set}
                      value={cfg.api_key_masked || '未配置'}
                      hint={cfg.api_key_set ? '加密存储' : '请在下方填写'}
                    />
                    <StatusTile
                      icon={IconGlobe} label="接入端点" ok={!!cfg.base_url_effective}
                      value={cfg.base_url_effective || '未配置'}
                      hint={cfg.base_url ? '用户级配置' : '服务端 .env 默认'}
                    />
                    <StatusTile
                      icon={IconDatabase} label="向量能力" ok={cfg.embedding_ready}
                      value={cfg.embedding_ready ? '可用' : '不可用'}
                      hint={cfg.embedding_hint}
                    />
                    <StatusTile
                      icon={IconWrench} label="工具密钥" ok={cfg.web_search_ready}
                      value={
                        cfg.web_search_ready
                          ? ([cfg.serper_set && 'Serper', cfg.firecrawl_set && 'FireCrawl']
                              .filter(Boolean).join(' · ') || '服务端 .env')
                          : ([cfg.serper_set && 'Serper', cfg.firecrawl_set && 'FireCrawl']
                              .filter(Boolean).join(' · ') || '未配置')
                      }
                      hint={cfg.web_search_ready ? '联网 / 岗位搜索可用' : '未配置时回落 .env'}
                    />
                  </div>
                )}

                <Section
                  icon={IconZap}
                  title="大模型接入"
                  desc="OpenAI 兼容协议；保存后立即生效，无需重启服务"
                  right={<Badge on={keyOk} tone="info">{keyOk ? '已连接' : '待配置'}</Badge>}
                >
                  <div className="space-y-5">
                    {/* Provider 预设 */}
                    <div>
                      <div className="label">
                        服务商预设 <span className="label-hint">点击可一键填充端点与各角色模型名</span>
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        {BASE_URL_PRESETS.map((p) => {
                          const active = activePreset === p.label;
                          return (
                            <button
                              key={p.label}
                              type="button"
                              onClick={() => { setBaseUrl(p.url); setModels({ ...p.models }); }}
                              className={`text-left px-3 py-2.5 rounded-xl border transition-all duration-200 ease-smooth ${
                                active
                                  ? 'border-brand-300 bg-tint shadow-[0_0_0_3px_rgba(99,102,241,0.08)]'
                                  : 'border-ink-200 bg-surface-0 hover:border-tint-line hover:bg-surface-50'
                              }`}
                            >
                              <div className={`text-[14.5px] font-medium ${active ? 'text-tint-fg' : 'text-ink-700'}`}>
                                {p.label}
                              </div>
                              <div className="text-[12.5px] text-ink-400 mt-0.5 truncate">{p.hint}</div>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* Key */}
                    <div>
                      <label className="label">
                        大模型 API Key <span className="label-hint">AES-GCM 加密存储，不回显明文</span>
                      </label>
                      <div className="relative">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-300">
                          <IconKey size={15} />
                        </span>
                        <input
                          className="input pl-9 font-mono"
                          type="password"
                          autoComplete="off"
                          placeholder={keyOk ? `已配置 ${cfg?.api_key_masked}，留空表示不修改` : 'sk-...'}
                          value={apiKey}
                          onChange={(e) => setApiKey(e.target.value)}
                        />
                      </div>
                    </div>

                    {/* Base URL */}
                    <div>
                      <label className="label">
                        Base URL <span className="label-hint">留空则使用服务端默认端点</span>
                      </label>
                      <input
                        className="input font-mono"
                        placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1"
                        value={baseUrl}
                        onChange={(e) => setBaseUrl(e.target.value)}
                      />
                    </div>

                    {/* 操作 */}
                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      <button className="btn-grad" onClick={saveSvc} disabled={busy}>
                        {busy ? <IconLoader size={15} /> : <IconCheck size={15} />}
                        保存配置
                      </button>
                      <button className="btn-ghost" onClick={testConn} disabled={testing}>
                        {testing ? <IconLoader size={15} /> : <IconZap size={15} />}
                        {testing ? '测试中…' : '测试连接'}
                      </button>
                      <button className="btn-danger ml-auto" onClick={clearAll} disabled={busy}>
                        <IconRefresh size={14} />
                        清除用户级配置
                      </button>
                    </div>

                    {/* 测试结果 */}
                    {testResult && (
                      <div
                        className={`rounded-xl border p-3.5 animate-fade-up ${
                          testResult.ok
                            ? 'border-emerald-200 dark:border-emerald-900/70 bg-emerald-50/70 dark:bg-emerald-950/45'
                            : 'border-rose-200 dark:border-rose-900/70 bg-rose-50/70 dark:bg-rose-950/45'
                        }`}
                      >
                        <div className={`flex items-center gap-2 text-[15px] font-medium ${
                          testResult.ok ? 'text-emerald-800 dark:text-emerald-200' : 'text-rose-700 dark:text-rose-300'
                        }`}>
                          {testResult.ok ? <IconCheckCircle size={15} /> : <IconAlert size={15} />}
                          {testResult.ok
                            ? `连接成功 · 延迟 ${testResult.latency_ms} ms`
                            : '连接失败'}
                        </div>
                        {testResult.ok ? (
                          <div className="mt-2 space-y-1 text-[13.5px] text-emerald-700/90 dark:text-emerald-300 font-mono break-all">
                            <div>模型：{testResult.model || '—'}</div>
                            <div>端点：{testResult.base_url || '—'}</div>
                            {testResult.reply && <div>返回：{testResult.reply}</div>}
                          </div>
                        ) : (
                          <div className="mt-2 text-[13.5px] text-rose-700/90 dark:text-rose-300 break-all leading-relaxed">
                            {testResult.error}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </Section>

                <Section
                  icon={IconLayers}
                  title="模型分层路由"
                  desc="不同角色用不同模型：规划求稳、写作求质、评审异源"
                  right={<span className="text-[13px] text-ink-400">留空 = 使用系统默认</span>}
                >
                  <div className="space-y-2">
                    {LLM_ROLES.map((r) => {
                      const Icon = ROLE_ICON[r.key] || IconSparkles;
                      const overridden = !!(models[r.key] || '').trim();
                      return (
                        <div
                          key={r.key}
                          className="grid grid-cols-1 sm:grid-cols-[190px_1fr] gap-2.5 sm:gap-3 items-center py-2 border-b border-ink-100 last:border-0"
                        >
                          <div className="flex items-start gap-2.5">
                            <span className={`mt-[1px] w-7 h-7 shrink-0 rounded-lg flex items-center justify-center ${
                              overridden ? 'bg-tint text-tint-fg' : 'bg-surface-100 text-ink-400'
                            }`}>
                              <Icon size={14} />
                            </span>
                            <span className="min-w-0">
                              <span className="block text-[14.5px] font-medium text-ink-700">{r.label}</span>
                              <span className="block text-[12.5px] text-ink-400 leading-tight">{r.desc}</span>
                            </span>
                          </div>

                          <div className="flex items-center gap-2">
                            <input
                              className="input input-sm font-mono flex-1"
                              placeholder={cfg?.defaults?.[r.key] || '系统默认'}
                              value={models[r.key] || ''}
                              onChange={(e) => setModels({ ...models, [r.key]: e.target.value })}
                            />
                            <span className="shrink-0 w-[130px] text-right text-[12.5px] text-ink-400">
                              生效
                              <code className="ml-1 font-mono text-ink-600">
                                {cfg?.models?.[r.key] || '-'}
                              </code>
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </Section>

                <Section
                  icon={IconSearch}
                  title="工具服务密钥"
                  desc="岗位检索、联网搜索与网页抓取；未配置时回落服务端 .env"
                  right={
                    <div className="flex gap-1.5">
                      <Badge on={!!cfg?.serper_set || !!cfg?.web_search_ready}>Serper</Badge>
                      <Badge on={!!cfg?.firecrawl_set}>FireCrawl</Badge>
                    </div>
                  }
                >
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="label">Serper API Key <span className="label-hint">岗位 / 联网搜索</span></label>
                      <input
                        className="input font-mono"
                        type="password"
                        autoComplete="off"
                        placeholder={
                          cfg?.serper_set
                            ? `已配置 ${cfg.serper_masked}`
                            : cfg?.web_search_ready
                              ? '当前使用服务端 .env 的 Key'
                              : '留空表示不修改'
                        }
                        value={serper}
                        onChange={(e) => setSerper(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="label">FireCrawl API Key <span className="label-hint">网页抓取</span></label>
                      <input
                        className="input font-mono"
                        type="password"
                        autoComplete="off"
                        placeholder={cfg?.firecrawl_set ? `已配置 ${cfg.firecrawl_masked}` : '留空表示不修改'}
                        value={firecrawl}
                        onChange={(e) => setFirecrawl(e.target.value)}
                      />
                    </div>
                  </div>
                  <button className="btn mt-4" onClick={saveSvc} disabled={busy}>
                    <IconCheck size={15} />
                    保存配置
                  </button>
                </Section>
              </>
            )}

            {/* ================= 求职偏好 ================= */}
            {tab === 'preferences' && (
              <Section
                icon={IconTarget}
                title="求职偏好"
                desc="会沉淀为长期记忆，影响岗位检索与求职信风格"
              >
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {([
                    ['city', '意向城市', '如：北京 / 上海 / 远程'],
                    ['industry', '目标行业', '如：大模型 / 金融科技'],
                    ['salary_range', '期望薪资', '如：30-45K·15薪'],
                    ['work_type', '工作方式', '如：全职 / 实习'],
                  ] as const).map(([k, label, ph]) => (
                    <div key={k}>
                      <label className="label">{label}</label>
                      <input
                        className="input"
                        placeholder={ph}
                        value={(prefs as any)[k] || ''}
                        onChange={(e) => setPrefs({ ...prefs, [k]: e.target.value })}
                      />
                    </div>
                  ))}
                </div>
                <button className="btn mt-4" onClick={savePrefs} disabled={busy}>
                  <IconCheck size={15} />
                  保存偏好
                </button>
              </Section>
            )}
          </div>
        </div>

        <div className="h-2" />
      </div>

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-fade-up">
          <div className={`flex items-start gap-2.5 max-w-lg px-4 py-3 rounded-xl shadow-pop border text-[14.5px] ${
            toast.ok
              ? 'bg-surface-0 border-emerald-200 dark:border-emerald-900/70 text-ink-700'
              : 'bg-surface-0 border-rose-200 dark:border-rose-900/70 text-rose-700 dark:text-rose-300'
          }`}>
            <span className={`mt-[1px] shrink-0 ${toast.ok ? 'text-emerald-500 dark:text-emerald-400' : 'text-rose-500 dark:text-rose-400'}`}>
              {toast.ok ? <IconCheckCircle size={15} /> : <IconAlert size={15} />}
            </span>
            <span className="leading-snug">{toast.text}</span>
            <button className="shrink-0 text-ink-300 hover:text-ink-600 ml-1" onClick={() => setToast(null)}>
              <IconX size={13} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
