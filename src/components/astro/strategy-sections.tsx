'use client';

import { useState } from 'react';
import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { CheckSquare, Orbit } from 'lucide-react';
import { NorthIndianChart, type KundaliPlanet } from './north-indian-chart';
import { fmtGbp, fmtPx, type FinalStrategy, type HorizonPlan, type NatalVsToday, type ScoreRow } from '@/lib/astro/api-strategy';

const SIG: Record<string, string> = {
  bullish: 'border-[#a8d8bf] bg-[#e2f3e9] text-[#2f7357]',
  bearish: 'border-[#e8b3a8] bg-[#fbe7e0] text-[#a34332]',
  neutral: 'border-[#dcc08a] bg-[#f9efd8] text-[#8a6a3a]',
  'n/a': 'border-[#e2d8c6] bg-[#f6f1e7] text-[#9a8a72]',
};

const KIND: Record<string, string> = {
  sky: 'bg-[#e2eef3] text-[#2f6577]',
  timing: 'bg-[#fbe7e0] text-[#a34332]',
  dasha: 'bg-[#f3e6f0] text-[#8a4f78]',
  ingress: 'bg-[#fdf0dc] text-[#a06a1c]',
  station: 'bg-[#eef0e4] text-[#5d6b3a]',
};

export function SectionTitle({ icon: I, children }: { icon: typeof Orbit; children: React.ReactNode }) {
  return (
    <div className="mb-2 flex items-center gap-2">
      <I className="h-4 w-4 text-[#c98a2e]" />
      <h3 className="font-display text-sm font-semibold text-[#5c4327]">{children}</h3>
    </div>
  );
}

export function Note({ children }: { children: React.ReactNode }) {
  return <p className="mt-2 rounded-md bg-[#fdf6e6] px-3 py-2 text-[11px] leading-relaxed text-[#7c5a2e]">{children}</p>;
}

function Bar2({ score }: { score: number }) {
  const w = Math.min(50, Math.abs(score) / 2);
  return (
    <div className="relative h-1.5 w-full min-w-[60px] rounded-full bg-[#f0e4cc]">
      <div className="absolute left-1/2 top-0 h-1.5 w-px bg-[#c9b48c]" />
      <div
        className={`absolute top-0 h-1.5 rounded-full ${score >= 0 ? 'bg-[#6fb38f]' : 'bg-[#d27a66]'}`}
        style={score >= 0 ? { left: '50%', width: `${w}%` } : { right: '50%', width: `${w}%` }}
      />
    </div>
  );
}

