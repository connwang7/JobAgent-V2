'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api } from '@/lib/api';
import { isAbort, streamChat, StreamOptions } from '@/lib/sse';
import { useSessionStore } from '@/lib/store';
import { clockTime } from '@/lib/format';
import PlanView, { PlanStep } from '@/components/plan-view';
import ToolCard from '@/components/tool-card';
import ConfirmCard from '@/components/confirm-card';
import ThinkingBlock from '@/components/thinking-block';
import {
  IconAlert, IconBrain, IconCheck, IconCheckCircle, IconClip, IconClock, IconCopy,
  IconFile, IconGlobe, IconPlus, IconRefresh, IconSend, IconSparkles, IconStop,
  IconTrash, IconUpload, IconWrench, IconX, Logo, agentIcon, agentLabel,
} from '@/components/icons';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  agent_name?: string;
  error?: boolean;
  thinking?: string;
  thinkingSec?: number;
}

interface ToolEvent {
  key: string;
  agent: string;
  tool: string;
  args_digest?: string;
  kind: 'tool' | 'start';
  at: string;
}

const SUGGESTIONS = [
  { icon: '📄', text: '帮我分析简历，看看我适合投什么岗位' },
  { icon: '🎯', text: '找北京的大模型岗位，并针对最匹配的写一封求职信' },
  { icon: '🔍', text: '深度调研这几家公司，给出面试准备建议' },
  { icon: '💬', text: '我的简历投大厂算法岗有戏吗？差在哪里？' },
];

const PHASE_LABEL: Record<string, string> = {
  planning: '规划中',
  executing: '执行中',
  writing: '撰写中',
  reviewing: '质检中',
  done: '已完成',
};

/* ------------------------------------------------------------------ 小组件 */

function CopyButton({ text }: { text: string }) {
  const [ok, setOk] = useState(false);
  return (
    <button
      type="button"
      title="复制"
      className="inline-flex items-center gap-1 text-[12.5px] text-ink-400 transition-colors hover:text-tint-fg"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setOk(true);
          window.setTimeout(() => setOk(false), 1500);
        } catch {
          /* 剪贴板不可用 */
        }
      }}
    >
      {ok ? <IconCheck size={13} /> : <IconCopy size={13} />}
      {ok ? '已复制' : '复制'}
    </button>
  );
}

/** 「模型正在思考」——首个 token 到达前的等待态（DeepSeek 风格） */
function ThinkingIndicator({ phase, label }: { phase: string; label?: string }) {
  const [sec, setSec] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => setSec((s) => s + 1), 1000);
    return () => window.clearInterval(t);
  }, []);

  const phaseText = PHASE_LABEL[phase] || '处理中';
  return (
    <div className="inline-flex items-center gap-2.5 px-4 py-3 rounded-2xl rounded-tl-md border border-ink-200/80 bg-surface-0 shadow-card">
      <span className="relative flex w-4 h-4 items-center justify-center shrink-0">
        <span className="absolute inset-0 rounded-full bg-brand-400/30 animate-ping" />
        <span className="relative w-2 h-2 rounded-full bg-gradient-to-br from-brand-500 to-accent-500" />
      </span>
      <span className="thinking-sheen text-[14.5px] font-medium">模型正在思考</span>
      <span className="flex items-center gap-1" aria-hidden>
        <i className="w-1 h-1 rounded-full bg-ink-300 animate-bounce-dot" />
        <i className="w-1 h-1 rounded-full bg-ink-300 animate-bounce-dot" style={{ animationDelay: '0.15s' }} />
        <i className="w-1 h-1 rounded-full bg-ink-300 animate-bounce-dot" style={{ animationDelay: '0.3s' }} />
      </span>
      <span className="text-[12.5px] text-ink-400 tabular-nums">
        {label ? `${label} · ` : ''}
        {phaseText} · {sec}s
      </span>
    </div>
  );
}

function Avatar({ role, agent }: { role: 'user' | 'assistant'; agent?: string }) {
  if (role === 'user') {
    // 用户头像用固定深色（night-*），避免跟随主题反转后白底白字
    return (
      <span className="w-9 h-9 shrink-0 rounded-xl bg-gradient-to-br from-night-700 to-night-800 text-white text-[13px] font-semibold flex items-center justify-center shadow-card">
        我
      </span>
    );
  }
  const Icon = agent ? agentIcon(agent) : IconSparkles;
  return (
    <span className="w-9 h-9 shrink-0 rounded-xl bg-gradient-to-br from-brand-500 to-accent-500 text-white flex items-center justify-center shadow-glow">
      <Icon size={17} />
    </span>
  );
}

/* ------------------------------------------------------------------ 主页面 */

