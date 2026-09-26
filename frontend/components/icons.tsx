'use client';

/**
 * 内联 SVG 图标集。
 *
 * 设计约定：
 * - 24×24 视觉栅格、线性描边（stroke 1.7）、round 端点，和圆角卡片语言一致；
 * - 一律继承 `currentColor`，因此颜色由外层文字色控制，不需要传色值；
 * - 默认 18px，正文用 16，导航用 19，按钮用 16。
 */
import * as React from 'react';

type IconProps = React.SVGProps<SVGSVGElement> & { size?: number };

function Svg({ size = 18, children, ...rest }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

/* ------------------------------------------------------------------ 品牌 */

/** 品牌标记：渐变圆角方块 + 「A」字形 + 亮点 */
export function Logo({ size = 32, className = '' }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="logo-grad" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#6366f1" />
          <stop offset="0.55" stopColor="#7c3aed" />
          <stop offset="1" stopColor="#a855f7" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#logo-grad)" />
      <path
        d="M8.8 22.4 16 9.6l7.2 12.8"
        fill="none"
        stroke="#fff"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="16" cy="18.4" r="1.95" fill="#fff" />
    </svg>
  );
}

/* -------------------------------------------------------------- 导航图标 */

export const IconChat = (p: IconProps) => (
  <Svg {...p}>
    <path d="M20.5 12.4c0 4.1-3.7 7.4-8.2 7.4-.9 0-1.8-.1-2.6-.4l-4.4 1.7 1.3-3.7A7 7 0 0 1 4.1 12.4C4.1 8.3 7.8 5 12.3 5s8.2 3.3 8.2 7.4Z" />
  </Svg>
);

export const IconFile = (p: IconProps) => (
  <Svg {...p}>
    <path d="M14 3H7.5A1.5 1.5 0 0 0 6 4.5v15A1.5 1.5 0 0 0 7.5 21h9a1.5 1.5 0 0 0 1.5-1.5V7l-4-4Z" />
    <path d="M13.8 3.2V7H18" />
    <path d="M9 12.5h6M9 16h4" />
  </Svg>
);

export const IconBriefcase = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3" y="7.5" width="18" height="12" rx="2.2" />
    <path d="M9 7.5V6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1.5" />
    <path d="M3 12.5h18" />
    <path d="M11 12.5h2v2h-2z" />
  </Svg>
);

export const IconMail = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3" y="5.5" width="18" height="13" rx="2.2" />
    <path d="m4 7.5 7.1 5a1.6 1.6 0 0 0 1.9 0l7.1-5" />
  </Svg>
);

export const IconSettings = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="3.1" />
    <path d="M19.3 14.4a1.5 1.5 0 0 0 .3 1.7l.1.1a1.9 1.9 0 1 1-2.7 2.7l-.1-.1a1.5 1.5 0 0 0-1.7-.3 1.5 1.5 0 0 0-.9 1.4v.3a1.9 1.9 0 1 1-3.8 0v-.2a1.5 1.5 0 0 0-1-1.4 1.5 1.5 0 0 0-1.7.3l-.1.1a1.9 1.9 0 1 1-2.7-2.7l.1-.1a1.5 1.5 0 0 0 .3-1.7 1.5 1.5 0 0 0-1.4-.9H3.6a1.9 1.9 0 1 1 0-3.8h.2a1.5 1.5 0 0 0 1.4-1 1.5 1.5 0 0 0-.3-1.7l-.1-.1a1.9 1.9 0 1 1 2.7-2.7l.1.1a1.5 1.5 0 0 0 1.7.3h.1a1.5 1.5 0 0 0 .9-1.4V3.6a1.9 1.9 0 1 1 3.8 0v.2a1.5 1.5 0 0 0 .9 1.4 1.5 1.5 0 0 0 1.7-.3l.1-.1a1.9 1.9 0 1 1 2.7 2.7l-.1.1a1.5 1.5 0 0 0-.3 1.7v.1a1.5 1.5 0 0 0 1.4.9h.3a1.9 1.9 0 1 1 0 3.8h-.2a1.5 1.5 0 0 0-1.4.9Z" />
  </Svg>
);

/* ---------------------------------------------------------- 会话 / 智能体 */

