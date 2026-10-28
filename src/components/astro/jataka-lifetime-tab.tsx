'use client';

import { Area, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { JatakaPlan } from '@/lib/astro/api-jataka';
import type { JatakaLifetimeStage } from '@/lib/astro/types';
import { Note, Pill, TOOLTIP_STYLE, gbp, gbpShort } from './jataka-ui';
import { LineChart as LineChartIcon } from 'lucide-react';

/** Lifetime wealth: illustrative £ projection by age (low/base/high), modulated by dasha. */
export function JatakaLifetimeTab({ plan, stages, headline }: { plan: JatakaPlan; stages: JatakaLifetimeStage[]; headline: string }) {
  if (!plan || plan.error) return <Note text="Lifetime projection unavailable." />;
  const life = plan.lifetime;
  const data = life.rows.map((r) => ({ ...r, band: [r.low, r.high] as [number, number], age: Math.round(r.age) }));
  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/80 p-3">
        <p className="mb-1 flex flex-wrap items-center gap-1.5 text-xs font-semibold text-[#5c4327]">
          <LineChartIcon className="h-3.5 w-3.5 text-[#c98a2e]" /> Illustrative wealth by age ({Math.round(life.age_now)} → {life.inputs.end_age})
          <Pill tone="rose">illustrative — not a prediction</Pill>
        </p>
        <div className="h-60 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 6, right: 10, bottom: 0, left: 4 }}>
              <defs>
                <linearGradient id="lifeBand" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#c9962e" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#c9962e" stopOpacity={0.06} />
                </linearGradient>
              </defs>
              <XAxis dataKey="age" tick={{ fontSize: 10, fill: '#97795a' }} unit="y" />
              <YAxis tick={{ fontSize: 10, fill: '#97795a' }} width={44} tickFormatter={(v) => gbpShort(Number(v))} />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                labelFormatter={(l, p) => {
                  const r = p?.[0]?.payload as (typeof data)[number] | undefined;
                  return r ? `age ${l} · ${r.year} · ${r.md}/${r.ad} (×${r.dasha_mod})` : `age ${l}`;
                }}
                formatter={(v, n) => (Array.isArray(v) ? [`${gbp(Number(v[0]))} – ${gbp(Number(v[1]))}`, 'low–high'] : [gbp(Number(v)), String(n)])}
              />
              <Area type="monotone" dataKey="band" stroke="none" fill="url(#lifeBand)" isAnimationActive={false} />
              <Line type="monotone" dataKey="base" name="base case" stroke="#a8701a" strokeWidth={2} dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-1 text-[11px] leading-relaxed text-[#7c5a2e]">{life.plain}</p>
        <div className="warm-scroll mt-2 overflow-x-auto">
          <table className="w-full min-w-[420px] text-left text-[11px]">
            <thead><tr className="text-[10px] uppercase tracking-wide text-[#b39a76]"><th className="py-1 pr-2">Age</th><th className="pr-2">Year · dasha</th><th className="pr-2 text-right">Low</th><th className="pr-2 text-right">Base</th><th className="text-right">High</th></tr></thead>
            <tbody>
              {life.milestones.map((m) => (
                <tr key={m.age} className="border-t border-[#f4ead2]">
                  <td className="py-1 pr-2 font-medium text-[#5c4327]">{m.age}</td>
                  <td className="pr-2 text-[#97795a]">{m.year} · {m.md}</td>
                  <td className="pr-2 text-right font-mono text-[#7c5a2e]">{gbp(m.low)}</td>
                  <td className="pr-2 text-right font-mono font-semibold text-[#3f8a6e]">{gbp(m.base)}</td>
                  <td className="text-right font-mono text-[#7c5a2e]">{gbp(m.high)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-1 text-[10px] leading-snug text-[#b39a76]">{life.method} Change capital, savings and base return in the form above.</p>
      </div>

      <p className="font-display text-sm text-[#5c4327]">{headline}</p>
      <div className="space-y-1.5">
        {stages.map((s) => (
          <div key={s.lord + s.start} className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6]/70 px-3 py-2">
            <div className="flex flex-wrap items-center justify-between gap-1">
              <p className="text-xs font-semibold text-[#5c4327]">{s.lord} · age {s.age_from}–{s.age_to} ({s.start}–{s.end})</p>
              <div className="flex items-center gap-1.5">
                <Pill tone="lav">{s.phase}</Pill>
                <span className="font-mono text-[11px] text-[#8a6a3a]" title="relative wealth-potential index (0-100)">{s.wealth_index}</span>
              </div>
            </div>
            <p className="mt-0.5 text-[11px] leading-snug text-[#7c5a2e]">{s.note}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
