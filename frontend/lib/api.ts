import { auth } from './auth';

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '/api/v1';

export interface Envelope<T = any> {
  code: string;
  data: T;
  message: string;
}

export class ApiError extends Error {
  constructor(public code: string, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 30000): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  if (auth.access) {
    headers.set('Authorization', `Bearer ${auth.access}`);
  }

  // 所有请求都带超时：后端若被阻塞（历史上 celery publish 会卡 ~108s），
  // 前端至少要能停下来给出提示，而不是永远转圈。
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers, signal: ac.signal });
  } catch (e: any) {
    clearTimeout(timer);
    if (e?.name === 'AbortError') {
      throw new ApiError('HTTP-TIMEOUT', `请求超时（${Math.round(timeoutMs / 1000)} 秒），请稍后重试`);
    }
    throw new ApiError('NETWORK', e?.message || '网络异常，无法连接服务端');
  } finally {
    clearTimeout(timer);
  }

  // 401：token 缺失/过期 → 清掉本地凭证并回登录页，避免各页面弹出"请求失败"
  if (res.status === 401) {
    auth.clear();
    const isAuthPage = typeof window !== 'undefined' && window.location.pathname.startsWith('/auth');
    if (!isAuthPage && typeof window !== 'undefined') {
      window.location.href = '/auth';
    }
    throw new ApiError('AUTH-102', '登录状态已失效，请重新登录');
  }

  let json: Envelope<T>;
  try {
    json = await res.json();
  } catch {
    throw new ApiError(`HTTP-${res.status}`, `服务端返回了非 JSON 响应（HTTP ${res.status}）`);
  }
  if (!res.ok || (json.code && json.code !== 'OK')) {
    throw new ApiError(json.code || `HTTP-${res.status}`, json.message || '请求失败');
  }
  return json.data;
}