export default function Workbench() {
  const currentId = useSessionStore((s) => s.currentId);
  const sessions = useSessionStore((s) => s.sessions);

  const [messages, setMessages] = useState<Message[]>([]);
  const [plan, setPlan] = useState<PlanStep[]>([]);
  const [completed, setCompleted] = useState<string[]>([]);
  const [runningAgent, setRunningAgent] = useState('');
  const [tools, setTools] = useState<ToolEvent[]>([]);

  // 流式态
  const [streaming, setStreaming] = useState('');
  const [thinking, setThinking] = useState('');
  const [thinkDone, setThinkDone] = useState(false);

  const [interrupt, setInterrupt] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState('');
  const [input, setInput] = useState('');
  const [model, setModel] = useState('');

  const [deepThinking, setDeepThinking] = useState(false);
  const [webSearch, setWebSearch] = useState(false);
  /** 联网搜索是否真的可用（用户级或服务端配有 Serper Key）；未知时按可用处理，避免误拦 */
  const [webSearchReady, setWebSearchReady] = useState(true);
  const [webSearchHint, setWebSearchHint] = useState('');

  // 参考简历
  const [resume, setResume] = useState<any>(null);
  /** 简历中心里的全部版本（供"选择参考简历"面板展示） */
  const [resumeList, setResumeList] = useState<any[]>([]);
  const [resumeOpen, setResumeOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadSec, setUploadSec] = useState(0);
  const [notice, setNotice] = useState<{ text: string; ok: boolean } | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const seqRef = useRef(0);
  /** 已按 currentId 加载过消息的会话 id，避免"刚建完会话又被清空"的竞态 */
  const loadedIdRef = useRef('');
  /**
   * send() 正在自建会话：zustand 更新 currentId 会立刻触发下面的加载 effect，
   * 其异步 listMessages 会在乐观插入用户消息之后返回空列表把它覆盖
   * （现象：新会话的第一条提问发出去后"被吞掉"看不见）。
   */
  const creatingSessionRef = useRef(false);
  /** 全量简历列表：用于按会话绑定的 resume_id 解析当前要展示的参考简历 */
  const allResumesRef = useRef<any[]>([]);
  /**
   * 本会话里刚上传、但还没随消息绑定到会话的简历 id。
   * 上传到"发第一条消息"之间有个空窗期（后端是在 chat 时才把 resume_id 写到会话上），
   * 没有它的话，中途的状态刷新会按会话的旧 resume_id 把 chip 打回去。
   */
  const pendingResumeRef = useRef<number | null>(null);

  const currentTitle = useMemo(
    () => sessions.find((s) => s.id === currentId)?.title || '',
    [sessions, currentId],
  );

  /* ---------------- 初始化 ---------------- */

  useEffect(() => {
    try {
      setDeepThinking(localStorage.getItem('jobagent.deepThinking') === '1');
      setWebSearch(localStorage.getItem('jobagent.webSearch') === '1');
    } catch {
      /* 忽略隐私模式下的存储异常 */
    }
    api
      .getLLMConfig()
      .then((c) => {
        setModel(c.models?.worker || c.models?.planner || '');
        // 后端已把「用户级 Key 或服务端 .env」合并成 effective 可用性
        if (typeof c.web_search_ready === 'boolean') {
          setWebSearchReady(c.web_search_ready);
          // 之前存的"开"若已不可用，直接落回关闭，避免每次提问都带着一个假开关
          if (!c.web_search_ready) {
            setWebSearch(false);
            try { localStorage.setItem('jobagent.webSearch', '0'); } catch { /* noop */ }
          }
        }
        setWebSearchHint(c.web_search_hint || '');
      })
      .catch(() => {});
  }, []);

  /**
   * 参考简历按**会话**解析：只有本会话显式绑定/刚上传的简历才展示，
   * 不再默认把"账号里最新一份简历"挂在每个新会话上。
   */
  const resolveSessionResume = useCallback(() => {
    const state = useSessionStore.getState();
    const sessionRid = state.sessions.find((s) => s.id === state.currentId)?.resume_id ?? null;
    // 会话已绑定到刚上传的这份 → 交接完成，后续以会话为准
    if (pendingResumeRef.current && sessionRid === pendingResumeRef.current) {
      pendingResumeRef.current = null;
    }
    const rid = pendingResumeRef.current ?? sessionRid;
    setResume(rid ? allResumesRef.current.find((r) => r.id === rid) ?? null : null);
  }, []);

  const loadResume = useCallback(async () => {
    try {
      allResumesRef.current = await api.listResumes();
    } catch {
      allResumesRef.current = [];
    }
    setResumeList(allResumesRef.current);
    resolveSessionResume();
    return allResumesRef.current;
  }, [resolveSessionResume]);

  /** 关联简历中心里已有的某一版（草稿态先暂存，发送时随会话创建一起绑定） */
  const selectResume = useCallback(async (item: any) => {
    setResumeOpen(false);
    const sid = useSessionStore.getState().currentId;
    if (!sid) {
      pendingResumeRef.current = item.id;
      setResume(item);
      return;
    }
    try {
      await api.bindSessionResume(sid, item.id);
      pendingResumeRef.current = null;
      setResume(item);
      await useSessionStore.getState().refresh();
    } catch (err: any) {
      setNotice({ text: err?.message || '关联简历失败', ok: false });
    }
  }, []);

  /** 取消本会话的参考简历关联 */
  const unbindResume = useCallback(async () => {
    setResumeOpen(false);
    pendingResumeRef.current = null;
    const sid = useSessionStore.getState().currentId;
    if (!sid) {
      setResume(null);
      return;
    }
    try {
      await api.bindSessionResume(sid, null);
      setResume(null);
      await useSessionStore.getState().refresh();
    } catch (err: any) {
      setNotice({ text: err?.message || '取消关联失败', ok: false });
    }
  }, []);

  useEffect(() => {
    void loadResume();
  }, [loadResume]);

  // 切换会话 → 清掉"待绑定"的临时简历，再按新会话解析要展示的参考简历
  useEffect(() => {
    pendingResumeRef.current = null;
    resolveSessionResume();
  }, [currentId, resolveSessionResume]);

  // 会话列表刷新（如发送后后端把 resume_id 绑到会话）→ 重新解析
  useEffect(() => {
    resolveSessionResume();
  }, [sessions, resolveSessionResume]);

  // 切换会话 → 加载历史消息
  useEffect(() => {
    if (loadedIdRef.current === currentId) return;
    if (creatingSessionRef.current) return; // send 正在自建会话：由它自己维护消息，勿抢跑覆盖
    loadedIdRef.current = currentId;

    setPlan([]);
    setCompleted([]);
    setTools([]);
    setInterrupt(null);
    setRunningAgent('');

    if (!currentId) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const msgs = await api.listMessages(currentId);
        if (cancelled) return;
        setMessages(
          msgs.map((m: any) => ({
            id: String(m.id),
            role: m.role,
            content: m.content,
            agent_name: m.agent_name,
          })),
        );
      } catch {
        /* 401 已由 api 层统一处理 */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [currentId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' });
  }, [messages, streaming, thinking, tools.length]);

  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [input]);

  useEffect(() => {
    if (!notice) return;
    const t = window.setTimeout(() => setNotice(null), 5000);
    return () => window.clearTimeout(t);
  }, [notice]);

  // 上传期间的等待秒数：让"转圈"变成可感知的进度，而不是无信息等待
  useEffect(() => {
    if (!uploading) {
      setUploadSec(0);
      return;
    }
    const t = window.setInterval(() => setUploadSec((s) => s + 1), 1000);
    return () => window.clearInterval(t);
  }, [uploading]);

  /* ---------------- 附件：上传简历 ---------------- */

  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ''; // 允许重复选中同一个文件
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setNotice({ text: '仅支持 PDF 格式的简历', ok: false });
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setNotice({ text: '文件超过 10MB 限制', ok: false });
      return;
    }

    setUploading(true);
    setNotice(null);
    try {
      const r = await api.uploadResume(file);
      setNotice({
        text: `已上传「${file.name}」（v${r.version}），后台解析中，完成后会自动作为本会话的参考简历`,
        ok: true,
      });
      // 上传后才在输入框上方展示参考简历（本会话级别，不再常驻显示历史简历）
      pendingResumeRef.current = r.id;
      const list = await loadResume();
      setResume(list.find((x: any) => x.id === r.id) ?? r);
      // 解析是后台任务，稍后再刷一次状态；若失败要明确告诉用户原因与补救入口
      window.setTimeout(async () => {
        const latest = await loadResume();
        const item = latest.find((x: any) => x.id === r.id);
        if (item && item.status === 'failed') {
          setNotice({
            text: `上传成功，但解析失败：${item.error || '未知原因'}。到「简历中心」点「重新解析」可重试`,
            ok: false,
          });
        }
      }, 6000);
    } catch (err: any) {
      setNotice({ text: err?.message || '上传失败', ok: false });
    } finally {
      setUploading(false);
    }
  }

  /* ---------------- 发送 ---------------- */

  const send = useCallback(
    async (preset?: string, o?: { appendUser?: boolean }) => {
      const content = (preset ?? input).trim();
      if (!content || busy) return;
      const appendUser = o?.appendUser !== false;

      // 草稿态：首次发送时惰性创建会话，避免历史里堆积空会话
      let sid = currentId;
      if (!sid) {
        creatingSessionRef.current = true; // 告诉加载 effect：这条会话的消息由我自己维护
        const s = await useSessionStore.getState().create(resume?.id ?? null);
        creatingSessionRef.current = false;
        if (!s) {
          setNotice({ text: '新建会话失败，请重试', ok: false });
          return;
        }
        sid = s.id;
        loadedIdRef.current = sid;
      }

      const store = useSessionStore.getState();
      const titleNow = store.sessions.find((s) => s.id === sid)?.title;
      if (!titleNow || titleNow === '新会话') {
        store.renameLocal(sid, content.slice(0, 30));
      }

      setInput('');
      setBusy(true);
      store.setGenerating(true);
      setPhase('planning');
      setPlan([]);
      setCompleted([]);
      setTools([]);
      setStreaming('');
      setThinking('');
      setThinkDone(false);
      setRunningAgent('');

      setMessages((prev) =>
        appendUser ? [...prev, { id: `u-${Date.now()}`, role: 'user', content }] : prev,
      );

      let acc = '';
      let thinkAcc = '';
      let thinkStart = 0;
      let thinkFinished = false;
      let thinkSec = 0;
      let errMsg = '';
      let interrupted = false;
      const planRef: PlanStep[] = [];
      const pushedTools: ToolEvent[] = [];

      const pushAssistant = (text: string, extra: Partial<Message> = {}) =>
        setMessages((prev) => [
          ...prev,
          { id: `a-${Date.now()}-${prev.length}`, role: 'assistant', content: text, ...extra },
        ]);

      const markThinkDone = () => {
        if (thinkFinished) return;
        thinkFinished = true;
        thinkSec = thinkStart ? Math.max(1, Math.round((Date.now() - thinkStart) / 1000)) : 0;
        setThinkDone(true);
      };

      // 参考简历：只在"本会话绑定了简历 / 刚上传"时带上，后端据此绑定到会话
      const opts: StreamOptions = { deepThinking, webSearch, resumeId: resume?.id ?? null };

      try {
        const ac = new AbortController();
        abortRef.current = ac;
        opts.signal = ac.signal;

        await streamChat(
          sid,
          content,
          {
            onStatus: (d) => setPhase(d?.phase || ''),

            onPlan: (d) => {
              planRef.length = 0;
              planRef.push(...(d.steps || []));
              setPlan(d.steps || []);
              setPhase('executing');
            },

            onAgentStart: (d) => {
              setRunningAgent(d.node || '');
              const ev: ToolEvent = {
                key: `t${seqRef.current++}`,
                agent: d.node || '',
                tool: '启动',
                args_digest: d.desc,
                kind: 'start',
                at: clockTime(),
              };
              pushedTools.push(ev);
              setTools((prev) => [...prev, ev]);
            },

            onToolCall: (d) => {
              const ev: ToolEvent = {
                key: `t${seqRef.current++}`,
                agent: d.node || d.agent || '',
                tool: d.tool || 'tool',
                args_digest: d.args_digest,
                kind: 'tool',
                at: clockTime(),
              };
              pushedTools.push(ev);
              setTools((prev) => [...prev, ev]);
            },

            onThinking: (d) => {
              if (!thinkStart) thinkStart = Date.now();
              thinkAcc += d?.content || '';
              setThinking(thinkAcc);
            },

            onThinkingDone: () => markThinkDone(),

            onToken: (d) => {
              if (thinkAcc) markThinkDone();
              acc += d?.content || '';
              setStreaming(acc);
            },

            onInterrupt: (d) => {
              interrupted = true;
              setInterrupt(d);
              setPhase('reviewing');
            },

            onFinal: () => {
              setCompleted(planRef.map((s) => s.id));
              setRunningAgent('');
              setPhase('');
            },

            onError: (d) => {
              if (d?.aborted) return;
              errMsg = d?.message || '未知错误';
            },
          },
          opts,
        );
      } catch (err: any) {
        if (!isAbort(err)) errMsg = errMsg || err?.message || String(err);
      } finally {
        abortRef.current = null;
        setStreaming('');
        setThinking('');
        setThinkDone(false);
        setBusy(false);
        setPhase('');
        setRunningAgent('');
        useSessionStore.getState().setGenerating(false);
      }

      if (!thinkFinished && thinkAcc) {
        thinkFinished = true;
        thinkSec = thinkStart ? Math.max(1, Math.round((Date.now() - thinkStart) / 1000)) : 0;
      }

      const blocks: string[] = [];
      if (acc.trim()) blocks.push(acc.trim());
      if (errMsg) {
        blocks.push(
          `⚠️ **执行失败**\n\n\`${errMsg.replace(/\n/g, ' ').slice(0, 400)}\`\n\n` +
            '> 请到左下角「设置 → 大模型接入」检查 API Key、Base URL 与模型名，' +
            '点「测试连接」确认可用后重试。',
        );
      }
      if (!blocks.length && !interrupted) {
        blocks.push('（本轮没有返回可展示的文本，请重试；可查看右侧执行轨迹或后端日志）');
      }

      if (blocks.length) {
        pushAssistant(blocks.join('\n\n'), {
          error: !!errMsg,
          thinking: thinkAcc || undefined,
          thinkingSec: thinkSec || undefined,
        });
      }

      // 同步标题与排序（后端会用首条消息重写 title）
      void useSessionStore.getState().refresh();
    },
    [input, busy, currentId, deepThinking, webSearch, resume],
  );

  const stop = () => abortRef.current?.abort();

  /** 重新生成：丢掉这条回答，用上一条用户提问重跑（不重复插入用户消息） */
  const regenerate = useCallback(
    (assistantIdx: number) => {
      if (busy) return;
      let content = '';
      for (let i = assistantIdx - 1; i >= 0; i -= 1) {
        if (messages[i]?.role === 'user') {
          content = messages[i].content;
          break;
        }
      }
      if (!content) return;
      setMessages((prev) => prev.slice(0, assistantIdx));
      setInterrupt(null);
      void send(content, { appendUser: false });
    },
    [busy, messages, send],
  );

  /** 新建会话：只切到草稿态，不立刻建库（避免历史里堆空记录） */
  const newSession = () => {
    if (busy) return;
    setNotice(null);
    useSessionStore.getState().startDraft();
    taRef.current?.focus();
  };

  /** 打开/收起「选择参考简历」；打开时顺手刷新列表，保证能看到简历中心刚上传的版本 */
  const toggleResumePicker = () => {
    if (!resumeOpen) void loadResume();
    setResumeOpen(!resumeOpen);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      send();
    }
  };

  const toggle = (which: 'deep' | 'web') => {
    if (which === 'deep') {
      const v = !deepThinking;
      setDeepThinking(v);
      try { localStorage.setItem('jobagent.deepThinking', v ? '1' : '0'); } catch { /* noop */ }
    } else {
      const v = !webSearch;
      // 没有可用的搜索密钥就明确告知，而不是点亮开关后静默不检索
      if (v && !webSearchReady) {
        setNotice({
          ok: false,
          text: webSearchHint || '未配置 Serper API Key，联网搜索不可用；到 设置 → 工具密钥 填入后生效。',
        });
        return;
      }
      setWebSearch(v);
      try { localStorage.setItem('jobagent.webSearch', v ? '1' : '0'); } catch { /* noop */ }
    }
  };

  const railTools = useMemo(() => [...tools].reverse(), [tools]);
  /** 生成期间始终显示实时行：即便还没吐字，也要让用户看到「模型正在思考」 */
  const liveVisible = busy;
  const isEmpty = messages.length === 0 && !liveVisible && !plan.length && !interrupt;
  /** 最后一条助手回答的下标（只有它显示「重新生成」） */
  const lastAssistantIdx = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].role === 'assistant') return i;
    }
    return -1;
  }, [messages]);

  return (
    <div className="flex h-full">
      {/* ==================== 对话主区 ==================== */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* 头部 */}
        <header className="h-[68px] shrink-0 px-6 flex items-center gap-3 border-b border-ink-200/80 bg-surface-0/80 backdrop-blur">
          <div className="min-w-0">
            <h1 className="text-[16.5px] font-semibold text-ink-900 tracking-tight flex items-center gap-2">
              会话工作台
              {busy && (
                <span className="badge badge-info">
                  <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse-soft" />
                  {PHASE_LABEL[phase] || '处理中'}
                </span>
              )}
            </h1>
            <p className="text-[12.5px] text-ink-400 truncate">
              {currentTitle ? `当前会话：${currentTitle}` : '新会话 · 发送消息后自动保存到左侧历史'}
            </p>
          </div>

          <div className="ml-auto flex items-center gap-2 shrink-0">
            {model && (
              <span className="hidden lg:inline-flex badge badge-off font-mono" title="当前生效模型">
                {model}
              </span>
            )}
            <button className="btn-ghost" onClick={newSession} disabled={busy}>
              <IconPlus size={16} />
              新建会话
            </button>
          </div>
        </header>

        {/* 消息流 */}
        <div className="flex-1 overflow-y-auto">
          {isEmpty ? (
            <div className="min-h-full flex items-center justify-center px-8 py-10">
              <EmptyState onPick={send} />
            </div>
          ) : (
            <div className="mx-auto w-full max-w-[960px] px-7 py-6 space-y-6">
              {plan.length > 0 && (
                <PlanView steps={plan} completed={completed} running={runningAgent} />
              )}

              {messages.map((m, i) => (
                <MessageRow
                  key={m.id}
                  msg={m}
                  isLast={i === lastAssistantIdx}
                  busy={busy}
                  onRegenerate={() => regenerate(i)}
                />
              ))}

              {/* 实时流：思考块 + 正文；还没吐字时显示「模型正在思考」 */}
              {liveVisible && (
                <div className="flex gap-3 animate-fade-up">
                  <Avatar role="assistant" agent={runningAgent} />
                  <div className="min-w-0 flex-1">
                    {thinking && <ThinkingBlock text={thinking} done={thinkDone} />}
                    {streaming ? (
                      <div className="md">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{streaming}</ReactMarkdown>
                        <span className="caret" />
                      </div>
                    ) : !thinking ? (
                      <ThinkingIndicator phase={phase} label={runningAgent ? agentLabel(runningAgent) : undefined} />
                    ) : null}
                  </div>
                </div>
              )}

              {interrupt && (
                <ConfirmCard
                  payload={interrupt}
                  onResolved={(approved) => {
                    setInterrupt(null);
                    setMessages((prev) => [
                      ...prev,
                      {
                        id: `a-hitl-${Date.now()}`,
                        role: 'assistant',
                        agent_name: 'HITL',
                        content: approved
                          ? '✅ 求职信已确认，正在生成 Word 文档，可到「求职信管理」下载。'
                          : '已按你的要求放弃本次求职信草稿。',
                      },
                    ]);
                  }}
                />
              )}

              <div ref={bottomRef} className="h-1" />
            </div>
          )}
        </div>

        {/* 输入区 */}
        <div className="shrink-0 border-t border-ink-200/80 bg-surface-0/80 backdrop-blur px-7 py-4">
          <div className="mx-auto w-full max-w-[960px]">
            {/* 提示条 */}
            {notice && (
              <div
                className={`mb-2.5 flex items-start gap-2 rounded-xl border px-3.5 py-2.5 text-[13px] animate-fade-up ${
                  notice.ok
                    ? 'border-tint-line bg-tint/70 text-tint-fg'
                    : 'border-rose-200 dark:border-rose-900/70 bg-rose-50/70 dark:bg-rose-950/45 text-rose-700 dark:text-rose-300'
                }`}
              >
                {notice.ok ? (
                  <IconCheckCircle size={15} className="mt-[1px] shrink-0" />
                ) : (
                  <IconAlert size={15} className="mt-[1px] shrink-0" />
                )}
                <span className="leading-snug">{notice.text}</span>
              </div>
            )}

            <div className="relative rounded-2xl border border-ink-200 bg-surface-0 shadow-card transition-all duration-200 ease-smooth focus-within:border-brand-300 focus-within:ring-4 focus-within:ring-brand-500/10">
              {/* 选择参考简历：关联简历中心已有版本 / 上传新的 PDF */}
              {resumeOpen && (
                <ResumePicker
                  resumes={resumeList}
                  currentResumeId={resume?.id ?? null}
                  onPick={selectResume}
                  onUpload={() => {
                    setResumeOpen(false);
                    fileRef.current?.click();
                  }}
                  onUnbind={unbindResume}
                  onClose={() => setResumeOpen(false)}
                />
              )}

              {/* 参考简历 / 上传进度（二选一，避免叠罗汉） */}
              {uploading ? (
                <div className="flex items-center gap-2 px-3.5 pt-2.5 text-[12.5px] text-ink-400">
                  <span className="shrink-0 block w-3 h-3 rounded-full border-2 border-brand-400 border-t-transparent animate-spin" />
                  <span className="truncate">
                    正在上传并提交解析…已等待 {uploadSec} 秒
                  </span>
                </div>
              ) : resume ? (
                <div className="flex items-center gap-1.5 px-3.5 pt-2.5 text-[12.5px] text-ink-400">
                  <IconFile size={13} className="shrink-0" />
                  <span className="truncate">
                    参考简历 v{resume.version} · {resume.filename}
                  </span>
                  {resume.status !== 'ready' && (
                    <span
                      className={`shrink-0 ${
                        resume.status === 'failed'
                          ? 'text-rose-600 dark:text-rose-300'
                          : 'text-amber-600 dark:text-amber-300'
                      }`}
                      title={resume.error || undefined}
                    >
                      （{resume.status === 'failed' ? '解析失败' : '解析中'}）
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={toggleResumePicker}
                    className="ml-auto shrink-0 text-ink-400 transition-colors hover:text-tint-fg"
                  >
                    更换
                  </button>
                  <button
                    type="button"
                    onClick={unbindResume}
                    className="shrink-0 text-ink-400 transition-colors hover:text-rose-600 dark:hover:text-rose-300"
                    title="取消本会话的简历关联"
                  >
                    移除
                  </button>
                </div>
              ) : !resume && messages.length === 0 && resumeList.some((r) => r.status === 'ready') ? (
                // 空会话时提示"简历中心有现成的可以关联"，避免用户以为只能重新上传
                <div className="flex items-center gap-1.5 px-3.5 pt-2.5 text-[12.5px] text-ink-400">
                  <IconFile size={13} className="shrink-0" />
                  <span className="truncate">
                    本会话未关联简历 · 简历中心有{' '}
                    {resumeList.filter((r) => r.status === 'ready').length} 份已就绪
                  </span>
                  <button
                    type="button"
                    onClick={toggleResumePicker}
                    className="ml-auto shrink-0 text-ink-400 transition-colors hover:text-tint-fg"
                  >
                    去关联
                  </button>
                </div>
              ) : null}

              <div className="flex items-end gap-2 px-3 py-2.5">
                {/* 上传简历 */}
                <input
                  ref={fileRef}
                  type="file"
                  accept="application/pdf"
                  className="hidden"
                  onChange={onPickFile}
                />
                <button
                  type="button"
                  title="选择参考简历：关联「简历中心」已有版本，或上传新的 PDF"
                  onClick={toggleResumePicker}
                  disabled={uploading || busy}
                  className={`shrink-0 mb-0.5 w-9 h-9 rounded-xl flex items-center justify-center transition-colors disabled:opacity-50 disabled:pointer-events-none ${
                    resume ? 'text-brand-500 hover:bg-surface-100' : 'text-ink-400 hover:bg-surface-100 hover:text-tint-fg'
                  }`}
                >
                  {uploading ? (
                    <span className="block w-4 h-4 rounded-full border-2 border-brand-400 border-t-transparent animate-spin" />
                  ) : (
                    <IconClip size={18} />
                  )}
                </button>

                <textarea
                  ref={taRef}
                  rows={1}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={onKeyDown}
                  disabled={busy}
                  placeholder="描述你的求职目标，例如：帮我找北京的大模型岗位，并针对最匹配的写求职信"
                  className="flex-1 resize-none bg-transparent text-[15.5px] leading-7 text-ink-800 placeholder:text-ink-400 outline-none py-1.5 max-h-52 disabled:opacity-60"
                />

                {busy ? (
                  <button
                    className="shrink-0 w-10 h-10 rounded-xl bg-night-800 text-white flex items-center justify-center hover:bg-night-900 transition-colors"
                    onClick={stop}
                    title="停止生成"
                  >
                    <IconStop size={17} />
                  </button>
                ) : (
                  <button
                    className="shrink-0 w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-accent-500 text-white flex items-center justify-center shadow-glow transition-all hover:brightness-110 active:scale-95 disabled:opacity-40 disabled:shadow-none disabled:pointer-events-none"
                    onClick={() => send()}
                    disabled={!input.trim()}
                    title="发送（Enter）"
                  >
                    <IconSend size={18} />
                  </button>
                )}
              </div>

              {/* 开关行 */}
              <div className="flex items-center gap-2 px-3.5 pb-3 pt-0.5">
                <button
                  type="button"
                  className={`chip ${deepThinking ? 'chip-active' : ''}`}
                  onClick={() => toggle('deep')}
                  disabled={busy}
                  title="切换到推理模型，输出思考过程后再给结论"
                >
                  <IconBrain size={15} />
                  深度思考
                </button>
                <button
                  type="button"
                  className={`chip ${webSearch ? 'chip-active' : ''} ${!webSearchReady ? 'opacity-60' : ''}`}
                  onClick={() => toggle('web')}
                  disabled={busy}
                  title={
                    webSearchReady
                      ? '规划阶段强制加入联网检索步骤'
                      : '不可用：未配置 Serper API Key（设置 → 工具密钥）'
                  }
                >
                  <IconGlobe size={15} />
                  联网搜索
                  {!webSearchReady && <span className="text-[11px]">·未配置</span>}
                </button>
                <span className="ml-auto hidden sm:block text-[12.5px] text-ink-300">
                  Enter 发送 · Shift + Enter 换行
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ==================== 执行轨迹 ==================== */}
      <aside className="hidden xl:flex w-[288px] shrink-0 flex-col border-l border-ink-200/80 bg-surface-0">
        <div className="h-[68px] shrink-0 px-4 flex items-center gap-2 border-b border-ink-200/80">
          <span className="w-7 h-7 rounded-lg bg-surface-100 text-ink-500 flex items-center justify-center">
            <IconWrench size={15} />
          </span>
          <span className="section-title">执行轨迹</span>
          <span className="ml-auto badge badge-off tabular-nums">{tools.length}</span>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {railTools.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center px-6 py-10">
              <span className="w-12 h-12 rounded-2xl bg-surface-100 text-ink-300 flex items-center justify-center mb-3">
                <IconClock size={21} />
              </span>
              <p className="text-[13px] text-ink-400 leading-relaxed">
                还没有执行记录
                <br />
                发送一条消息后，这里会显示各节点的工具调用
              </p>
            </div>
          )}
          {railTools.map((t) => (
            <ToolCard
              key={t.key}
              agent={t.agent}
              tool={t.tool}
              argsDigest={t.args_digest}
              at={t.at}
              kind={t.kind}
            />
          ))}
        </div>
      </aside>
    </div>
  );
}

