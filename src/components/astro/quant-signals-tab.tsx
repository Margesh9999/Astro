'use client';

import { useMemo, useState } from 'react';
import { ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, Area } from 'recharts';
import { quantDeskApi, type SignalRule, type SignalsResponse } from '@/lib/astro/api-quant';
import {
  AXIS_TICK, C, ChartTitle, HeatGrid, InsightBox, LoadState, SectionTitle, SignalPill, TIP_STYLE,
  divergeStyle, fmtSigned, shortDate, signColor, useQuant,
} from './quant-ui';

const FAMILIES = ['All', 'Trend', 'Momentum', 'Mean-reversion', 'Breakout', 'Volume'] as const;

/** semicircle consensus gauge, −100 … +100 */
export function ConsensusGauge({ score, label }: { score: number; label: string }) {
  const s = Math.max(-100, Math.min(100, score));
  const ang = Math.PI * (1 - (s + 100) / 200); // π (left) … 0 (right)
  const cx = 100, cy = 92, R = 78;
  const nx = cx + R * 0.86 * Math.cos(ang);
  const ny = cy - R * 0.86 * Math.sin(ang);
  const arc = (a0: number, a1: number) => {
    const p0 = [cx + R * Math.cos(a0), cy - R * Math.sin(a0)];
    const p1 = [cx + R * Math.cos(a1), cy - R * Math.sin(a1)];
    return `M ${p0[0]} ${p0[1]} A ${R} ${R} 0 0 1 ${p1[0]} ${p1[1]}`;
  };
  const color = signColor(s >= 15 ? 1 : s <= -15 ? -1 : 0);
  return (
    <svg viewBox="0 0 200 112" className="h-auto w-full max-w-[220px]" role="img" aria-label={`Consensus ${s} ${label}`}>
      <path d={arc(Math.PI, Math.PI * 0.75)} stroke="#e6a99f" strokeWidth={14} fill="none" />
      <path d={arc(Math.PI * 0.75, Math.PI * 0.575)} stroke="#f0cfc4" strokeWidth={14} fill="none" />
      <path d={arc(Math.PI * 0.575, Math.PI * 0.425)} stroke="#f3e6c9" strokeWidth={14} fill="none" />
      <path d={arc(Math.PI * 0.425, Math.PI * 0.25)} stroke="#cfe6d6" strokeWidth={14} fill="none" />
      <path d={arc(Math.PI * 0.25, 0)} stroke="#9fd0b6" strokeWidth={14} fill="none" />
      <line x1={cx} y1={cy} x2={nx} y2={ny} stroke={color} strokeWidth={3} strokeLinecap="round" />
      <circle cx={cx} cy={cy} r={5} fill={color} />
      <text x={cx} y={cy - 22} textAnchor="middle" fontSize="18" fontWeight={700} fill={color} fontFamily="monospace">
        {s > 0 ? '+' : ''}{Math.round(s)}
      </text>
      <text x={cx} y={110} textAnchor="middle" fontSize="11" fontWeight={600} fill="#5c4327">{label}</text>
      <text x={14} y={110} fontSize="8" fill="#b39a76">SELL</text>
      <text x={186} y={110} fontSize="8" fill="#b39a76" textAnchor="end">BUY</text>
    </svg>
  );
}

