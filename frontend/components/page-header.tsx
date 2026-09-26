'use client';

/** 内页统一页头 */
export default function PageHeader({
  icon: Icon,
  title,
  desc,
  children,
}: {
  icon: any;
  title: string;
  desc?: string;
  children?: React.ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-center gap-3">
      <span className="w-10 h-10 rounded-2xl bg-gradient-to-br from-brand-500 to-accent-500 text-white flex items-center justify-center shadow-glow shrink-0">
        <Icon size={18} />
      </span>
      <div className="min-w-0">
        <h1 className="text-[21px] font-semibold tracking-tight text-ink-900">{title}</h1>
        {desc && <p className="text-[14.5px] text-ink-400 mt-0.5">{desc}</p>}
      </div>
      {children && <div className="ml-auto flex items-center gap-2">{children}</div>}
    </header>
  );
}

/** 空状态占位 */
export function EmptyState({
  icon: Icon,
  title,
  desc,
}: {
  icon: any;
  title: string;
  desc?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-10">
      <span className="w-12 h-12 rounded-2xl bg-surface-100 text-ink-300 flex items-center justify-center mb-3">
        <Icon size={21} />
      </span>
      <p className="text-[15px] font-medium text-ink-600">{title}</p>
      {desc && <p className="mt-1 text-[13.5px] text-ink-400 max-w-xs leading-relaxed">{desc}</p>}
    </div>
  );
}
