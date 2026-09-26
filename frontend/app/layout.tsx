import type { Metadata, Viewport } from 'next';
import { THEME_BOOT_SCRIPT } from '@/lib/theme';
import './globals.css';

export const metadata: Metadata = {
  title: 'JobAgent · 多智能体求职助手',
  description: '多智能体求职助手：简历解析、岗位匹配、求职信撰写与质检，全过程可观测。',
};

export const viewport: Viewport = {
  themeColor: '#4f46e5',
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning：首屏内联脚本会在 hydration 前改写 <html> 的
    // class / color-scheme / data-theme，属预期行为，不该报 hydration 不匹配。
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        {/* 防主题闪烁：必须在任何样式生效前把 dark class 打上 */}
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      </head>
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
