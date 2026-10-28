'use client';

import { useState } from 'react';
import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { CycleBucket, CycleBucketRow, CycleStats } from '@/lib/astro/api-cycles';
import { shortDate } from '@/lib/astro/api-cycles';
import { edgeColour, SectionNote, VerdictBadge } from './cycles-shared';

function SectionTitle({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="mb-1">
      <p className="text-xs font-semibold text-[#5c4327]">{title}</p>
      {sub && <p className="text-[10px] text-[#b39a76]">{sub}</p>}
    </div>
  );
}

/** Diverging hit-rate rows centred on the all-days baseline. */
function DivergingRows({ bucket }: { bucket: CycleBucket }) {
  const base = bucket.baseline.hit_pct;
  const maxAbs = Math.max(1, ...bucket.rows.map((r) => Math.abs(r.hit_pct - base)));
  return (
    <div className="space-y-1">
      {bucket.rows.map((r) => {
        const d = r.hit_pct - base;
        const w = (Math.abs(d) / maxAbs) * 50;
        const cur = r.label === bucket.current;
        return (
          <div key={r.label} className={`grid grid-cols-[minmax(0,7.5rem)_1fr_auto] items-center gap-2 text-[11px] ${cur ? 'font-semibold' : ''}`}>
            <span className="truncate text-[#5c4327]" title={r.label}>
              {cur && '▸ '}
              {r.label}
            </span>
            <div className="relative h-3 rounded bg-[#f6f1e7]">
              <div className="absolute left-1/2 top-0 h-full w-px bg-[#b39a76]/60" />
              <div
                className="absolute top-0 h-full rounded"
                style={{
                  left: d >= 0 ? '50%' : `${50 - w}%`,
                  width: `${Math.max(w, 0.8)}%`,
                  background: edgeColour(d, r.verdict),
                }}
              />
            </div>
            <span className="flex items-center gap-1 whitespace-nowrap font-mono text-[10.5px] text-[#7c5a2e]">
              {r.hit_pct.toFixed(1)}% <span className="text-[#b39a76]">t{r.t >= 0 ? '+' : ''}{r.t.toFixed(1)}</span>
              <VerdictBadge verdict={r.verdict} className="hidden sm:inline-block" />
            </span>
          </div>
        );
      })}
      <p className="text-[10px] text-[#b39a76]">
        Bars = share of up days minus the {base.toFixed(1)}% all-days average · faded = noise · ▸ = today
      </p>
    </div>
  );
}

function NakshatraHeatmap({ bucket }: { bucket: CycleBucket }) {
  const [sel, setSel] = useState<CycleBucketRow | null>(null);
  const base = bucket.baseline.hit_pct;
  const shown = sel ?? bucket.rows.find((r) => r.label === bucket.current) ?? null;
  const maxAbs = Math.max(0.5, ...bucket.rows.map((r) => Math.abs(r.hit_pct - base)));
  return (
    <div>
      <div className="grid grid-cols-3 gap-1 sm:grid-cols-9">
        {bucket.rows.map((r) => {
          const cur = r.label === bucket.current;
          return (
            <button
              type="button"
              key={r.label}
              onClick={() => setSel(r)}
              className={`rounded px-1 py-1 text-center text-[9.5px] leading-tight text-[#3d2a17] ${
                cur ? 'ring-2 ring-[#7e6bb0]' : ''
              } ${sel?.label === r.label ? 'outline outline-1 outline-[#4a3525]' : ''}`}
              style={{ background: edgeColour(r.hit_pct - base, r.verdict, 0.25 + (1.2 * Math.abs(r.hit_pct - base)) / maxAbs) }}
              title={`${r.label}: ${r.hit_pct}% up days (t ${r.t})`}
            >
              <span className="block truncate">{r.label}</span>
              <span className="font-mono">{r.hit_pct.toFixed(0)}%</span>
            </button>
          );
        })}
      </div>
      {shown && (
        <p className="mt-1.5 text-[11px] leading-snug text-[#7c5a2e]">
          <span className="font-semibold">{shown.label}</span> (lord {shown.lord}): {shown.n.toLocaleString()} days, up{' '}
          {shown.hit_pct}% vs {base}% average, avg {shown.mean_pct >= 0 ? '+' : ''}
          {shown.mean_pct.toFixed(3)}%/day, t {shown.t >= 0 ? '+' : ''}
          {shown.t.toFixed(2)} — <VerdictBadge verdict={shown.verdict} />. Next Moon in {shown.label}:{' '}
          <span className="font-medium">{shortDate(shown.next)}</span>.
        </p>
      )}
      <p className="text-[10px] text-[#b39a76]">Tap a nakshatra for details · purple ring = Moon today · green = more up days, red = fewer</p>
    </div>
  );
}