function ConsensusHistory({ data }: { data: SignalsResponse['consensus']['history'] }) {
  const rows = data.dates.map((d, i) => ({ date: d, score: data.score[i], close: data.close[i] }));
  return (
    <div className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <XAxis dataKey="date" tick={AXIS_TICK} tickFormatter={shortDate} minTickGap={40} />
          <YAxis yAxisId="s" domain={[-100, 100]} tick={AXIS_TICK} width={28} />
          <YAxis yAxisId="p" orientation="right" hide domain={['auto', 'auto']} />
          <Tooltip contentStyle={TIP_STYLE} labelFormatter={(l) => String(l)}
            formatter={(v, n) => (n === 'score' ? [Number(v).toFixed(0), 'Consensus'] : [Number(v).toLocaleString(), 'Close'])} />
          <ReferenceLine yAxisId="s" y={0} stroke="#d9c9a4" />
          <ReferenceLine yAxisId="s" y={30} stroke={C.green} strokeDasharray="3 3" strokeWidth={0.7} />
          <ReferenceLine yAxisId="s" y={-30} stroke={C.red} strokeDasharray="3 3" strokeWidth={0.7} />
          <Area yAxisId="s" type="monotone" dataKey="score" stroke={C.lilac} fill="rgba(155,138,196,0.18)" strokeWidth={1.2} isAnimationActive={false} />
          <Line yAxisId="p" type="monotone" dataKey="close" stroke={C.copper} strokeWidth={1.4} dot={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function RuleCard({ r }: { r: SignalRule }) {
  const bt = r.backtest;
  const beat = bt.cagr !== null && bt.bh_cagr !== null && bt.cagr >= bt.bh_cagr;
  const readout = Object.entries(r.readout).filter(([, v]) => v !== null).slice(0, 4);
  return (
    <div className="flex min-w-0 flex-col rounded-lg border border-[#f0e4cc] bg-[#fffdf6] p-2.5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-xs font-semibold text-[#5c4327]" title={r.name}>{r.name}</p>
          <p className="truncate text-[9px] uppercase tracking-wide text-[#b39a76]" title={r.source}>{r.family} · {r.source}</p>
        </div>
        <div className="flex flex-col items-end gap-0.5">
          <SignalPill signal={r.signal} />
          <span className="whitespace-nowrap text-[9px] text-[#b39a76]">{r.fresh ? 'fresh · ' : ''}{r.age_days}d</span>
        </div>
      </div>
      <div className="mt-1.5 grid grid-cols-4 gap-1 text-center text-[10px]">
        <div className="rounded bg-[#fdf8ec] px-1 py-0.5">
          <p className="text-[8px] uppercase text-[#b39a76]">Hit</p>
          <p className="font-mono font-semibold" style={{ color: (bt.hit_rate ?? 0) >= 52 ? C.green : (bt.hit_rate ?? 0) < 48 ? C.red : C.brown }}>
            {bt.hit_rate !== null ? `${bt.hit_rate.toFixed(0)}%` : '—'}
          </p>
        </div>
        <div className="rounded bg-[#fdf8ec] px-1 py-0.5">
          <p className="text-[8px] uppercase text-[#b39a76]">20d · buy</p>
          <p className="font-mono font-semibold" style={{ color: signColor(bt.avg_fwd20_buy) }}>{fmtSigned(bt.avg_fwd20_buy, 1)}</p>
        </div>
        <div className="rounded bg-[#fdf8ec] px-1 py-0.5">
          <p className="text-[8px] uppercase text-[#b39a76]">CAGR / B&amp;H</p>
          <p className="font-mono font-semibold" style={{ color: beat ? C.green : C.brown }}>
            {bt.cagr !== null ? bt.cagr.toFixed(1) : '—'}/{bt.bh_cagr !== null ? bt.bh_cagr.toFixed(1) : '—'}
          </p>
        </div>
        <div className="rounded bg-[#fdf8ec] px-1 py-0.5">
          <p className="text-[8px] uppercase text-[#b39a76]">Max DD</p>
          <p className="font-mono font-semibold text-[#c9553f]">{bt.max_dd !== null ? `${bt.max_dd.toFixed(0)}%` : '—'}</p>
        </div>
      </div>
      {readout.length > 0 && (
        <p className="mt-1 truncate font-mono text-[9px] text-[#97795a]" title={readout.map(([k, v]) => `${k} ${v}`).join(' · ')}>
          {readout.map(([k, v]) => `${k} ${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`).join(' · ')}
        </p>
      )}
      <p className="mt-1 text-[10px] leading-snug text-[#8a7350]">{r.rule}</p>
      <p className="mt-1 text-[10px] leading-snug text-[#7c5a2e]">{r.insight.means}</p>
      <p className="mt-1 text-[10px] font-medium leading-snug text-[#5c4327]">→ {r.insight.action}</p>
    </div>
  );
}

export function QuantSignalsTab({ symbol }: { symbol: string }) {
  const { data, error, loading } = useQuant(symbol, quantDeskApi.signals);
  const [fam, setFam] = useState<(typeof FAMILIES)[number]>('All');
  const rules = useMemo(() => (data ? data.rules.filter((r) => fam === 'All' || r.family === fam) : []), [data, fam]);
  if (!data) return <LoadState loading={loading} error={error} what="Signal board" />;
  const c = data.consensus;
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-[230px_1fr]">
        <div className="flex flex-col items-center rounded-lg border border-[#eed9b4] bg-gradient-to-b from-[#fdf3dc] to-[#fffdf6] p-2">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-[#97795a]">Edge-weighted consensus</p>
          <ConsensusGauge score={c.weighted_score} label={c.label} />
          <div className="mt-1 flex gap-2 text-[10px]">
            <span className="text-[#2f7357]">{c.buy} buy</span>
            <span className="text-[#a14d3c]">{c.sell} sell</span>
            <span className="text-[#8a6a3a]">{c.neutral} neutral</span>
          </div>
          <p className="text-[9px] text-[#b39a76]">simple vote {c.score > 0 ? '+' : ''}{c.score}</p>
        </div>
        <div className="min-w-0">
          <ChartTitle>Consensus score (lilac, left axis) vs price (copper) · last 2 years</ChartTitle>
          <ConsensusHistory data={c.history} />
        </div>
      </div>
      <InsightBox insight={c.insight} />

      <SectionTitle>Signal board · {data.rules.length} classic rules</SectionTitle>
      <div className="flex flex-wrap gap-1">
        {FAMILIES.map((f) => (
          <button key={f} onClick={() => setFam(f)}
            className={`rounded-full border px-2.5 py-1 text-[10px] font-medium transition ${
              fam === f ? 'border-[#d98324] bg-[#fbe3bd] text-[#7c4a12]' : 'border-[#ecdec2] bg-[#fffdf6]/80 text-[#97795a] hover:border-[#d9b46a]'}`}>
            {f}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {rules.map((r) => <RuleCard key={r.key} r={r} />)}
      </div>
      <p className="text-[10px] text-[#b39a76]">
        Hit = share of fresh signals that were right 20 trading days later · 20d·buy = average return over the 20 days after a fresh BUY ·
        CAGR/B&amp;H = long-or-cash rule vs buy-and-hold, %/yr. {data.method}
        {!data.has_volume && ' Volume rules hidden: this symbol has no reliable volume data.'}
      </p>

      <SectionTitle>Which rules actually predict? (forward-return edge)</SectionTitle>
      <HeatGrid
        rows={data.horizon_heatmap.rows.map((r) => r.name)}
        cols={data.horizon_heatmap.horizons.map((h) => `next ${h}`)}
        values={data.horizon_heatmap.rows.map((r) => r.values)}
        style={(v) => divergeStyle(v, 1.0)}
        fmt={(v) => (v === null ? '·' : `${v > 0 ? '+' : ''}${v.toFixed(2)}`)}
        title={(r, cl, v) => `${r} in BUY mode, ${cl}: ${v === null ? 'n/a' : `${v.toFixed(2)}% vs an average day`}`}
      />
      <p className="text-[10px] text-[#b39a76]">
        Cells = extra % return vs an average {data.symbol} day while the rule was in BUY mode. Baseline:{' '}
        {Object.entries(data.horizon_heatmap.baseline).map(([k, v]) => `${k} ${fmtSigned(v, 2)}`).join(' · ')}.
      </p>
      <InsightBox insight={data.horizon_heatmap.insight} />
    </div>
  );
}
