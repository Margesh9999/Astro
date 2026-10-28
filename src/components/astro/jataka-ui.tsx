'use client';

import type { ReactNode } from 'react';
import { Lightbulb } from 'lucide-react';

export function Pill({ children, tone = 'gold' }: { children: ReactNode; tone?: 'gold' | 'green' | 'rose' | 'lav' }) {
  const tones = {
    gold: 'border-[#dcc08a] bg-[#f9efd8] text-[#8a6a3a]',
    green: 'border-[#a8d8bf] bg-[#e2f3e9] text-[#2f7357]',
    rose: 'border-[#e8b3a8] bg-[#fbe7e0] text-[#a34332]',
    lav: 'border-[#cbb8dd] bg-[#efe7f8] text-[#6b4e93]',
  };
  return <span className={`inline-block rounded border px-1.5 py-px text-[10px] font-medium ${tones[tone]}`}>{children}</span>;
}

export function Note({ text, icon }: { text: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex items-start gap-1.5 rounded-lg border border-[#e8ddb8] bg-[#fdf8ec] px-2.5 py-2">
      {icon ?? <Lightbulb className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-[#c98a2e]" />}
      <p className="text-[11px] leading-relaxed text-[#7c5a2e]">{text}</p>
    </div>
  );
}

/** A collapsible concept section */
export function Concept({ icon, title, subtitle, children, open = false }: {
  icon: ReactNode; title: string; subtitle: string; children: ReactNode; open?: boolean;
}) {
  return (
    <details open={open} className="group rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/80">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2.5">
        <span className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg border border-[#eccf9d] bg-[#fdf3dc]">{icon}</span>
        <span className="min-w-0 flex-1">
          <span className="block text-xs font-semibold text-[#5c4327]">{title}</span>
          <span className="block text-[10px] text-[#b39a76]">{subtitle}</span>
        </span>
        <span className="text-[10px] text-[#c98a2e] group-open:hidden">open ▾</span>
        <span className="hidden text-[10px] text-[#c98a2e] group-open:inline">close ▴</span>
      </summary>
      <div className="border-t border-[#f4ead2] px-3 py-3">{children}</div>
    </details>
  );
}

/** Fit-score bar (0–100) */
export function FitBar({ value, tone }: { value: number; tone?: 'green' | 'gold' | 'rose' }) {
  const t = tone ?? (value >= 60 ? 'green' : value >= 45 ? 'gold' : 'rose');
  const grad = t === 'green' ? 'from-[#8bb5a3] to-[#3f9a72]' : t === 'gold' ? 'from-[#f0cf8a] to-[#d0a040]' : 'from-[#eab0a2] to-[#c9553f]';
  return (
    <div className="h-1.5 overflow-hidden rounded-full bg-[#f4ead2]">
      <div className={`h-full rounded-full bg-gradient-to-r ${grad}`} style={{ width: `${Math.max(2, Math.min(100, value))}%` }} />
    </div>
  );
}

export const gbp = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined || Number.isNaN(v)
    ? '—'
    : `${v < 0 ? '−' : ''}£${Math.abs(v).toLocaleString('en-GB', { maximumFractionDigits: digits })}`;

export const gbpShort = (v: number) => {
  const a = Math.abs(v);
  if (a >= 1e6) return `£${(v / 1e6).toFixed(a >= 1e7 ? 0 : 1)}m`;
  if (a >= 1e3) return `£${(v / 1e3).toFixed(0)}k`;
  return `£${v.toFixed(0)}`;
};

export const pct = (v: number | null | undefined, digits = 1, signed = true) =>
  v === null || v === undefined ? '—' : `${signed && v > 0 ? '+' : ''}${(v * 100).toFixed(digits)}%`;

export const TOOLTIP_STYLE = { background: '#fffdf6', border: '1px solid #ecdec2', borderRadius: 8, fontSize: 11 };