function SunSignChart({ bucket }: { bucket: CycleBucket }) {
  const data = bucket.rows.map((r) => ({
    sign: r.label.slice(0, 3),
    full: `${r.label} (${r.rashi})`,
    v: r.month_mean_pct ?? 0,
    hit: r.month_hit_pct ?? 0,
    months: r.months ?? 0,
    verdict: r.verdict,
    cur: r.label === bucket.current,
    next: r.next,
  }));
  return (
    <div className="h-40 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 6, right: 4, bottom: 0, left: 0 }}>
          <XAxis dataKey="sign" tick={{ fontSize: 9, fill: '#97795a' }} interval={0} tickLine={false} />
          <YAxis tick={{ fontSize: 9, fill: '#97795a' }} tickFormatter={(v: number) => `${v}%`} width={42} />
          <ReferenceLine y={0} stroke="#b39a76" />
          <Tooltip
            cursor={{ fill: '#f6f1e7' }}
            contentStyle={{ fontSize: 11, background: '#fffdf6', border: '1px solid #e8d5ae' }}
            formatter={(v: number, _n, p) => [
              `${v.toFixed(2)}% avg · up ${p.payload.hit}% of ${p.payload.months} yrs · next ${shortDate(p.payload.next)}`,
              p.payload.full,
            ]}
            labelFormatter={() => ''}
          />
          <Bar dataKey="v" radius={[3, 3, 0, 0]} isAnimationActive={false}>
            {data.map((d) => (
              <Cell key={d.sign} fill={edgeColour(d.v, d.verdict)} stroke={d.cur ? '#7e6bb0' : undefined} strokeWidth={d.cur ? 2 : 0} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function RetroTable({ stats }: { stats: CycleStats }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[11px]">
        <thead>
          <tr className="text-left text-[10px] text-[#97795a]">
            <th className="py-0.5 font-normal">Planet</th>
            <th className="py-0.5 font-normal">Up days ℞ / direct</th>
            <th className="hidden py-0.5 font-normal sm:table-cell">Annualised ℞ / direct</th>
            <th className="py-0.5 font-normal">Vol</th>
            <th className="py-0.5 font-normal">Verdict</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(stats.retrograde).map(([p, r]) => (
            <tr key={p} className="border-t border-[#f0e4cc]">
              <td className="py-1 font-medium text-[#5c4327]">
                {p}
                <span className={`ml-1 text-[9px] ${r.now === 'retrograde' ? 'text-[#c9553f]' : 'text-[#3f8a6e]'}`}>
                  {r.now === 'retrograde' ? '℞ now' : 'direct'}
                </span>
              </td>
              <td className="py-1 font-mono text-[#7c5a2e]">
                {r.retro.hit_pct?.toFixed(1)}% / {r.direct.hit_pct?.toFixed(1)}%
              </td>
              <td className="hidden py-1 font-mono text-[#7c5a2e] sm:table-cell">
                {r.retro.annual_pct?.toFixed(1)}% / {r.direct.annual_pct?.toFixed(1)}%
              </td>
              <td className="py-1 font-mono text-[#7c5a2e]">{r.vol_ratio?.toFixed(2)}×</td>
              <td className="py-1">
                <VerdictBadge verdict={r.verdict} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CyclesStatsPanel({ stats }: { stats: CycleStats }) {
  const c = stats.conclusions;
  return (
    <div className="space-y-4">
      <SectionNote>
        <span className="font-semibold">Bottom line: </span>
        {c.overall}
      </SectionNote>
      {stats.demo_data && (
        <p className="rounded border border-[#eecfc7] bg-[#fbeae4] px-2 py-1 text-[10.5px] text-[#a14d3c]">
          Demo mode: prices are synthetic, so these statistics only illustrate the method.
        </p>
      )}

      <div>
        <SectionTitle title="By moon phase (8)" sub={`${stats.days.toLocaleString()} sessions since ${stats.history_start.slice(0, 4)}`} />
        <DivergingRows bucket={stats.moon_phase} />
        <p className="mt-1 text-[11px] leading-snug text-[#7c5a2e]">{c.moon_phase}</p>
      </div>

      <div>
        <SectionTitle title="By paksha (lunar fortnight)" />
        <DivergingRows bucket={stats.paksha} />
        <p className="mt-1 text-[11px] leading-snug text-[#7c5a2e]">{c.paksha}</p>
      </div>

      <div>
        <SectionTitle title="By Moon nakshatra (27)" sub="Share of up days when the Moon sat in each lunar mansion" />
        <NakshatraHeatmap bucket={stats.nakshatra} />
        <p className="mt-1 text-[11px] leading-snug text-[#7c5a2e]">{c.nakshatra}</p>
      </div>

      <div>
        <SectionTitle title="Sankranti seasonality — Sun's sidereal sign (12)" sub="Average return over each solar month" />
        <SunSignChart bucket={stats.sun_sign} />
        <p className="mt-1 text-[11px] leading-snug text-[#7c5a2e]">{c.sun_sign}</p>
      </div>

      <div>
        <SectionTitle title="Retrograde vs direct" sub="Daily returns while each planet is retrograde (℞) vs direct" />
        <RetroTable stats={stats} />
        <p className="mt-1 text-[11px] leading-snug text-[#7c5a2e]">{c.retrograde}</p>
      </div>

      <p className="text-[10px] leading-snug text-[#b39a76]">
        How to read: {stats.method} Source: {stats.data_source}.
      </p>
    </div>
  );
}
