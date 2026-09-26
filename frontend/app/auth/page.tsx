'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { auth } from '@/lib/auth';
import {
  IconAlert, IconChat, IconGlobe, IconLoader, IconShield, IconSparkles, Logo,
} from '@/components/icons';

const HIGHLIGHTS = [
  { Icon: IconSparkles, title: '多智能体协作', desc: '规划 / 检索 / 调研 / 撰写 / 质检分工执行' },
  { Icon: IconGlobe, title: '深度思考 + 联网', desc: '可选推理模型与实时检索增强' },
  { Icon: IconShield, title: '隐私自持', desc: '密钥加密存储，模型可自选端点' },
];

export default function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (auth.isAuthed) router.replace('/');
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      if (mode === 'login') {
        const data = await api.login(email, password);
        auth.set(data.access_token, data.refresh_token);
      } else {
        await api.register(email, password, email.split('@')[0]);
        const data = await api.login(email, password);
        auth.set(data.access_token, data.refresh_token);
      }
      router.push('/');
    } catch (err: any) {
      setError(err.message || '操作失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex">
      {/* 左侧品牌区（大屏可见） */}
      <div className="hidden lg:flex lg:w-[46%] relative overflow-hidden bg-night-900 text-white flex-col justify-between p-12 glow-grid">
        <div
          className="absolute -top-24 -left-20 w-[420px] h-[420px] rounded-full opacity-30 blur-3xl"
          style={{ background: 'radial-gradient(circle, #6366f1, transparent 70%)' }}
        />
        <div
          className="absolute -bottom-32 -right-16 w-[380px] h-[380px] rounded-full opacity-25 blur-3xl"
          style={{ background: 'radial-gradient(circle, #a855f7, transparent 70%)' }}
        />

        <div className="relative flex items-center gap-3">
          <Logo size={36} />
          <div className="leading-tight">
            <div className="text-[18px] font-semibold tracking-tight">JobAgent</div>
            <div className="text-[13px] text-white/50">多智能体求职助手 · v2</div>
          </div>
        </div>

        <div className="relative">
          <h1 className="text-[32px] font-semibold leading-snug tracking-tight">
            把求职这件事
            <br />
            交给一支 <span className="gradient-text">Agent 团队</span>
          </h1>
          <p className="mt-4 max-w-sm text-[15px] leading-relaxed text-white/60">
            从简历解析、岗位匹配到求职信撰写与质检，全流程可观测、可介入、可回溯。
          </p>

          <div className="mt-9 space-y-3">
            {HIGHLIGHTS.map(({ Icon, title, desc }) => (
              <div key={title} className="flex items-start gap-3">
                <span className="mt-[2px] w-8 h-8 shrink-0 rounded-xl bg-white/10 border border-white/10 flex items-center justify-center text-brand-300">
                  <Icon size={15} />
                </span>
                <span className="leading-snug">
                  <span className="block text-[14.5px] font-medium">{title}</span>
                  <span className="block text-[13.5px] text-white/45">{desc}</span>
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="relative text-[13px] text-white/35">
          密钥加密存储 · 支持自选模型端点 · 执行轨迹完整记录
        </div>
      </div>

      {/* 右侧表单区 */}
      <div className="flex-1 flex items-center justify-center px-6 py-12 bg-surface-50">
        <div className="w-full max-w-[380px]">
          {/* 小屏品牌 */}
          <div className="lg:hidden flex items-center gap-2.5 mb-7">
            <Logo size={30} />
            <div className="text-[17px] font-semibold tracking-tight text-ink-900">JobAgent</div>
          </div>

          <h2 className="text-[22.5px] font-semibold tracking-tight text-ink-900">
            {mode === 'login' ? '欢迎回来' : '创建账号'}
          </h2>
          <p className="mt-1 text-[14.5px] text-ink-400">
            {mode === 'login' ? '登录后继续你的求职工作台' : '注册后即可上传简历并开始匹配'}
          </p>

          {/* 切换 */}
          <div className="mt-6 grid grid-cols-2 gap-1 p-1 rounded-xl bg-surface-100 border border-ink-100">
            {(['login', 'register'] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => { setMode(m); setError(''); }}
                className={`py-2 rounded-lg text-[14.5px] font-medium transition-all duration-200 ease-smooth ${
                  mode === m
                    ? 'bg-surface-0 text-tint-fg shadow-card'
                    : 'text-ink-500 hover:text-ink-700'
                }`}
              >
                {m === 'login' ? '登录' : '注册'}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="mt-5 space-y-4">
            <div>
              <label className="label">邮箱</label>
              <input
                className="input"
                placeholder="you@example.com"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="label">密码 {mode === 'register' && <span className="label-hint">至少 8 位</span>}</label>
              <input
                className="input"
                placeholder="••••••••"
                type="password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-xl border border-rose-200 dark:border-rose-900/70 bg-rose-50/70 dark:bg-rose-950/45 px-3 py-2.5 text-[14px] text-rose-700 dark:text-rose-300 animate-fade-up">
                <IconAlert size={14} className="mt-[1px] shrink-0" />
                <span className="leading-snug">{error}</span>
              </div>
            )}

            <button className="btn-grad w-full py-2.5" disabled={loading}>
              {loading ? <IconLoader size={15} /> : <IconChat size={15} />}
              {loading ? '处理中…' : mode === 'login' ? '登录' : '注册并登录'}
            </button>
          </form>

          <p className="mt-6 text-[13px] text-center text-ink-400">
            登录即表示你同意本地部署下的数据使用约定
          </p>
        </div>
      </div>
    </main>
  );
}
