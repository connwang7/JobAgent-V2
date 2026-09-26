/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        /**
         * 语义令牌（全部 CSS 变量驱动，在 globals.css 的 :root / .dark 里给两套值）：
         *   surface.*  背景层级：0=卡片/最上层，50=页面底，100=次级块，200=更深的分隔
         *   ink.*      文字层级：900=主文字 … 300=极弱（分隔线/占位）
         *   tint*      品牌色"淡底"组合：淡底背景 + 淡底边框 + 淡底上的文字/图标
         * 只在这三组上做昼夜反转，brand/accent 保持固定（渐变、实心按钮、图标发光点）。
         */
        surface: {
          0: 'rgb(var(--c-surface-0) / <alpha-value>)',
          50: 'rgb(var(--c-surface-50) / <alpha-value>)',
          100: 'rgb(var(--c-surface-100) / <alpha-value>)',
          200: 'rgb(var(--c-surface-200) / <alpha-value>)',
        },
        ink: {
          50: 'rgb(var(--c-ink-50) / <alpha-value>)',
          100: 'rgb(var(--c-ink-100) / <alpha-value>)',
          200: 'rgb(var(--c-ink-200) / <alpha-value>)',
          300: 'rgb(var(--c-ink-300) / <alpha-value>)',
          400: 'rgb(var(--c-ink-400) / <alpha-value>)',
          500: 'rgb(var(--c-ink-500) / <alpha-value>)',
          600: 'rgb(var(--c-ink-600) / <alpha-value>)',
          700: 'rgb(var(--c-ink-700) / <alpha-value>)',
          800: 'rgb(var(--c-ink-800) / <alpha-value>)',
          900: 'rgb(var(--c-ink-900) / <alpha-value>)',
        },
        tint: {
          DEFAULT: 'rgb(var(--c-tint) / <alpha-value>)',
          2: 'rgb(var(--c-tint-2) / <alpha-value>)',
          line: 'rgb(var(--c-tint-line) / <alpha-value>)',
          fg: 'rgb(var(--c-tint-fg) / <alpha-value>)',
        },

        /* 品牌主色：靛蓝。固定值——渐变、实心按钮、发光点昼夜通用 */
        brand: {
          50: '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
          900: '#312e81',
        },
        /* 辅助色：紫。用于渐变第二色与思考态 */
        accent: {
          50: '#f5f3ff',
          100: '#ede9fe',
          200: '#ddd6fe',
          400: '#a78bfa',
          500: '#8b5cf6',
          600: '#7c3aed',
        },
        /* 永远偏暗的表面（代码块、登录页左栏）——不参与反转 */
        night: {
          700: '#1e293b',
          800: '#131a26',
          900: '#0f172a',
          950: '#0b0f16',
        },
      },
      fontFamily: {
        sans: [
          'Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI',
          'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans SC',
          'Helvetica Neue', 'Arial', 'sans-serif',
        ],
        mono: [
          'ui-monospace', 'SFMono-Regular', 'JetBrains Mono', 'Menlo',
          'Consolas', 'Liberation Mono', 'monospace',
        ],
      },
      borderRadius: {
        xl: '0.75rem',
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
      boxShadow: {
        card: 'var(--shadow-card)',
        pop: 'var(--shadow-pop)',
        glow: '0 6px 20px -6px rgba(99,102,241,0.55)',
        'inner-line': 'var(--shadow-inner-line)',
      },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.45' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        sheen: {
          '0%': { backgroundPosition: '200% center' },
          '100%': { backgroundPosition: '-200% center' },
        },
        'slide-in-right': {
          from: { opacity: '0', transform: 'translateX(8px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        bounceDot: {
          '0%, 80%, 100%': { transform: 'scale(0.6)', opacity: '0.4' },
          '40%': { transform: 'scale(1)', opacity: '1' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.28s cubic-bezier(0.22,1,0.36,1) both',
        'fade-in': 'fade-in 0.2s ease-out both',
        blink: 'blink 1s step-end infinite',
        'pulse-soft': 'pulse-soft 1.6s ease-in-out infinite',
        shimmer: 'shimmer 1.8s infinite',
        sheen: 'sheen 6s linear infinite',
        'slide-in-right': 'slide-in-right 0.25s ease-out both',
        'bounce-dot': 'bounceDot 1.2s infinite both',
      },
      transitionTimingFunction: {
        smooth: 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
    },
  },
  plugins: [],
};