export const api = {
  // ---- auth ----
  login: (email: string, password: string) =>
    request<{ user: any; access_token: string; refresh_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  register: (email: string, password: string, nickname: string) =>
    request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, nickname }),
    }),

  // ---- sessions ----
  listSessions: () => request<any[]>('/sessions'),
  /** resumeId：新建会话时即绑定参考简历（用户显式上传的情况） */
  createSession: (title = '新会话', resumeId: number | null = null) =>
    request<any>('/sessions', {
      method: 'POST',
      body: JSON.stringify({ title, resume_id: resumeId }),
    }),
  listMessages: (id: string) => request<any[]>(`/sessions/${id}/messages`),
  /** 关联/取消关联简历中心里的简历（resumeId=null 表示取消关联） */
  bindSessionResume: (id: string, resumeId: number | null) =>
    request<any>(`/sessions/${id}/resume`, {
      method: 'PUT',
      body: JSON.stringify({ resume_id: resumeId }),
    }),
  deleteSession: (id: string) => request(`/sessions/${id}`, { method: 'DELETE' }),

  // ---- runs ----
  approveRun: (runId: string, approved: boolean) =>
    request(`/runs/${runId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved }),
    }),
  trace: (runId: string) => request<any[]>(`/runs/${runId}/trace`),

  // ---- resume ----
  listResumes: () => request<ResumeItem[]>('/resumes'),
  uploadResume: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    // 上传允许多等一会儿：文件最大 10MB
    return request<ResumeItem>('/resumes', { method: 'POST', body: fd }, 120000);
  },
  reparseResume: (id: number) =>
    request<ResumeItem>(`/resumes/${id}/reparse`, { method: 'POST' }),
  resumeProfile: (id: number) => request<any>(`/resumes/${id}/profile`),
  /** 删除单个版本（对象存储 + 时间线 + 记录一起删，不可恢复） */
  deleteResume: (id: number) =>
    request<{ id: number; version: number; object_deleted: boolean }>(`/resumes/${id}`, {
      method: 'DELETE',
    }),
  /** 一键清空全部简历版本（不可恢复，调用方必须先二次确认） */
  clearResumes: () =>
    request<{ deleted: number; objects_deleted: number }>('/resumes', { method: 'DELETE' }),
  /** 版本操作时间线 */
  resumeEvents: (id: number) => request<ResumeTimeline>(`/resumes/${id}/events`),

  // ---- jobs / matches ----
  searchJobs: (keyword: string, location: string) =>
    request<any[]>(`/jobs/search?keyword=${encodeURIComponent(keyword)}&location=${encodeURIComponent(location)}`),
  matches: (resumeId?: number) =>
    request<any[]>(`/jobs/matches${resumeId ? `?resume_id=${resumeId}` : ''}`),

  // ---- letters ----
  listLetters: () => request<any[]>('/letters'),
  confirmLetter: (id: string, approved: boolean) =>
    request(`/letters/${id}/confirm`, {
      method: 'POST',
      body: JSON.stringify({ approved }),
    }),
  downloadUrl: (id: string) => request<{ url: string }>(`/letters/${id}/download`),

  // ---- profile（账号信息） ----
  getProfile: () => request<Profile>('/me/profile'),
  putProfile: (payload: { nickname: string }) =>
    request<{ nickname: string }>('/me/profile', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  changePassword: (oldPassword: string, newPassword: string) =>
    request('/me/password', {
      method: 'POST',
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    }),

  // ---- preferences ----
  getPreferences: () => request<any>('/me/preferences'),
  putPreferences: (payload: any) =>
    request('/me/preferences', { method: 'PUT', body: JSON.stringify(payload) }),

  // ---- LLM / 工具服务配置 ----
  getLLMConfig: () => request<LLMConfig>('/auth/llm-config'),
  putLLMConfig: (payload: LLMConfigPayload) =>
    request<LLMConfig>('/auth/llm-config', { method: 'PUT', body: JSON.stringify(payload) }),
  clearLLMConfig: () =>
    request<LLMConfig>('/auth/llm-config', { method: 'DELETE' }),
  testLLMConfig: () =>
    request<LLMTestResult>('/auth/llm-config/test', { method: 'POST' }),
};

export interface ResumeItem {
  id: number;
  filename: string;
  file_size: number;
  version: number;
  /** pending / parsing / ready / failed */
  status: string;
  error: string;
  /** naive UTC ISO 字符串，前端用 parseServerTime() 解析 */
  created_at: string;
}

export interface ResumeEventItem {
  id: number;
  /** uploaded / reparse_requested / parse_started / parse_succeeded / parse_failed */
  event: string;
  detail: string;
  created_at: string;
}

export interface ResumeTimeline {
  resume_id: number;
  version: number;
  status: string;
  events: ResumeEventItem[];
}

export const LLM_ROLES: { key: string; label: string; desc: string }[] = [
  { key: 'planner', label: 'Planner 规划', desc: '拆解任务 DAG，要求稳定、便宜' },
  { key: 'worker', label: 'Worker 执行', desc: '岗位搜索 / 调研 / 匹配打分' },
  { key: 'writer', label: 'Writer 写作', desc: '求职信等生成类任务，可上更强模型' },
  { key: 'critic', label: 'Critic 评审', desc: '质量把关，建议与生成器异模型' },
  { key: 'thinking', label: '深度思考', desc: '开启「深度思考」时使用的推理模型' },
];

export interface ProfileStats {
  /** 会话数 */
  sessions: number;
  /** 简历数 */
  resumes: number;
  /** 求职信数 */
  letters: number;
  /** 长期记忆条数 */
  memories: number;
}

export interface Profile {
  id: number;
  email: string;
  nickname: string;
  is_active: boolean;
  /** naive UTC ISO 字符串，前端用 parseServerTime() 解析 */
  created_at: string;
  stats: ProfileStats;
}

export interface LLMConfig {
  base_url: string;
  base_url_effective: string;
  model_pref: Record<string, string>;
  models: Record<string, string>;
  defaults: Record<string, string>;
  api_key_set: boolean;
  api_key_masked: string;
  serper_set: boolean;
  serper_masked: string;
  firecrawl_set: boolean;
  firecrawl_masked: string;
  embedding_ready: boolean;
  embedding_hint: string;
  /** 联网搜索/岗位搜索是否可用（含服务端 .env 回落） */
  web_search_ready: boolean;
  web_search_hint: string;
}

export interface LLMConfigPayload {
  api_key?: string;
  base_url?: string;
  model_pref?: Record<string, string>;
  serper_api_key?: string;
  firecrawl_api_key?: string;
  clear_api_key?: boolean;
  clear_serper?: boolean;
  clear_firecrawl?: boolean;
}

export interface LLMTestResult {
  ok: boolean;
  model: string;
  base_url: string;
  latency_ms: number;
  reply: string;
  error: string;
}
