'use client';

import { useState, type ReactNode } from 'react';
import { HelpCircle } from 'lucide-react';
import { VERDICT_STYLE, type Verdict } from '@/lib/astro/api-cycles';

/** Small verdict pill: significant / weak hint / noise / too few. */
export function VerdictBadge({ verdict, className = '' }: { verdict?: Verdict; className?: string }) {
  const v = VERDICT_STYLE[verdict ?? 'too few'] ?? VERDICT_STYLE['too few'];
  return (
    <span className={`inline-block whitespace-nowrap rounded border px-1.5 py-px text-[9px] uppercase ${v.cls} ${className}`}>
      {v.label}
    </span>
  );
}

/**
 * A metric with a tap-to-expand plain-English explanation (works on touch,
 * unlike hover tooltips). `children` is the value element.
 */
export function ExplainedMetric({
  label,
  explain,
  children,
  defaultOpen = false,
}: {
  label: string;
  explain?: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-md border border-[#f0e4cc] bg-[#fffdf6] px-2.5 py-1.5">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-2 text-left"
        aria-expanded={open}
      >
        <span className="flex items-center gap-1 text-[11px] text-[#97795a]">
          {label}
          {explain && <HelpCircle className="h-3 w-3 text-[#c98a2e]" aria-label="what does this mean?" />}
        </span>
        <span className="font-mono text-xs font-semibold text-[#5c4327]">{children}</span>
      </button>
      {open && explain && <p className="mt-1 text-[11px] leading-snug text-[#7c5a2e]">{explain}</p>}
    </div>
  );
}

/** Colour for a signed excess value, alpha by significance. */
export function edgeColour(diff: number, verdict?: Verdict, scale = 1): string {
  const strong = (verdict === 'significant' ? 1 : verdict === 'weak' ? 0.7 : 0.35) * scale;
  const pos = diff >= 0;
  const [r, g, b] = pos ? [74, 154, 126] : [207, 91, 84];
  return `rgba(${r},${g},${b},${strong})`;
}

export function SectionNote({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-md border border-[#e8ddb8] bg-[#fdf8ec] px-2.5 py-1.5 text-[11px] leading-snug text-[#7c5a2e]">
      {children}
    </p>
  );
}