/** 思考：大脑 + 火花，用于「深度思考」与思考块 */
export const IconBrain = (p: IconProps) => (
  <Svg {...p}>
    <path d="M9.6 4.2A2.6 2.6 0 0 0 7 6.8v.4A2.9 2.9 0 0 0 5 9.9c0 1 .5 2 1.3 2.5A2.9 2.9 0 0 0 5.2 15c0 1.4 1 2.6 2.3 2.9v.3a2.6 2.6 0 0 0 5.2 0V6.8a2.6 2.6 0 0 0-3.1-2.6Z" />
    <path d="M14.4 4.2A2.6 2.6 0 0 1 17 6.8v.4a2.9 2.9 0 0 1 2 2.7c0 1-.5 2-1.3 2.5a2.9 2.9 0 0 1 1.1 2.6c0 1.4-1 2.6-2.3 2.9v.3a2.6 2.6 0 0 1-5.2 0" />
    <path d="M8.4 10.2h1.4M14 10.2h1.4M8.8 14.4h1.2M14.2 14.4h1.2" />
  </Svg>
);

/** 联网搜索 */
export const IconGlobe = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.2" />
    <path d="M3.8 12h16.4" />
    <path d="M12 3.8c2.2 2.2 3.3 5.1 3.3 8.2S14.2 18 12 20.2C9.8 18 8.7 15.1 8.7 12S9.8 6 12 3.8Z" />
  </Svg>
);

export const IconSearch = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="11" cy="11" r="6.4" />
    <path d="m15.8 15.8 3.7 3.7" />
  </Svg>
);

/** 工具调用 */
export const IconWrench = (p: IconProps) => (
  <Svg {...p}>
    <path d="M14.6 6.2a3.9 3.9 0 0 1 5.2-3.6l-2.6 2.6 1.6 1.6 2.6-2.6a3.9 3.9 0 0 1-4.9 4.9L6.9 19.7a2 2 0 1 1-2.8-2.8L13.9 7l.7-.8Z" />
  </Svg>
);

/** 规划 / 目标 */
export const IconTarget = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="7.8" />
    <circle cx="12" cy="12" r="3.9" />
    <circle cx="12" cy="12" r="0.9" fill="currentColor" stroke="none" />
  </Svg>
);

/** 调度 / 分层 */
export const IconLayers = (p: IconProps) => (
  <Svg {...p}>
    <path d="m12 3.6 8 4.2-8 4.2-8-4.2 8-4.2Z" />
    <path d="m4 12.4 8 4.2 8-4.2" />
    <path d="m4 16.4 8 4.2 8-4.2" />
  </Svg>
);

/** 汇总 / 报告 */
export const IconChart = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 20V4" />
    <path d="M4 20h16" />
    <path d="M8.5 16.5v-4M12.5 16.5v-7.5M16.5 16.5v-5.5" />
  </Svg>
);

export const IconCompass = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.2" />
    <path d="m15.4 8.6-2 4.8-4.8 2 2-4.8 4.8-2Z" />
  </Svg>
);

export const IconSparkles = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 3.5 13.6 8 18 9.6 13.6 11.2 12 15.7 10.4 11.2 6 9.6 10.4 8 12 3.5Z" />
    <path d="M18.5 15.2 19.2 17l1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7.7-1.8Z" />
    <path d="M5.6 15.4l.5 1.3 1.3.5-1.3.5-.5 1.3-.5-1.3L3.8 17.2l1.3-.5.5-1.3Z" />
  </Svg>
);

export const IconBulb = (p: IconProps) => (
  <Svg {...p}>
    <path d="M9 17.5h6" />
    <path d="M10 21h4" />
    <path d="M12 3.2a5.8 5.8 0 0 0-3.3 10.5c.5.4.8.9.8 1.5v.3h5v-.3c0-.6.3-1.1.8-1.5A5.8 5.8 0 0 0 12 3.2Z" />
  </Svg>
);

/* ------------------------------------------------------------ 动作图标 */

export const IconSend = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 19.5V5" />
    <path d="m5.8 11.2 6.2-6.2 6.2 6.2" />
  </Svg>
);

export const IconStop = (p: IconProps) => (
  <Svg {...p}>
    <rect x="7" y="7" width="10" height="10" rx="2.4" fill="currentColor" stroke="none" />
  </Svg>
);

export const IconClip = (p: IconProps) => (
  <Svg {...p}>
    <path d="M20.2 11.9 12.5 19.6a4.9 4.9 0 0 1-6.9-6.9l7.6-7.6a3.2 3.2 0 0 1 4.6 4.6l-7.7 7.6a1.6 1.6 0 0 1-2.3-2.3l7-7" />
  </Svg>
);

export const IconCopy = (p: IconProps) => (
  <Svg {...p}>
    <rect x="9" y="9" width="11.5" height="11.5" rx="2.2" />
    <path d="M5.5 15H5a1.5 1.5 0 0 1-1.5-1.5V5A1.5 1.5 0 0 1 5 3.5h8.5A1.5 1.5 0 0 1 15 5v.5" />
  </Svg>
);

