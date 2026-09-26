'use client';

/**
 * 会话（对话历史）全局状态。
 *
 * 为什么放全局：历史列表渲染在左侧栏（layout），而消息流在会话工作台（page），
 * 两者需要共享"当前会话"这一状态。用 zustand 避免 props 层层透传。
 *
 * 设计取舍：**不在初始化时自动创建会话**。否则每次打开页面都会多出一条空的
 * 「新会话」垃圾记录；改为首次发送消息时惰性创建（currentId 为空即"草稿态"）。
 */
import { create } from 'zustand';
import { api } from './api';

export interface SessionItem {
  id: string;
  title: string;
  resume_id: number | null;
  created_at: string;
  updated_at: string;
}

interface SessionState {
  sessions: SessionItem[];
  /** 当前会话 id；空字符串表示"新会话草稿"（尚未落库） */
  currentId: string;
  /** 首次加载是否完成（用于避免闪烁） */
  ready: boolean;
  /** 是否有 Agent 正在生成（生成中禁止切换会话） */
  generating: boolean;
  error: string;

  init: () => Promise<void>;
  refresh: () => Promise<void>;
  select: (id: string) => void;
  create: (resumeId?: number | null) => Promise<SessionItem | null>;
  /** 切到"新会话草稿"：不落库，首次发送时才真正创建 */
  startDraft: () => void;
  remove: (id: string) => Promise<void>;
  setGenerating: (v: boolean) => void;
  /** 首条消息发出后本地同步标题，省一次请求 */
  renameLocal: (id: string, title: string) => void;
  reset: () => void;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  sessions: [],
  currentId: '',
  ready: false,
  generating: false,
  error: '',

  async init() {
    try {
      const list = (await api.listSessions()) as SessionItem[];
      set({ sessions: list, currentId: list[0]?.id ?? '', ready: true, error: '' });
    } catch (e: any) {
      // 401 已由 api 层统一跳转登录页，这里只兜底
      set({ ready: true, error: e?.message || '会话列表加载失败' });
    }
  },

  async refresh() {
    try {
      const list = (await api.listSessions()) as SessionItem[];
      const cur = get().currentId;
      const stillThere = list.some((s) => s.id === cur);
      set({
        sessions: list,
        error: '',
        currentId: cur && stillThere ? cur : list[0]?.id ?? '',
      });
    } catch (e: any) {
      set({ error: e?.message || '会话列表刷新失败' });
    }
  },

  select(id) {
    if (get().generating) return; // 生成中不允许切换，避免串台
    set({ currentId: id });
  },

  async create(resumeId?: number | null) {
    try {
      const s = (await api.createSession('新会话', resumeId ?? null)) as SessionItem;
      set((st) => ({ sessions: [s, ...st.sessions], currentId: s.id, error: '' }));
      return s;
    } catch (e: any) {
      set({ error: e?.message || '新建会话失败' });
      return null;
    }
  },

  startDraft() {
    if (get().generating) return; // 生成中不切走，避免结果丢到别的会话
    set({ currentId: '' });
  },

  async remove(id) {
    const backup = get().sessions;
    // 乐观移除，失败再回滚
    set((st) => ({ sessions: st.sessions.filter((s) => s.id !== id) }));
    try {
      await api.deleteSession(id);
      const list = get().sessions;
      if (get().currentId === id) set({ currentId: list[0]?.id ?? '' });
    } catch (e: any) {
      set({ sessions: backup, error: e?.message || '删除会话失败' });
    }
  },

  setGenerating(v) {
    set({ generating: v });
  },

  renameLocal(id, title) {
    set((st) => ({
      sessions: st.sessions.map((s) => (s.id === id ? { ...s, title } : s)),
    }));
  },

  reset() {
    set({ sessions: [], currentId: '', ready: false, generating: false, error: '' });
  },
}));
