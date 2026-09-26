/**
 * 时间格式化。
 *
 * ⚠️ 关键约定：后端返回的 datetime 都是 **不带时区的 UTC**（MySQL 里存 naive UTC，
 * Pydantic 直接 isoformat()，形如 "2026-09-25T13:53:00"，末尾没有 Z 也没有偏移量）。
 * JS 的 `new Date("2026-09-25T13:53:00")` 会把它当**本地时间**解析，
 * 在东八区就会整体差 8 小时（刚建的会话显示成"8 小时前"）。
 * 所以这里统一用 parseServerTime() 处理，不要直接用 new Date(后端时间)。
 */

/** 把后端时间字符串按 UTC 解析（已带时区信息的原样尊重） */
export function parseServerTime(input?: string | null): Date | null {
  if (!input) return null;
  let s = String(input).trim();
  // "2026-09-25 13:53:00" → "2026-09-25T13:53:00"，兼容部分驱动/手写 SQL 的格式
  s = s.replace(' ', 'T');

  const hasTimezone = /(Z|[+-]\d{2}:?\d{2})$/.test(s);
  const d = new Date(hasTimezone ? s : `${s}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** 相对时间：刚刚 / 12 分钟前 / 3 小时前 / 昨天 14:20 / 9-23 */
export function relativeTime(input?: string | null): string {
  const d = parseServerTime(input);
  if (!d) return '';

  const diff = Date.now() - d.getTime();

  // 时钟轻微不同步时，未来时间直接按"刚刚"处理
  if (diff < 60_000) return '刚刚';

  const min = Math.floor(diff / 60_000);
  if (min < 60) return `${min} 分钟前`;

  const hour = Math.floor(min / 60);
  if (hour < 24) return `${hour} 小时前`;

  const hhmm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  const day = Math.floor(hour / 24);
  if (day === 1) return `昨天 ${hhmm}`;
  if (day < 7) return `${day} 天前`;
  return `${d.getMonth() + 1}-${d.getDate()}`;
}

/** 完整本地时间：2026-09-25 21:53 */
export function formatDateTime(input?: string | null): string {
  const d = parseServerTime(input);
  if (!d) return '—';
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** 只到分钟：09-25 21:53 */
export function formatShortDateTime(input?: string | null): string {
  const d = parseServerTime(input);
  if (!d) return '';
  const p = (n: number) => String(n).padStart(2, '0');
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** 时间戳 → HH:MM:SS（执行轨迹用） */
export function clockTime(d: Date = new Date()): string {
  return d.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}