/* ------------------------------------------------------------------ 子组件 */

function MessageRow({ msg, isLast, busy, onRegenerate }: {
  msg: Message;
  isLast: boolean;
  busy: boolean;
  onRegenerate: () => void;
}) {
  const isUser = msg.role === 'user';
  const canRegenerate = !isUser && isLast && !busy;
  return (
    <div className={`group flex gap-3 animate-fade-up ${isUser ? 'flex-row-reverse' : ''}`}>
      <Avatar role={msg.role} agent={msg.agent_name} />

      <div className={`min-w-0 max-w-[86%] flex flex-col ${isUser ? 'items-end' : ''}`}>
        {!isUser && msg.agent_name && (
          <span className="mb-1 text-[12.5px] font-medium text-ink-400">
            {agentLabel(msg.agent_name)}
          </span>
        )}

        {msg.thinking && (
          <div className="w-full">
            <ThinkingBlock
              text={msg.thinking}
              done
              elapsedMs={msg.thinkingSec ? msg.thinkingSec * 1000 : undefined}
            />
          </div>
        )}

        {isUser ? (
          <div className="px-4 py-2.5 rounded-2xl rounded-tr-md bg-gradient-to-br from-brand-500 to-accent-500 text-white text-[15.5px] leading-relaxed shadow-glow whitespace-pre-wrap break-words">
            {msg.content}
          </div>
        ) : (
          <div
            className={`w-full px-4 py-3 rounded-2xl rounded-tl-md border ${
              msg.error
                ? 'border-rose-200 dark:border-rose-900/70 bg-rose-50/60 dark:bg-rose-950/40'
                : 'border-ink-200/80 bg-surface-0 shadow-card'
            }`}
          >
            <div className="md">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* 操作栏：默认淡出，hover 或「最后一条回答」时常显 */}
        <div
          className={`mt-1 flex items-center gap-3 ${isUser ? 'justify-end' : ''} transition-opacity duration-150 ${
            isUser || isLast ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
          }`}
        >
          {!isUser && msg.error && (
            <span className="inline-flex items-center gap-1 text-[12.5px] text-rose-500 dark:text-rose-400">
              <IconAlert size={12} /> 执行异常
            </span>
          )}
          {!isUser && <CopyButton text={msg.content} />}
          {canRegenerate && (
            <button
              type="button"
              title="用上一条提问重新生成"
              onClick={onRegenerate}
              className="inline-flex items-center gap-1 text-[12.5px] text-ink-400 transition-colors hover:text-tint-fg"
            >
              <IconRefresh size={13} />
              重新生成
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/** 「选择参考简历」面板：关联简历中心已有版本，或上传新的 PDF */
function ResumePicker({
  resumes, currentResumeId, onPick, onUpload, onUnbind, onClose,
}: {
  resumes: any[];
  currentResumeId: number | null;
  onPick: (item: any) => void;
  onUpload: () => void;
  onUnbind: () => void;
  onClose: () => void;
}) {
  return (
    <>
      {/* 点击空白处关闭 */}
      <div className="fixed inset-0 z-30" onClick={onClose} />
      <div className="absolute bottom-[calc(100%+8px)] left-0 z-40 w-[368px] overflow-hidden rounded-2xl border border-ink-200 bg-surface-0 shadow-pop animate-fade-up">
        <div className="flex items-center gap-2 border-b border-ink-200/80 px-3.5 py-2.5">
          <IconFile size={14} className="text-ink-400" />
          <span className="text-[13px] font-medium text-ink-700">选择参考简历</span>
          <button
            type="button"
            onClick={onClose}
            className="ml-auto text-ink-400 transition-colors hover:text-tint-fg"
            title="关闭"
          >
            <IconX size={14} />
          </button>
        </div>

        <div className="max-h-[248px] overflow-y-auto py-1">
          {resumes.length === 0 ? (
            <p className="px-3.5 py-4 text-[12.5px] leading-relaxed text-ink-400">
              简历中心还没有简历。先上传一份 PDF，解析完成后就能在这里选择关联。
            </p>
          ) : (
            resumes.map((r) => {
              const active = currentResumeId === r.id;
              return (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => onPick(r)}
                  className={`flex w-full items-start gap-2.5 px-3.5 py-2 text-left transition-colors hover:bg-surface-100 ${
                    active ? 'bg-surface-100' : ''
                  }`}
                >
                  <span
                    className={`mt-[6px] h-1.5 w-1.5 shrink-0 rounded-full ${
                      r.status === 'ready'
                        ? 'bg-brand-500'
                        : r.status === 'failed'
                          ? 'bg-rose-500'
                          : 'bg-amber-400'
                    }`}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] text-ink-700">
                      v{r.version} · {r.filename}
                    </span>
                    <span className="block truncate text-[11.5px] text-ink-400">
                      {r.status === 'ready'
                        ? '已就绪，可直接分析'
                        : r.status === 'failed'
                          ? `解析失败：${(r.error || '未知原因').slice(0, 24)}`
                          : '解析中，完成后可用'}
                    </span>
                  </span>
                  {active && <IconCheck size={14} className="mt-[3px] shrink-0 text-brand-500" />}
                </button>
              );
            })
          )}
        </div>

        <div className="border-t border-ink-200/80 py-1">
          <button
            type="button"
            onClick={onUpload}
            className="flex w-full items-center gap-2 px-3.5 py-2 text-left text-[13px] text-ink-600 transition-colors hover:bg-surface-100"
          >
            <IconUpload size={14} />
            上传新的 PDF…
          </button>
          {currentResumeId !== null && (
            <button
              type="button"
              onClick={onUnbind}
              className="flex w-full items-center gap-2 px-3.5 py-2 text-left text-[13px] text-rose-600 transition-colors hover:bg-surface-100 dark:text-rose-300"
            >
              <IconTrash size={14} />
              取消本会话的关联
            </button>
          )}
        </div>
      </div>
    </>
  );
}

function EmptyState({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="w-full flex flex-col items-center text-center animate-fade-up">
      <div className="relative mb-6">
        <div className="absolute inset-0 blur-2xl opacity-40 bg-gradient-to-br from-brand-400 to-accent-500 rounded-full scale-125" />
        <Logo size={64} className="relative drop-shadow-[0_6px_16px_rgba(99,102,241,0.4)]" />
      </div>

      <h2 className="text-[23px] font-semibold tracking-tight text-ink-900">
        开始你的 <span className="gradient-text">多智能体求职</span> 之旅
      </h2>
      <p className="mt-2.5 max-w-2xl text-[14.5px] text-ink-400 leading-relaxed">
        规划、检索、调研、撰写、质检由不同 Agent 协作完成；开启「深度思考」可以看到模型的推理过程。
      </p>

      <div className="mt-9 grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-3xl">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.text}
            onClick={() => onPick(s.text)}
            className="group flex items-start gap-3 px-4 py-3.5 rounded-2xl border border-ink-200/80 bg-surface-0 text-left transition-all duration-200 ease-smooth hover:border-brand-300 hover:shadow-pop hover:-translate-y-[1px]"
          >
            <span className="text-[17px] leading-none mt-[2px]">{s.icon}</span>
            <span className="text-[14px] text-ink-600 leading-snug group-hover:text-ink-800">
              {s.text}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
