'use client';

import { auth } from './auth';
import { API_BASE } from './api';

export interface StreamOptions {
  /** 深度思考：后端把生成类角色切到推理模型，并下发 reasoning_content 作为思考流 */
  deepThinking?: boolean;
  /** 联网搜索：规划阶段强制插入 WebSearcher 步骤 */
  webSearch?: boolean;
  /** 本会话参考简历（仅用户显式上传后才带）：后端校验归属并绑定到会话 */
  resumeId?: number | null;
  /** 用户主动中止 */
  signal?: AbortSignal;
}

export type SSEHandlers = {
  /** 阶段状态：planning / executing / writing … */
  onStatus?: (data: { phase?: string; deep_thinking?: boolean; web_search?: boolean }) => void;
  onPlan?: (data: any) => void;
  onAgentStart?: (data: any) => void;
  onToolCall?: (data: any) => void;
  /** 思考过程增量（reasoning_content） */
  onThinking?: (data: { content: string }) => void;
  /** 思考结束，正式回答开始 */
  onThinkingDone?: (data: { elapsed_ms?: number }) => void;
  /** 正式回答增量 */
  onToken?: (data: { content: string }) => void;
  onCritic?: (data: any) => void;
  onInterrupt?: (data: any) => void;
  onFinal?: (data: any) => void;
  onError?: (data: any) => void;
};

/** 中止异常，调用方可用 isAbort 判断是否需要静默处理 */
export class StreamAborted extends Error {
  constructor() {
    super('已停止生成');
    this.name = 'StreamAborted';
  }
}

export function isAbort(err: unknown): boolean {
  return (
    err instanceof StreamAborted ||
    (err as any)?.name === 'AbortError' ||
    (err as any)?.code === 20
  );
}

/**
 * 会话对话走 SSE（不能用 fetch + JSON）：
 * POST /sessions/{id}/chat，响应 text/event-stream。
 */
export async function streamChat(
  sessionId: string,
  content: string,
  handlers: SSEHandlers,
  opts: StreamOptions = {},
): Promise<void> {
  const { deepThinking = false, webSearch = false, resumeId = null, signal } = opts;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/sessions/${sessionId}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(auth.access ? { Authorization: `Bearer ${auth.access}` } : {}),
      },
      body: JSON.stringify({
        content,
        deep_thinking: deepThinking,
        web_search: webSearch,
        resume_id: resumeId,
      }),
      signal,
    });
  } catch (err) {
    if (isAbort(err)) throw new StreamAborted();
    throw err;
  }

  // 非 200 时不走 SSE：把后端错误包络解析出来，别让它静默丢失
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body?.message || body?.detail?.message || JSON.stringify(body?.detail ?? body);
    } catch {
      /* 非 JSON 响应 */
    }
    if (res.status === 401) detail = '登录状态已失效，请重新登录';
    throw new Error(detail);
  }
  if (!res.body) throw new Error('SSE 连接失败：响应无数据流');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let lastEvent = '';
  let aborted = false;

  const dispatch = (event: string, data: any) => {
    switch (event) {
      case 'status': handlers.onStatus?.(data); break;
      case 'plan': handlers.onPlan?.(data); break;
      case 'agent_start': handlers.onAgentStart?.(data); break;
      case 'tool_call': handlers.onToolCall?.(data); break;
      case 'thinking': handlers.onThinking?.(data); break;
      case 'thinking_done': handlers.onThinkingDone?.(data); break;
      case 'token': handlers.onToken?.(data); break;
      case 'critic': handlers.onCritic?.(data); break;
      case 'interrupt': handlers.onInterrupt?.(data); break;
      case 'final': handlers.onFinal?.(data); break;
      case 'error': handlers.onError?.(data); break;
    }
  };

  try {
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() || '';
      for (const block of blocks) {
        let event = 'message';
        let data = '';
        for (const line of block.split('\n')) {
          if (line.startsWith('event: ')) event = line.slice(7).trim();
          else if (line.startsWith('data: ')) data += line.slice(6);
        }
        if (data) {
          lastEvent = event;
          try {
            dispatch(event, JSON.parse(data));
          } catch {
            /* 单个事件解析失败不影响后续 */
          }
        }
      }
    }
  } catch (err) {
    if (isAbort(err) || signal?.aborted) {
      aborted = true;
    } else {
      throw err;
    }
  }

  if (aborted) {
    handlers.onError?.({ message: '已停止生成', aborted: true });
    throw new StreamAborted();
  }

  // 流结束时若始终没收到终止事件（final / interrupt / error），说明后端提前断开
  if (lastEvent && !['final', 'interrupt', 'error'].includes(lastEvent)) {
    handlers.onError?.({ message: '连接意外中断，请重试（可查看后端日志）' });
  }
}
