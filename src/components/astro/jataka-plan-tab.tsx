'use client';

import type { JatakaPlan, PlanFit } from '@/lib/astro/api-jataka';
import { FitBar, Note, Pill, gbp } from './jataka-ui';
import { Briefcase, Globe2, IndianRupee, Layers } from 'lucide-react';

function FitList({ title, icon, rows, top = 3 }: { title: string; icon: React.ReactNode; rows: PlanFit[]; top?: number }) {
  return (
    <div className="rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/80 p-3">
      <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-[#5c4327]">{icon}{title}</p>
      <div className="space-y-2">
        {rows.map((r, i) => (
          <div key={r.name}>
            <div className="flex items-center justify-between gap-2 text-[11px]">
              <span className={`text-[#5c4327] ${i < top ? 'font-semibold' : ''}`}>{i < top ? '★ ' : ''}{r.name}</span>
              <span className="font-mono text-[#8a6a3a]">{r.fit}</span>
            </div>
            <FitBar value={r.fit} />
            <p className="mt-0.5 text-[10px] leading-snug text-[#97795a]">{r.why}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Recommendations: markets, sectors, strategies (fit + why) and income bands. */
export function JatakaPlanTab({ plan }: { plan: JatakaPlan }) {
  if (!plan || plan.error) return <Note text={`Money plan unavailable — ${plan?.error ?? 'no data'}`} />;
  const inc = plan.income;
  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-lg border border-[#e4d0b4] bg-gradient-to-r from-[#fdf3dc] via-[#f9e9d2] to-[#f6e3c4] p-3">
        <p className="font-display text-[10px] uppercase tracking-[0.18em] text-[#a8701a]">Where to focus for consistent trading income</p>
        <p className="mt-1 text-xs leading-relaxed text-[#5c4327]">{plan.summary}</p>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <FitList title="Markets" icon={<Globe2 className="h-3.5 w-3.5 text-[#c98a2e]" />} rows={plan.markets} top={2} />
        <FitList title="Sectors" icon={<Layers className="h-3.5 w-3.5 text-[#c98a2e]" />} rows={plan.sectors} top={3} />
      </div>

      <div className="rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/80 p-3">
        <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-[#5c4327]">
          <Briefcase className="h-3.5 w-3.5 text-[#c98a2e]" /> Trading strategies — fit for this chart
        </p>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {plan.strategies.map((s, i) => (
            <div key={s.key} className={`rounded-lg border px-2.5 py-2 ${i < 2 ? 'border-[#d9b46a] bg-[#fdf3dc]/70' : 'border-[#f0e4cc] bg-[#fdf8ec]'}`}>
              <div className="flex items-center justify-between gap-2">
                <p className="text-[11px] font-semibold text-[#5c4327]">{i < 2 ? '★ ' : ''}{s.label}</p>
                <span className="font-mono text-[10px] text-[#8a6a3a]">fit {s.fit}</span>
              </div>
              <FitBar value={s.fit} />
              <p className="mt-0.5 text-[10px] leading-snug text-[#7c5a2e]">{s.why}</p>
              <p className="mt-0.5 text-[10px] text-[#b39a76]">
                reference return range {Math.round(s.returns.low * 1000) / 10}% / {Math.round(s.returns.base * 1000) / 10}% / {Math.round(s.returns.high * 1000) / 10}% a year (low/base/high)
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-[#eed9b4] bg-gradient-to-r from-[#fdf3dc] to-[#fbead0] p-3">
        <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-[#8a6a3a]">
          <IndianRupee className="h-4 w-4" /> Illustrative income at {gbp(inc.capital)} capital
          <Pill tone="lav">dasha factor ×{plan.dasha_factor.toFixed(2)} ({plan.dasha_now.md}/{plan.dasha_now.ad})</Pill>
        </p>
        <div className="warm-scroll overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-[11px]">
            <thead>
              <tr className="text-[10px] uppercase tracking-wide text-[#b39a76]">
                <th className="py-1 pr-2">Strategy</th>
                <th className="pr-2 text-right">Weekly (low · base · high)</th>
                <th className="pr-2 text-right">Monthly</th>
                <th className="pr-2 text-right">Yearly</th>
                <th className="text-right">Capital for {gbp(inc.target_weekly)}/wk</th>
              </tr>
            </thead>
            <tbody>
              {inc.rows.map((r) => (
                <tr key={r.key} className="border-t border-[#eedcb8]">
                  <td className="py-1.5 pr-2 font-medium text-[#5c4327]">{r.strategy}<span className="ml-1 text-[10px] font-normal text-[#97795a]">{r.annual_return_pct.base}%/yr base</span></td>
                  <td className="pr-2 text-right font-mono text-[#3f8a6e]">{gbp(r.weekly.low)} · <b>{gbp(r.weekly.base)}</b> · {gbp(r.weekly.high)}</td>
                  <td className="pr-2 text-right font-mono text-[#5c4327]">{gbp(r.monthly.base)}</td>
                  <td className="pr-2 text-right font-mono text-[#5c4327]">{gbp(r.yearly.base)}</td>
                  <td className="text-right font-mono text-[#8a6a3a]">{r.capital_for_target ? gbp(r.capital_for_target) : 'n/a'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs font-medium leading-relaxed text-[#6b4f2e]">{inc.target_line}</p>
        <p className="mt-1 text-[10px] leading-snug text-[#97795a]">{inc.method}</p>
      </div>
      <p className="text-[10px] text-[#b39a76]">{plan.disclaimer}</p>
    </div>
  );
}
