'use client';

import { BookOpenText, ShieldAlert } from 'lucide-react';
import type { CyclesInsight } from '@/lib/astro/api-cycles';
import { shortDate } from '@/lib/astro/api-cycles';

const BIAS_STYLE: Record<string, string> = {
  Bullish: 'border-[#a8d8bf] bg-[#e2f3e9] text-[#2f7357]',
  Bearish: 'border-[#e8b3a8] bg-[#fbe7e0] text-[#a34332]',
  Neutral: 'border-[#eed9b4] bg-[#fdf3dc] text-[#8a6a3a]',
};

const fmt = (v?: number) => (v == null ? '—' : v.toLocaleString(undefined, { maximumFractionDigits: 2 }));

/** Big plain-English "Today's reading": sky now → price now → meaning → action. */
export function CyclesReading({ insight }: { insight: CyclesInsight }) {
  const r = insight.reading;
  const heads = ['Sky now', 'Price now', `For ${insight.name}`, 'What to do'];
  return (
    <div className="rounded-xl border border-[#e3c68f] bg-gradient-to-br from-[#fffaf0] via-[#fdf3dc] to-[#fbead0] p-3 sm:p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 font-display text-sm font-semibold text-[#5c4327]">
          <BookOpenText className="h-4 w-4 text-[#c98a2e]" /> Today&apos;s reading · {shortDate(insight.date)}
        </p>
        <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${BIAS_STYLE[r.bias] ?? BIAS_STYLE.Neutral}`}>
          {r.bias} bias
        </span>
      </div>
      <ol className="space-y-1.5">
        {r.sentences.map((s, i) => {
          const body = s.replace(/^(Sky now|Price now|For [^:]+|What to do):\s*/, '');
          const last = i === r.sentences.length - 1 && s.startsWith('What to do');
          return (
            <li
              key={i}
              className={`text-[12.5px] leading-relaxed sm:text-[13px] ${last ? 'rounded-lg border border-[#e3c68f] bg-[#fffdf6] px-2.5 py-1.5 font-medium text-[#4a3525]' : 'text-[#5c4327]'}`}
            >
              <span className="mr-1 text-[11px] font-semibold uppercase tracking-wide text-[#b0802f]">
                {last ? 'What to do' : (heads[i] ?? '')}
              </span>
              {body}
            </li>
          );
        })}
      </ol>
      {r.levels.support != null && (
        <div className="mt-2.5 grid grid-cols-2 gap-1.5 text-[11px] sm:grid-cols-4">
          <div className="rounded-md bg-[#fbe7e0] px-2 py-1">
            <span className="block text-[10px] text-[#a34332]">Stop-loss area (S)</span>
            <span className="font-mono font-semibold text-[#a34332]">{fmt(r.levels.support)}</span>
          </div>
          <div className="rounded-md bg-[#fdf3dc] px-2 py-1">
            <span className="block text-[10px] text-[#8a6a3a]">Dip-buy zone (inner S)</span>
            <span className="font-mono font-semibold text-[#8a6a3a]">{fmt(r.levels.inner_support)}</span>
          </div>
          <div className="rounded-md bg-[#fdf3dc] px-2 py-1">
            <span className="block text-[10px] text-[#8a6a3a]">First target (inner R)</span>
            <span className="font-mono font-semibold text-[#8a6a3a]">{fmt(r.levels.inner_resistance)}</span>
          </div>
          <div className="rounded-md bg-[#e2f3e9] px-2 py-1">
            <span className="block text-[10px] text-[#2f7357]">Stretch target (R)</span>
            <span className="font-mono font-semibold text-[#2f7357]">{fmt(r.levels.resistance)}</span>
          </div>
        </div>
      )}
      {r.avoid && (
        <p className="mt-2 flex items-start gap-1.5 text-[11px] text-[#a14d3c]">
          <ShieldAlert className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
          Caution date: {shortDate(r.avoid.date)} — {r.avoid.title}.
        </p>
      )}
      {insight.demo_data && (
        <p className="mt-1.5 text-[10px] text-[#a14d3c]">Demo mode: synthetic prices — levels and history are illustrative.</p>
      )}
    </div>
  );
}
