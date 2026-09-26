'use client';

/** token 存储（access 15min / refresh 7d） */
const ACCESS_KEY = 'jobagent.access';
const REFRESH_KEY = 'jobagent.refresh';
const EMAIL_KEY = 'jobagent.email';

/**
 * 说明：JWT 的 `sub` 是**用户 id**（`str(user.id)`），payload 里没有邮箱，
 * 所以侧栏的用户信息不能从 token 里解。这里缓存一份邮箱做首屏展示，
 * 真值仍以 `GET /me/profile` 为准（见 app/(dashboard)/layout.tsx）。
 */
export const auth = {
  get access() {
    return typeof window === 'undefined' ? null : localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return typeof window === 'undefined' ? null : localStorage.getItem(REFRESH_KEY);
  },
  /** 上次登录/拉取到的邮箱，仅用于避免首屏空白 */
  get emailCache() {
    if (typeof window === 'undefined') return '';
    try {
      return localStorage.getItem(EMAIL_KEY) || '';
    } catch {
      return '';
    }
  },
  set(access: string, refresh: string) {
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  setEmailCache(email: string) {
    try {
      if (email) localStorage.setItem(EMAIL_KEY, email);
      else localStorage.removeItem(EMAIL_KEY);
    } catch {
      /* 隐私模式忽略 */
    }
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(EMAIL_KEY);
  },
  get isAuthed() {
    return Boolean(this.access);
  },
};