export const IconCheck = (p: IconProps) => (
  <Svg {...p}>
    <path d="m5 12.8 4.6 4.6L19 7" />
  </Svg>
);

export const IconCheckCircle = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.4" />
    <path d="m8.4 12.2 2.5 2.5 4.7-5" />
  </Svg>
);

export const IconX = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6.4 6.4l11.2 11.2M17.6 6.4 6.4 17.6" />
  </Svg>
);

export const IconRefresh = (p: IconProps) => (
  <Svg {...p}>
    <path d="M20 12a8 8 0 1 1-2.5-5.8" />
    <path d="M20 4.5V10h-5.5" />
  </Svg>
);

export const IconLoader = ({ size = 18, className = '', ...rest }: IconProps) => (
  <Svg size={size} className={`animate-spin ${className}`} {...rest}>
    <path d="M12 3.6v3.2" />
    <path d="M12 17.2v3.2" />
    <path d="M4.9 4.9 7.2 7.2" />
    <path d="m16.8 16.8 2.3 2.3" />
    <path d="M3.6 12h3.2" />
    <path d="M17.2 12h3.2" />
    <path d="M4.9 19.1 7.2 16.8" />
    <path d="m16.8 7.2 2.3-2.3" />
  </Svg>
);

export const IconChevronDown = (p: IconProps) => (
  <Svg {...p}>
    <path d="m6.5 9.5 5.5 5.5 5.5-5.5" />
  </Svg>
);

export const IconChevronRight = (p: IconProps) => (
  <Svg {...p}>
    <path d="m9.5 6.5 5.5 5.5-5.5 5.5" />
  </Svg>
);

export const IconArrowLeft = (p: IconProps) => (
  <Svg {...p}>
    <path d="M19 12H5" />
    <path d="m11.2 5.8-6.2 6.2 6.2 6.2" />
  </Svg>
);

export const IconDownload = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 4v11" />
    <path d="m7.8 10.8 4.2 4.2 4.2-4.2" />
    <path d="M4.5 19.5h15" />
  </Svg>
);

export const IconEye = (p: IconProps) => (
  <Svg {...p}>
    <path d="M2.6 12S6 5.8 12 5.8 21.4 12 21.4 12 18 18.2 12 18.2 2.6 12 2.6 12Z" />
    <circle cx="12" cy="12" r="2.9" />
  </Svg>
);

export const IconKey = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="8.2" cy="15.8" r="3.6" />
    <path d="m11 13.4 7.8-7.8" />
    <path d="m16.4 8 2 2" />
    <path d="m14 10.4 2 2" />
  </Svg>
);

export const IconShield = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 3.4 5.5 5.8v5.4c0 4.2 2.7 7.6 6.5 9.4 3.8-1.8 6.5-5.2 6.5-9.4V5.8L12 3.4Z" />
    <path d="m9.4 12 1.9 1.9 3.4-3.6" />
  </Svg>
);

export const IconUser = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="8.2" r="3.8" />
    <path d="M4.8 20c.8-3.4 3.7-5.4 7.2-5.4s6.4 2 7.2 5.4" />
  </Svg>
);

export const IconLogout = (p: IconProps) => (
  <Svg {...p}>
    <path d="M14.5 4.5H6.8A1.8 1.8 0 0 0 5 6.3v11.4a1.8 1.8 0 0 0 1.8 1.8h7.7" />
    <path d="M17.5 8.6 21 12l-3.5 3.4" />
    <path d="M10.4 12H21" />
  </Svg>
);

export const IconAlert = (p: IconProps) => (
  <Svg {...p}>
    <path d="M10.9 4.3 3.4 17.4A1.3 1.3 0 0 0 4.5 19.4h15a1.3 1.3 0 0 0 1.1-2L13.1 4.3a1.3 1.3 0 0 0-2.2 0Z" />
    <path d="M12 9.6v4.2" />
    <circle cx="12" cy="16.4" r="0.85" fill="currentColor" stroke="none" />
  </Svg>
);

export const IconClock = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.2" />
    <path d="M12 7.6V12l3 1.8" />
  </Svg>
);

export const IconPlus = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 5.5v13M5.5 12h13" />
  </Svg>
);

export const IconUpload = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 16V5" />
    <path d="m7.8 9.2 4.2-4.2 4.2 4.2" />
    <path d="M4.5 15v3.5a1.5 1.5 0 0 0 1.5 1.5h12a1.5 1.5 0 0 0 1.5-1.5V15" />
  </Svg>
);

