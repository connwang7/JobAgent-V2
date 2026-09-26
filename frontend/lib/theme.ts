'use client';

/**
 * 主题（白天 / 夜晚 / 跟随系统）。
 *
 * 实现要点：
 * 1. 只操作 <html> 上的 `dark` class —— 配合 tailwind `darkMode: 'class'`
 *    与 globals.css 里的 CSS 变量，整套配色一次性反转，业务代码不需要写 `dark:`。
 * 2. `system` 模式下监听 matchMedia，用户改系统外观时实时跟随。
 * 3. **防闪烁**：首屏在 <head> 里跑一段内联脚本（见 app/layout.tsx）先把 class 打上，
 *    否则会先渲染浅色再跳深色。这里只负责后续的切换与订阅。
 * 4. 模式值**懒加载自 localStorage**（首个客户端渲染就能拿到正确值），
 *    但 SSR 时 `getServerSnapshot` 仍返回 'system'，避免 hydration 不匹配。
 */

export type ThemeMode = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

const STORAGE_KEY = 'ja-theme';
const MQ = '(prefers-color-scheme: dark)';

/** null = 尚未读取过本地偏好 */
let mode: ThemeMode | null = null;
let listeners = new Set<() => void>();
let mqBound = false;

function readSavedMode(): ThemeMode {
  if (typeof window === 'undefined') return 'system';
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return v === 'light' || v === 'dark' || v === 'system' ? v : 'system';
  } catch {
    // 隐私模式下 localStorage 可能抛异常
    return 'system';
  }
}

/** 当前模式；首次访问时从 localStorage 懒加载 */
function currentMode(): ThemeMode {
  if (mode === null) mode = readSavedMode();
  return mode;
}

function systemTheme(): ResolvedTheme {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia(MQ).matches ? 'dark' : 'light';
}

export function resolveTheme(m: ThemeMode): ResolvedTheme {
  return m === 'system' ? systemTheme() : m;
}

function paint(m: ThemeMode) {
  if (typeof document === 'undefined') return;
  const resolved = resolveTheme(m);
  const root = document.documentElement;
  root.classList.toggle('dark', resolved === 'dark');
  root.dataset.theme = resolved;
  root.style.colorScheme = resolved;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', resolved === 'dark' ? '#0d1117' : '#4f46e5');
}

function emit() {
  listeners.forEach((fn) => fn());
}

function bindSystemListener() {
  if (mqBound || typeof window === 'undefined') return;
  mqBound = true;
  window.matchMedia(MQ).addEventListener('change', () => {
    if (currentMode() !== 'system') return;
    paint('system');
    emit();
  });
}

/** 组件挂载后调用一次：绑定系统监听并把当前模式刷到 DOM 上 */
export function initTheme() {
  bindSystemListener();
  paint(currentMode());
  emit();
}

export function getThemeMode(): ThemeMode {
  return currentMode();
}

export function getResolvedTheme(): ResolvedTheme {
  return resolveTheme(currentMode());
}

export function setThemeMode(next: ThemeMode) {
  mode = next;
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* 存储不可用时仅本次会话生效 */
    }
  }
  paint(next);
  emit();
}

export function subscribeTheme(fn: () => void) {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

/** 给 <head> 内联脚本用的字符串（必须与上面的 key / class 保持一致） */
export const THEME_BOOT_SCRIPT = `(function(){try{var k='${STORAGE_KEY}',m=localStorage.getItem(k);if(m!=='light'&&m!=='dark'&&m!=='system')m='system';var d=m==='dark'||(m==='system'&&window.matchMedia('${MQ}').matches);var e=document.documentElement;if(d){e.classList.add('dark');e.style.colorScheme='dark';e.dataset.theme='dark';}else{e.classList.remove('dark');e.style.colorScheme='light';e.dataset.theme='light';}}catch(_){}})();`;

export const THEME_OPTIONS: { value: ThemeMode; label: string; desc: string }[] = [
  { value: 'light', label: '白天', desc: '始终使用浅色界面' },
  { value: 'dark', label: '夜晚', desc: '始终使用深色界面，适合夜间使用' },
  { value: 'system', label: '跟随系统', desc: '随操作系统的外观设置自动切换' },
];