/* ── signal scoreboard ─────────────────────────────────────────────────── */
export function Scoreboard({ rows, overall }: { rows: ScoreRow[]; overall: FinalStrategy['overall'] }) {
  const avail = rows.filter((r) => r.available);
  const drag = [...avail].sort((a, b) => a.score - b.score)[0];
  const lift = [...avail].sort((a, b) => b.score - a.score)[0];
  return (
    <div>
      <div className="flex flex-col gap-1.5">
        {rows.map((r) => (
          <div key={r.key} className={`rounded-lg border border-[#f0e4cc] px-3 py-2 ${r.available ? 'bg-[#fffdf6]/80' : 'bg-[#f8f4ec]'}`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="min-w-0 flex-1 text-xs font-semibold text-[#5c4327]">{r.input}</span>
              <span className={`rounded border px-1.5 py-px text-[9px] uppercase ${SIG[r.signal]}`}>{r.signal}</span>
              <span className="w-10 text-right text-[11px] font-semibold tabular-nums text-[#5c4327]">
                {r.available ? `${r.score > 0 ? '+' : ''}${Math.round(r.score)}` : '—'}
              </span>
              <span className="w-12 text-right text-[10px] text-[#b39a76]">w {Math.round(r.weight * 100)}%</span>
            </div>
            {r.available && <div className="mt-1"><Bar2 score={r.score} /></div>}
            <p className="mt-1 text-[10.5px] leading-snug text-[#97795a]">{r.reason}</p>
          </div>
        ))}
      </div>
      <Note>
        {overall.available} of {rows.length} inputs are live: {overall.bullish} bullish, {overall.bearish} bearish, {overall.neutral} neutral → overall{' '}
        <b>{overall.score > 0 ? '+' : ''}{overall.score}</b> ({overall.stance}).
        {lift && drag && lift.key !== drag.key && (
          <> The biggest lift is {lift.input.toLowerCase()} ({lift.score > 0 ? '+' : ''}{Math.round(lift.score)}); the biggest drag is {drag.input.toLowerCase()} ({Math.round(drag.score)}). Act only where the two agree with price.</>
        )}
      </Note>
    </div>
  );
}

/* ── natal vs today ────────────────────────────────────────────────────── */
export function NatalToday({ nvt }: { nvt: NatalVsToday }) {
  const toK = (p: NatalVsToday['natal_chart']): KundaliPlanet[] =>
    p.map((x) => ({ name: x.name, signNumber: x.signNumber, degree: x.degree, retrograde: x.retrograde, house: x.house, dignity: x.dignity, nakshatra: x.nakshatra, pada: x.pada }));
  return (
    <div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="flex flex-col items-center rounded-lg border border-[#f0e4cc] bg-[#fffdf6]/80 p-2">
          <p className="mb-1 text-[11px] font-semibold text-[#8a6a3a]">Janma Kundli (natal) · Lagna {nvt.lagna_sign}</p>
          <NorthIndianChart lagnaSignNumber={nvt.lagna_sign_number} planets={toK(nvt.natal_chart)} size={300} title="Natal chart" />
        </div>
        <div className="flex flex-col items-center rounded-lg border border-[#f0e4cc] bg-[#fffdf6]/80 p-2">
          <p className="mb-1 text-[11px] font-semibold text-[#8a6a3a]">Today&apos;s sky (gochar) on your Lagna</p>
          <NorthIndianChart lagnaSignNumber={nvt.lagna_sign_number} planets={toK(nvt.today_chart)} size={300} title="Transit chart" />
        </div>
      </div>
      <div className="mt-3 overflow-x-auto rounded-lg border border-[#f0e4cc]">
        <table className="w-full min-w-[560px] text-[11px]">
          <thead className="bg-[#f8eedb] text-[10px] uppercase tracking-wide text-[#97795a]">
            <tr>
              <th className="px-2 py-1.5 text-left">Graha</th>
              <th className="px-2 py-1.5 text-left">Natal</th>
              <th className="px-2 py-1.5 text-right">Strength</th>
              <th className="px-2 py-1.5 text-left">Today</th>
              <th className="px-2 py-1.5 text-right">From Moon</th>
              <th className="px-2 py-1.5 text-left">Gochar</th>
            </tr>
          </thead>
          <tbody>
            {nvt.rows.map((r) => (
              <tr key={r.graha} className="border-t border-[#f3e8d2] text-[#5c4327]">
                <td className="px-2 py-1 font-semibold">{r.graha}</td>
                <td className="px-2 py-1">
                  {r.natal_sign} {r.natal_degree.toFixed(1)}° · H{r.natal_house}
                  {r.natal_retro && r.graha !== 'Rahu' && r.graha !== 'Ketu' ? ' ℞' : ''}
                  <span className="block text-[9.5px] text-[#b39a76]">{r.natal_nakshatra} · {r.natal_dignity}</span>
                </td>
                <td className="px-2 py-1 text-right tabular-nums">{r.strength ?? '—'}</td>
                <td className="px-2 py-1">
                  {r.today_sign} {r.today_degree.toFixed(1)}° · H{r.today_house}
                  {r.today_retro && r.graha !== 'Rahu' && r.graha !== 'Ketu' ? ' ℞' : ''}
                  <span className="block text-[9.5px] text-[#b39a76]">{r.today_nakshatra}</span>
                </td>
                <td className="px-2 py-1 text-right tabular-nums">{r.house_from_moon}</td>
                <td className="px-2 py-1">
                  <span className={`rounded border px-1 text-[9px] uppercase ${r.gochar === 'favourable' ? SIG.bullish : SIG.bearish}`}>{r.gochar}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {nvt.activations.length > 0 && (
        <div className="mt-3">
          <p className="mb-1 text-[11px] font-semibold text-[#8a6a3a]">Transits activating natal points</p>
          <div className="grid grid-cols-1 gap-1.5 md:grid-cols-2">
            {nvt.activations.slice(0, 8).map((a, i) => (
              <div key={i} className="rounded-md border border-[#f0e4cc] bg-[#fffdf6]/80 px-2 py-1.5 text-[10.5px] text-[#7c5a2e]">
                <span className={`mr-1 rounded border px-1 text-[9px] uppercase ${a.tone === 'supportive' ? SIG.bullish : a.tone === 'testing' ? SIG.bearish : SIG.neutral}`}>
                  {a.tone}
                </span>
                <b>{a.transit}</b> {a.aspect} natal <b>{a.natal}</b> ({a.orb}°) — {a.meaning.split(': ')[1] ?? a.meaning}
              </div>
            ))}
          </div>
        </div>
      )}
      {nvt.flags.map((f) => (
        <p key={f.flag} className={`mt-2 rounded-md border px-3 py-1.5 text-[11px] ${f.tone === 'supportive' ? SIG.bullish : SIG.bearish}`}>
          <b>{f.flag}:</b> {f.text}
        </p>
      ))}
      <Note>{nvt.interpretation}</Note>
    </div>
  );
}

/* ── 30 / 60 / 90 / 365 plans ─────────────────────────────────────────── */
function Cell2({ k, v, tone }: { k: string; v: string; tone?: string }) {
  return (
    <div className="rounded-md border border-[#f0e4cc] bg-[#fffdf6] px-2 py-1.5">
      <p className="text-[9.5px] uppercase tracking-wide text-[#b39a76]">{k}</p>
      <p className={`text-xs font-semibold tabular-nums ${tone ?? 'text-[#5c4327]'}`}>{v}</p>
    </div>
  );
}

export function HorizonPlans({ plans }: { plans: HorizonPlan[] }) {
  const [sel, setSel] = useState(0);
  const p = plans[sel];
  if (!p) return null;
  const bearish = p.signal === 'bearish';
  return (
    <div>
      <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
        {plans.map((x, i) => (
          <button
            key={x.days}
            onClick={() => setSel(i)}
            className={`rounded-lg border px-2 py-1.5 text-left ${i === sel ? 'border-[#d9b46a] bg-[#fdf3dc]' : 'border-[#f0e4cc] bg-[#fffdf6]/80'}`}
          >
            <p className="text-[10px] uppercase tracking-wide text-[#97795a]">{x.days === 365 ? '1 year' : `${x.days} days`}</p>
            <p className="text-[11px] font-semibold text-[#5c4327]">{x.stance}</p>
            <p className={`text-[10px] ${SIG[x.signal]?.split(' ').pop()}`}>score {x.score > 0 ? '+' : ''}{Math.round(x.score)}</p>
          </button>
        ))}
      </div>
      <div className="mt-3 rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/70 p-3">
        <p className="text-xs font-semibold text-[#5c4327]">{p.label} — {p.stance}</p>
        <div className="mt-2 grid grid-cols-2 gap-1.5 md:grid-cols-5">
          <Cell2 k={bearish ? 'Sell / hedge zone' : 'Entry zone'} v={`${fmtPx(p.entry_low)}–${fmtPx(p.entry_high)}`} />
          <Cell2 k="Stop" v={fmtPx(p.stop)} tone="text-[#a34332]" />
          <Cell2 k="Target 1" v={fmtPx(p.target_1)} tone="text-[#2f7357]" />
          <Cell2 k="Target 2" v={fmtPx(p.target_2)} tone="text-[#2f7357]" />
          <Cell2 k="1σ range" v={`${fmtPx(p.expected_range[0])}–${fmtPx(p.expected_range[1])}`} />
        </div>
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-[#8a6a3a]">Instrument approach</p>
            <ul className="space-y-0.5">
              {p.approach.map((a) => (
                <li key={a} className="text-[11px] text-[#7c5a2e]">• {a}</li>
              ))}
            </ul>
            <p className="mb-1 mt-2 text-[10px] font-semibold uppercase tracking-wide text-[#8a6a3a]">Position sizing</p>
            <p className="text-[11px] text-[#7c5a2e]">
              Risk {p.position.risk_pct}% of capital per idea, max {p.position.max_alloc_pct}% allocation → about {fmtGbp(p.position.value)} in this stock.
            </p>
            <p className="mb-1 mt-2 text-[10px] font-semibold uppercase tracking-wide text-[#8a6a3a]">Income in this window (illustrative)</p>
            <p className="text-[11px] text-[#7c5a2e]">
              {fmtGbp(p.income_band.low)} – {fmtGbp(p.income_band.high)} (base {fmtGbp(p.income_band.base)}). {p.income_focus}
            </p>
          </div>
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-[#8a6a3a]">Key dates</p>
            {p.key_dates.length === 0 && <p className="text-[11px] text-[#b39a76]">No major dates in this window.</p>}
            <ul className="space-y-1">
              {p.key_dates.map((d) => (
                <li key={d.date + d.title} className="flex gap-2 text-[10.5px] leading-snug text-[#7c5a2e]">
                  <span className="w-[74px] shrink-0 tabular-nums font-semibold">{d.date}</span>
                  <span className="min-w-0">
                    <span className={`mr-1 rounded px-1 text-[9px] uppercase ${KIND[d.kind] ?? KIND.sky}`}>{d.kind}</span>
                    {d.title}
                    <span className="block text-[9.5px] text-[#b39a76]">{d.note}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <Note>{p.summary}</Note>
      </div>
    </div>
  );
}

/* ── income plan ──────────────────────────────────────────────────────── */
export function IncomePlan({ income }: { income: FinalStrategy['income'] }) {
  const data = [
    { k: 'Good year', v: income.required_capital.high, y: income.blended_yield.high },
    { k: 'Normal year', v: income.required_capital.base, y: income.blended_yield.base },
    { k: 'Poor year', v: income.required_capital.low, y: income.blended_yield.low },
  ];
  const bands: [string, FinalStrategy['income']['weekly_for_capital']][] = [
    ['Weekly', income.weekly_for_capital],
    ['Monthly', income.monthly_for_capital],
    ['Yearly', income.yearly_for_capital],
  ];
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      <div className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6]/80 p-3">
        <p className="text-[11px] font-semibold text-[#8a6a3a]">Capital needed for {fmtGbp(income.target_weekly)}/week</p>
        <div className="h-44 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <XAxis dataKey="k" tick={{ fontSize: 10, fill: '#97795a' }} />
              <YAxis tick={{ fontSize: 10, fill: '#97795a' }} tickFormatter={(v) => `£${Math.round(v / 1000)}k`} width={44} />
              <Tooltip formatter={(v) => [fmtGbp(Number(v)), 'capital needed']} contentStyle={{ fontSize: 11 }} />
              <ReferenceLine y={income.capital} stroke="#c98a2e" strokeDasharray="4 3" label={{ value: 'your capital', fontSize: 9, fill: '#c98a2e', position: 'insideTopRight' }} />
              <Bar dataKey="v" radius={[4, 4, 0, 0]}>
                {data.map((d) => (
                  <Cell key={d.k} fill={d.v <= income.capital ? '#8fcaa9' : '#e7a796'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="text-[10px] text-[#b39a76]">
          Blended ladder yields {Math.round(income.blended_yield.low * 100)}% / {Math.round(income.blended_yield.base * 100)}% /{' '}
          {Math.round(income.blended_yield.high * 100)}% a year (poor / normal / good). Green = your capital is enough.
        </p>
      </div>
      <div className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6]/80 p-3">
        <p className="text-[11px] font-semibold text-[#8a6a3a]">What {fmtGbp(income.capital)} could produce (illustrative)</p>
        <table className="mt-1 w-full text-[11px]">
          <thead className="text-[10px] uppercase text-[#b39a76]">
            <tr>
              <th className="text-left font-normal"></th>
              <th className="text-right font-normal">Low</th>
              <th className="text-right font-normal">Base</th>
              <th className="text-right font-normal">High</th>
            </tr>
          </thead>
          <tbody>
            {bands.map(([k, b]) => (
              <tr key={k} className="border-t border-[#f3e8d2] text-[#5c4327]">
                <td className="py-1">{k}</td>
                <td className="py-1 text-right tabular-nums">{fmtGbp(b.low)}</td>
                <td className="py-1 text-right font-semibold tabular-nums">{fmtGbp(b.base)}</td>
                <td className="py-1 text-right tabular-nums">{fmtGbp(b.high)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {income.ladder.length > 0 && (
          <>
            <p className="mt-2 text-[10px] font-semibold uppercase tracking-wide text-[#8a6a3a]">Suggested ladder</p>
            <ul className="space-y-0.5">
              {income.ladder.map((l) => (
                <li key={l.label} className="flex justify-between gap-2 text-[10.5px] text-[#7c5a2e]">
                  <span className="min-w-0">{Math.round(l.weight * 100)}% · {l.label}</span>
                  <span className="shrink-0 tabular-nums">{fmtGbp(l.allocation)} → ~{fmtGbp(l.target_weekly)}/wk</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
      <div className="md:col-span-2">
        <Note>{income.explain}{income.dasha_note ? ` ${income.dasha_note}` : ''}</Note>
      </div>
    </div>
  );
}

export function WeeklyRoutine({ items }: { items: FinalStrategy['weekly_routine'] }) {
  return (
    <ul className="grid grid-cols-1 gap-1.5 md:grid-cols-2">
      {items.map((it, i) => (
        <li key={i} className="flex gap-2 rounded-md border border-[#f0e4cc] bg-[#fffdf6]/80 px-2 py-1.5 text-[11px] text-[#7c5a2e]">
          <CheckSquare className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#45a79a]" />
          <span>
            <b className="text-[#5c4327]">{it.day}:</b> {it.task}
          </span>
        </li>
      ))}
    </ul>
  );
}