export const IconZap = (p: IconProps) => (
  <Svg {...p}>
    <path d="M13.2 3 5.6 13.2h5.4L10.4 21l7.9-10.4h-5.5L13.2 3Z" />
  </Svg>
);

export const IconDatabase = (p: IconProps) => (
  <Svg {...p}>
    <ellipse cx="12" cy="6.4" rx="7" ry="2.9" />
    <path d="M5 6.4v11.2c0 1.6 3.1 2.9 7 2.9s7-1.3 7-2.9V6.4" />
    <path d="M5 12c0 1.6 3.1 2.9 7 2.9s7-1.3 7-2.9" />
  </Svg>
);

export const IconTrash = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4.5 7h15" />
    <path d="M9.5 7V5.5A1.5 1.5 0 0 1 11 4h2a1.5 1.5 0 0 1 1.5 1.5V7" />
    <path d="M6.5 7l.8 11.1a1.9 1.9 0 0 0 1.9 1.8h5.6a1.9 1.9 0 0 0 1.9-1.8L17.5 7" />
    <path d="M10.5 11v5M13.5 11v5" />
  </Svg>
);

export const IconHistory = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3.6 12a8.4 8.4 0 1 0 2.6-6.1" />
    <path d="M3.4 4.6v4.2h4.2" />
    <path d="M12 8v4.2l3 1.8" />
  </Svg>
);

/* ------------------------------------------------------------ 主题 / 账号 */

/** 白天：太阳 + 光芒 */
export const IconSun = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="4.1" />
    <path d="M12 2.6v2.2M12 19.2v2.2M4.2 12H2M22 12h-2.2" />
    <path d="M5.6 5.6 7.2 7.2M16.8 16.8l1.6 1.6M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6" />
  </Svg>
);

/** 夜晚：月牙 */
export const IconMoon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M20.3 14.2A8.4 8.4 0 0 1 9.8 3.7a8.6 8.6 0 1 0 10.5 10.5Z" />
  </Svg>
);

/** 跟随系统：显示器 */
export const IconMonitor = (p: IconProps) => (
  <Svg {...p}>
    <rect x="2.8" y="4.5" width="18.4" height="12" rx="2" />
    <path d="M8.6 20h6.8M12 16.5V20" />
  </Svg>
);

/** 锁：密码 */
export const IconLock = (p: IconProps) => (
  <Svg {...p}>
    <rect x="4.6" y="10.4" width="14.8" height="9.6" rx="2.2" />
    <path d="M8.2 10.4V7.9a3.8 3.8 0 0 1 7.6 0v2.5" />
    <path d="M12 14.2v2.2" />
  </Svg>
);

/** 铅笔：编辑昵称 */
export const IconPencil = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4.6 19.4h3.2L19 8.2a2.26 2.26 0 0 0-3.2-3.2L4.6 16.2v3.2Z" />
    <path d="m14.9 5.9 3.2 3.2" />
  </Svg>
);

/** 调色板：外观设置 */
export const IconPalette = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 3.4a8.6 8.6 0 0 0 0 17.2c1.3 0 2.1-1 2.1-2.1 0-.6-.2-1-.5-1.4-.3-.4-.5-.8-.5-1.3 0-1.1.9-2 2-2h1.6a3.9 3.9 0 0 0 3.9-3.9c0-3.6-3.8-6.5-8.6-6.5Z" />
    <circle cx="7.6" cy="12.4" r="1.1" />
    <circle cx="9.8" cy="8.2" r="1.1" />
    <circle cx="14.6" cy="7.8" r="1.1" />
  </Svg>
);


/* ------------------------------------------------- 语义映射（按 agent 名） */

export const AGENT_ICON: Record<string, React.ComponentType<IconProps>> = {
  Planner: IconTarget,
  ResumeAnalyzer: IconFile,
  JobSearcher: IconBriefcase,
  WebResearcher: IconGlobe,
  CoverLetterGenerator: IconMail,
  Critic: IconShield,
  Synthesizer: IconChart,
  ChatBot: IconChat,
  HITL: IconCheckCircle,
};

export const AGENT_LABEL: Record<string, string> = {
  Planner: '任务规划',
  ResumeAnalyzer: '简历分析',
  JobSearcher: '岗位检索',
  WebResearcher: '深度调研',
  CoverLetterGenerator: '求职信撰写',
  Critic: '质量评审',
  Synthesizer: '结果汇总',
  ChatBot: '对话应答',
  HITL: '人工确认',
};

export function agentIcon(agent: string): React.ComponentType<IconProps> {
  return AGENT_ICON[agent] || IconSparkles;
}

export function agentLabel(agent: string): string {
  return AGENT_LABEL[agent] || agent || '未知节点';
}
