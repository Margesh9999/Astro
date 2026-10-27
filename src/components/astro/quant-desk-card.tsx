'use client';

import { useEffect, useState } from 'react';
import {
  Area, AreaChart, Bar, BarChart, Cell, ComposedChart, Line, LineChart,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { quantApi, enhanceApi } from '@/lib/astro/api';
import type { AnalyticsPack, QuantRiskResponse, QuantStatsResponse } from '@/lib/astro/types';
import { Briefcase, ShieldAlert, Lightbulb, TrendingUp, TrendingDown, MoveRight } from 'lucide-react';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function pct(n: number | null | undefined, d = 1) {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return `${(n * 100).toFixed(d)}%`;
}

function num(n: number | null | undefined, d = 2) {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return n.toFixed(d);
}

function heatStyle(v: number | null | undefined) {
  if (v === null || v === undefined) return { background: '#faf4e4', color: '#b39a76' };
  const x = Math.max(-0.12, Math.min(0.12, v));
  if (x >= 0) {
    const a = 0.12 + (x / 0.12) * 0.55;
    return { background: `rgba(74,154,126,${a})`, color: '#22423a' };
  }
  const a = 0.12 + (-x / 0.12) * 0.55;
  return { background: `rgba(207,91,84,${a})`, color: '#5c2620' };
}

function corrStyle(v: number | null | undefined) {
  if (v === null || v === undefined) return { background: '#faf4e4', color: '#b39a76' };
  const x = Math.max(-1, Math.min(1, v));
  if (x >= 0) {
    const a = 0.1 + x * 0.6;
    return { background: `rgba(74,154,126,${a})`, color: '#22423a' };
  }
  const a = 0.1 + -x * 0.6;
  return { background: `rgba(207,91,84,${a})`, color: '#5c2620' };
}

/** T1: the "why it matters" ribbon under every chart */
function Interpretation({ text }: { text: string }) {
  return (
    <div className="mt-2 flex items-start gap-1.5 rounded-lg border border-[#e8ddb8] bg-[#fdf8ec] px-2.5 py-2">
      <Lightbulb className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-[#c98a2e]" />
      <p className="text-[11px] leading-relaxed text-[#7c5a2e]">{text}</p>
    </div>
  );
}

const TIP_STYLE = {
  background: '#fffdf6',
  border: '1px solid #ecdec2',
  borderRadius: 8,
  fontSize: 11,
} as const;

function ChartTitle({ children }: { children: React.ReactNode }) {
  return <p className="mb-1 text-xs font-medium text-[#5c4327]">{children}</p>;
}

/* ── chart components ─────────────────────────────────────────────────────── */

function PriceMAs({ pack }: { pack: AnalyticsPack }) {
  const s = pack.price.series;
  const data = s.dates.map((d, i) => ({
    date: d,
    close: s.close[i],
    sma20: s.sma20[i],
    sma50: s.sma50[i],
    sma200: s.sma200[i],
  }));
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: 4 }}>
          <YAxis hide domain={['auto', 'auto']} />
          <Tooltip contentStyle={TIP_STYLE} labelFormatter={(l) => String(l)} />
          <Line type="monotone" dataKey="close" stroke="#b0763a" strokeWidth={1.6} dot={false} isAnimationActive={false} name="Close" />
          <Line type="monotone" dataKey="sma20" stroke="#4fa8a0" strokeWidth={1} dot={false} isAnimationActive={false} name="SMA20" />
          <Line type="monotone" dataKey="sma50" stroke="#9b8ac4" strokeWidth={1} dot={false} isAnimationActive={false} name="SMA50" />
          <Line type="monotone" dataKey="sma200" stroke="#d96f85" strokeWidth={1} dot={false} isAnimationActive={false} name="SMA200" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function VolChart({ pack }: { pack: AnalyticsPack }) {
  const data = pack.volatility.series.dates.map((d, i) => ({ date: d, vol: pack.volatility.series.vol[i] }));
  return (
    <div className="h-40 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: 4 }}>
          <defs>
            <linearGradient id="volFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#db8a3a" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#db8a3a" stopOpacity={0.03} />
            </linearGradient>
          </defs>
          <YAxis hide />
          <Tooltip contentStyle={TIP_STYLE} formatter={(v) => [`${Number(v).toFixed(1)}%`, '21d vol']} />
          <Area type="monotone" dataKey="vol" stroke="#db8a3a" strokeWidth={1.3} fill="url(#volFill)" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function RsiChart({ pack }: { pack: AnalyticsPack }) {
  const data = pack.rsi.series.dates.map((d, i) => ({ date: d, rsi: pack.rsi.series.rsi[i] }));
  return (
    <div className="h-36 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: 4 }}>
          <YAxis hide domain={[0, 100]} />
          <Tooltip contentStyle={TIP_STYLE} formatter={(v) => [Number(v).toFixed(0), 'RSI14']} />
          <ReferenceLine y={70} stroke="#cf5b54" strokeDasharray="3 3" strokeWidth={0.8} />
          <ReferenceLine y={30} stroke="#3f8a6e" strokeDasharray="3 3" strokeWidth={0.8} />
          <Line type="monotone" dataKey="rsi" stroke="#6fa96f" strokeWidth={1.2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function LongDrawdown({ pack }: { pack: AnalyticsPack }) {
  const data = pack.drawdown.series.dates.map((d, i) => ({ date: d, dd: pack.drawdown.series.dd[i] }));
  return (
    <div className="h-44 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: 4 }}>
          <defs>
            <linearGradient id="ddLongFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#cf5b54" stopOpacity={0.05} />
              <stop offset="100%" stopColor="#cf5b54" stopOpacity={0.4} />
            </linearGradient>
          </defs>
          <YAxis hide domain={['dataMin', 0]} />
          <Tooltip contentStyle={TIP_STYLE} formatter={(v) => [`${Number(v).toFixed(2)}%`, 'Drawdown']} />
          <Area type="monotone" dataKey="dd" stroke="#cf5b54" strokeWidth={1.2} fill="url(#ddLongFill)" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function SeasonBars({ pack }: { pack: AnalyticsPack }) {
  const data = pack.seasonality.by_month.map((v, i) => ({ month: MONTHS[i], avg: v }));
  return (
    <div className="h-36 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: 4 }}>
          <YAxis hide />
          <Tooltip contentStyle={TIP_STYLE} formatter={(v) => [`${Number(v).toFixed(2)}%`, 'avg month']} />
          <Area type="monotone" dataKey="avg" stroke="#9b8ac4" strokeWidth={1.4} fill="rgba(155,138,196,0.12)" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function MonthlyHeatmap({ pack }: { pack: AnalyticsPack }) {
  return (
    <div className="warm-scroll overflow-x-auto">
      <table className="w-full min-w-[520px] border-separate border-spacing-0.5 text-center text-[10px]">
        <thead>
          <tr>
            <th className="text-[#b39a76]">Yr</th>
            {MONTHS.map((m) => (
              <th key={m} className="font-medium text-[#b39a76]">{m}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {pack.heatmap.years.map((y, yi) => (
            <tr key={y}>
              <td className="font-mono text-[#97795a]">{y}</td>
              {pack.heatmap.values[yi].map((v, mi) => {
                const style = heatStyle(v === null ? null : v / 100);
                return (
                  <td key={mi} className="rounded font-mono" style={{ ...style, padding: '2px 1px' }}
                      title={v !== null ? `${MONTHS[mi]} ${y}: ${v.toFixed(2)}%` : ''}>
                    {v !== null ? v.toFixed(0) : '·'}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MacdChart({ pack }: { pack: NonNullable<AnalyticsPack['macd']> }) {
  const s = pack.series;
  const data = s.dates.map((d, i) => ({ date: d, macd: s.macd[i], signal: s.signal[i], hist: s.hist[i] }));
  return (
    <div className="h-44 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: 4 }}>
          <YAxis hide />
          <Tooltip contentStyle={TIP_STYLE} labelFormatter={(l) => String(l)} />
          <ReferenceLine y={0} stroke="#c9b58a" strokeWidth={0.8} />
          <Bar dataKey="hist" name="Histogram" isAnimationActive={false}>
            {data.map((row, i) => (
              <Cell key={i} fill={(row.hist ?? 0) >= 0 ? 'rgba(111,169,111,0.55)' : 'rgba(207,91,84,0.55)'} />
            ))}
          </Bar>
          <Line type="monotone" dataKey="macd" stroke="#b0763a" strokeWidth={1.3} dot={false} isAnimationActive={false} name="MACD" />
          <Line type="monotone" dataKey="signal" stroke="#4fa8a0" strokeWidth={1} dot={false} isAnimationActive={false} name="Signal" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function BollingerChart({ pack }: { pack: NonNullable<AnalyticsPack['bollinger']> }) {
  const s = pack.series;
  const data = s.dates.map((d, i) => ({ date: d, close: s.close[i], upper: s.upper[i], mid: s.mid[i], lower: s.lower[i] }));
  return (
    <div className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: 4 }}>
          <YAxis hide domain={['auto', 'auto']} />
          <Tooltip contentStyle={TIP_STYLE} labelFormatter={(l) => String(l)} />
          <Line type="monotone" dataKey="upper" stroke="#c9b58a" strokeWidth={0.8} dot={false} isAnimationActive={false} name="Upper band" />
          <Line type="monotone" dataKey="lower" stroke="#c9b58a" strokeWidth={0.8} dot={false} isAnimationActive={false} name="Lower band" />
          <Line type="monotone" dataKey="mid" stroke="#9b8ac4" strokeWidth={0.8} strokeDasharray="3 3" dot={false} isAnimationActive={false} name="20d mid" />
          <Line type="monotone" dataKey="close" stroke="#b0763a" strokeWidth={1.4} dot={false} isAnimationActive={false} name="Close" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function StochChart({ pack }: { pack: NonNullable<AnalyticsPack['stochastic']> }) {
  const s = pack.series;
  const data = s.dates.map((d, i) => ({ date: d, k: s.k[i], d: s.d[i] }));
  return (
    <div className="h-36 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: 4 }}>
          <YAxis hide domain={[0, 100]} />
          <Tooltip contentStyle={TIP_STYLE} />
          <ReferenceLine y={80} stroke="#cf5b54" strokeDasharray="3 3" strokeWidth={0.8} />
          <ReferenceLine y={20} stroke="#3f8a6e" strokeDasharray="3 3" strokeWidth={0.8} />
          <Line type="monotone" dataKey="k" stroke="#4fa8a0" strokeWidth={1.2} dot={false} isAnimationActive={false} name="%K" />
          <Line type="monotone" dataKey="d" stroke="#d96f85" strokeWidth={1} dot={false} isAnimationActive={false} name="%D" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function AtrChart({ pack }: { pack: NonNullable<AnalyticsPack['atr']> }) {
  const data = pack.series.dates.map((d, i) => ({ date: d, atr: pack.series.atr_pct[i] }));
  return (
    <div className="h-36 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: 4 }}>
          <defs>
            <linearGradient id="atrFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#8a6a3a" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#8a6a3a" stopOpacity={0.03} />
            </linearGradient>
          </defs>
          <YAxis hide />
          <Tooltip contentStyle={TIP_STYLE} formatter={(v) => [`${Number(v).toFixed(2)}%`, 'ATR-14']} />
          <Area type="monotone" dataKey="atr" stroke="#8a6a3a" strokeWidth={1.2} fill="url(#atrFill)" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function ObvChart({ pack }: { pack: NonNullable<AnalyticsPack['obv']> }) {
  const data = pack.series.dates.map((d, i) => ({ date: d, obv: pack.series.obv[i] }));
  const fmt = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 });
  return (
    <div className="h-36 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: 4 }}>
          <defs>
            <linearGradient id="obvFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4fa8a0" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#4fa8a0" stopOpacity={0.03} />
            </linearGradient>
          </defs>
          <YAxis hide />
          <Tooltip contentStyle={TIP_STYLE} formatter={(v) => [fmt.format(Number(v)), 'OBV']} />
          <Area type="monotone" dataKey="obv" stroke="#4fa8a0" strokeWidth={1.2} fill="url(#obvFill)" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function RollingSharpeChart({ pack }: { pack: NonNullable<AnalyticsPack['rolling_sharpe']> }) {
  const data = pack.series.dates.map((d, i) => ({ date: d, sharpe: pack.series.sharpe[i] }));
  return (
    <div className="h-36 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: 4 }}>
          <YAxis hide />
          <Tooltip contentStyle={TIP_STYLE} formatter={(v) => [Number(v).toFixed(2), 'Sharpe (63d)']} />
          <ReferenceLine y={0} stroke="#c9b58a" strokeWidth={0.8} />
          <Line type="monotone" dataKey="sharpe" stroke="#9b8ac4" strokeWidth={1.2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function DistHistogram({ pack }: { pack: NonNullable<AnalyticsPack['distribution']> }) {
  return (
    <div className="h-40 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={pack.bins} margin={{ top: 4, right: 6, bottom: 0, left: 4 }}>
          <YAxis hide />
          <Tooltip contentStyle={TIP_STYLE}
            formatter={(v, _n, p) => [`${v} days`, `${(p.payload as { center: number }).center >= 0 ? '+' : ''}${(p.payload as { center: number }).center}σ day`]} />
          <ReferenceLine x={0} stroke="#c9b58a" strokeWidth={0.8} />
          <Bar dataKey="count" isAnimationActive={false}>
            {pack.bins.map((b, i) => (
              <Cell key={i} fill={b.center >= 0 ? 'rgba(111,169,111,0.6)' : 'rgba(207,91,84,0.6)'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function AcfBars({ pack }: { pack: NonNullable<AnalyticsPack['memory']> }) {
  return (
    <div className="h-32 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={pack.acf} margin={{ top: 4, right: 6, bottom: 0, left: 4 }}>
          <YAxis hide domain={[-0.3, 0.3]} />
          <Tooltip contentStyle={TIP_STYLE} formatter={(v) => [Number(v).toFixed(3), 'autocorr']} />
          <ReferenceLine y={0} stroke="#c9b58a" strokeWidth={0.8} />
          <Bar dataKey="value" isAnimationActive={false}>
            {pack.acf.map((a, i) => (
              <Cell key={i} fill={a.value >= 0 ? 'rgba(79,168,160,0.7)' : 'rgba(217,111,133,0.7)'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Monte-Carlo fan chart: 5–95% outer band + 25–75% inner band + median path */
function FanChart({ pack }: { pack: NonNullable<NonNullable<AnalyticsPack['forecast']>['mc']> }) {
  const data = pack.dates.map((d, i) => ({
    date: d,
    p5: pack.p5[i],
    band95: +(pack.p95[i] - pack.p5[i]).toFixed(2),
    p25: pack.p25[i],
    band75: +(pack.p75[i] - pack.p25[i]).toFixed(2),
    p50: pack.p50[i],
  }));
  return (
    <div className="h-52 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: 4 }}>
          <YAxis hide domain={['dataMin - 10', 'dataMax + 10']} />
          <Tooltip
            contentStyle={TIP_STYLE}
            labelFormatter={(l) => String(l)}
            formatter={(v, n) => {
              if (n === 'p50') return [Number(v).toLocaleString(), 'Median path'];
              if (n === 'band95') return [`${Number(v).toLocaleString()} wide`, '5–95% band'];
              return null;
            }}
          />
          <Area type="monotone" dataKey="p5" stackId="f95" stroke="none" fill="none" isAnimationActive={false} name="p5" />
          <Area type="monotone" dataKey="band95" stackId="f95" stroke="none" fill="rgba(176,118,58,0.14)" isAnimationActive={false} name="band95" />
          <Area type="monotone" dataKey="p25" stackId="f75" stroke="none" fill="none" isAnimationActive={false} name="p25" />
          <Area type="monotone" dataKey="band75" stackId="f75" stroke="none" fill="rgba(176,118,58,0.22)" isAnimationActive={false} name="band75" />
          <Line type="monotone" dataKey="p50" stroke="#b0763a" strokeWidth={1.6} dot={false} isAnimationActive={false} name="p50" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/** composite signal gauge −100..+100 */
function SignalGauge({ score, label }: { score: number; label: string }) {
  const pos = ((score + 100) / 200) * 100;
  const color = score >= 15 ? '#3f8a6e' : score <= -15 ? '#c9553f' : '#c98a2e';
  return (
    <div>
      <div className="relative h-7 w-full overflow-hidden rounded-full border border-[#ecdec2]"
           style={{ background: 'linear-gradient(90deg, rgba(207,91,84,0.45), rgba(253,248,236,0.9) 46%, rgba(253,248,236,0.9) 54%, rgba(111,169,111,0.45))' }}>
        <div className="absolute top-0 h-full w-1 rounded shadow" style={{ left: `calc(${pos}% - 2px)`, background: color }} />
        <div className="flex h-full items-center justify-center">
          <span className="font-mono text-xs font-bold" style={{ color }}>
            {score > 0 ? '+' : ''}{score} · {label}
          </span>
        </div>
      </div>
      <div className="mt-1 flex justify-between text-[9px] uppercase tracking-wide text-[#b39a76]">
        <span>Strong sell</span><span>Neutral</span><span>Strong buy</span>
      </div>
    </div>
  );
}

function CorrMatrix({ pack }: { pack: NonNullable<AnalyticsPack['correlations']> }) {
  return (
    <div className="warm-scroll overflow-x-auto">
      <table className="border-separate border-spacing-0.5 text-center text-[10px]">
        <thead>
          <tr>
            <th />
            {pack.matrix.symbols.map((s) => (
              <th key={s} className="px-1 font-mono font-medium text-[#b39a76]">{s === '@this' ? 'THIS' : s}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {pack.matrix.symbols.map((row, ri) => (
            <tr key={row}>
              <td className="pr-1 text-right font-mono text-[#97795a]">{row === '@this' ? 'THIS' : row}</td>
              {pack.matrix.values[ri].map((v, ci) => {
                const style = corrStyle(v);
                return (
                  <td key={ci} className="rounded font-mono" style={{ ...style, padding: '3px 4px' }}
                      title={`${row} × ${pack.matrix.symbols[ci]}: ${v ?? 'n/a'}`}>
                    {v !== null ? v.toFixed(2).replace('0.', '.') : '·'}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CorrBars({ pack }: { pack: NonNullable<AnalyticsPack['correlations']> }) {
  return (
    <div className="flex flex-col gap-1.5">
      {pack.pairs.map((p) => {
        const w = Math.abs(p.corr) * 50;
        return (
          <div key={p.symbol} className="flex items-center gap-2 text-[11px]">
            <span className="w-36 flex-shrink-0 truncate text-[#7c5a2e]">{p.name}</span>
            <div className="relative h-3.5 flex-1 rounded bg-[#faf4e4]">
              <div className="absolute inset-y-0 left-1/2 w-px bg-[#d9c9a4]" />
              <div className={`absolute inset-y-0 ${p.corr >= 0 ? 'left-1/2 bg-[#6fa96f]/60' : 'bg-[#cf5b54]/60 right-1/2'}`}
                   style={p.corr >= 0 ? { left: '50%', width: `${w}%` } : { right: '50%', width: `${w}%` }} />
            </div>
            <span className={`w-12 text-right font-mono ${p.corr >= 0 ? 'text-[#3f8a6e]' : 'text-[#c9553f]'}`}>
              {p.corr >= 0 ? '+' : ''}{p.corr.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ── main card ────────────────────────────────────────────────────────────── */

export function QuantDeskCard({ symbol }: { symbol: string }) {
  const [state, setState] = useState<{
    stats?: QuantStatsResponse;
    risk?: QuantRiskResponse;
    pack?: AnalyticsPack;
    packError?: string;
    error?: string;
  } | null>(null);

  useEffect(() => {
    let alive = true;
    Promise.allSettled([quantApi.quantStats(symbol, 3), quantApi.quantRisk(symbol, 3)])
      .then(([s, r]) => {
        if (!alive) return;
        if (s.status === 'rejected') {
          setState({ error: String(s.reason?.message ?? s.reason) });
        } else {
          setState({
            stats: s.value,
            risk: r.status === 'fulfilled' ? r.value : undefined,
          });
        }
      });
    // chart pack (full history, incl. round-3 blocks) — loaded independently
    enhanceApi
      .analyticsCharts(symbol)
      .then((pack) => alive && setState((prev) => ({ ...(prev ?? {}), pack })))
      .catch((e) => alive && setState((prev) => ({ ...(prev ?? {}), packError: String(e?.message ?? e) })));
    return () => {
      alive = false;
    };
  }, [symbol]);

  const stale = !!state?.stats && state.stats.symbol !== symbol;
  const loading = !state || stale;
  const error = state?.error ?? null;
  const pack = stale ? null : (state?.pack ?? null);
  const stats = stale ? null : (state?.stats ?? null);
  const risk = stale ? null : (state?.risk ?? null);

  const st = stats?.stats;
  const tiles: Array<[string, string, string]> = st
    ? [
        ['CAGR', pct(st.cagr), '#3f8a6e'],
        ['Ann. vol', pct(st.ann_vol), '#8a6a3a'],
        ['Sharpe', num(st.sharpe), st.sharpe && st.sharpe > 0 ? '#3f8a6e' : '#c9553f'],
        ['Sortino', num(st.sortino), '#8a6a3a'],
        ['Calmar', num(st.calmar), '#8a6a3a'],
        ['Max DD', pct(st.max_drawdown), '#c9553f'],
        ['Hit rate', pct(st.hit_rate), '#8a6a3a'],
        ['Skew / Kurt', `${num(st.skew, 2)} / ${num(st.kurtosis, 2)}`, '#8a6a3a'],
      ]
    : [];

  const fc = pack?.forecast;
  const stanceIcon = (stance: string) =>
    stance === 'bullish' ? <TrendingUp className="h-3 w-3 text-[#3f8a6e]" />
    : stance === 'bearish' ? <TrendingDown className="h-3 w-3 text-[#c9553f]" />
    : <MoveRight className="h-3 w-3 text-[#c98a2e]" />;

  return (
    <Card className="vedic-card flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Briefcase className="h-4 w-4 text-[#c98a2e]" />
            <CardTitle className="font-display text-base tracking-wide">Quant Desk</CardTitle>
          </div>
          <span className="rounded bg-[#f7ecd4] px-2 py-0.5 font-mono text-[10px] text-[#97795a]">
            {symbol}
            {pack ? ` · since ${pack.start}` : ' · 3y daily'}
          </span>
        </div>
        <CardDescription className="text-[#97795a]">
          ffn-style analytics · gs-quant risk · indicators, memory, correlations &amp; behaviour forecasts — every chart explains itself
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        {loading && !stats ? (
          <div className="grid grid-cols-4 gap-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-12 bg-[#efdfbc]" />
            ))}
          </div>
        ) : error && !stats ? (
          <div className="flex flex-1 items-center justify-center py-8 text-sm text-[#97795a]">
            Quant analytics unavailable — {error}
          </div>
        ) : (
          <Tabs defaultValue="overview" className="mt-0">
            <TabsList className="mb-3 flex-wrap bg-[#f4e8cf]">
              <TabsTrigger value="overview" className="text-xs data-[state=active]:bg-[#fffdf6]">Overview</TabsTrigger>
              <TabsTrigger value="charts" className="text-xs data-[state=active]:bg-[#fffdf6]">Trend Charts</TabsTrigger>
              <TabsTrigger value="momentum" className="text-xs data-[state=active]:bg-[#fffdf6]">Momentum &amp; Vol</TabsTrigger>
              <TabsTrigger value="memory" className="text-xs data-[state=active]:bg-[#fffdf6]">Volume &amp; Memory</TabsTrigger>
              <TabsTrigger value="correlations" className="text-xs data-[state=active]:bg-[#fffdf6]">Correlations</TabsTrigger>
              <TabsTrigger value="forecast" className="text-xs data-[state=active]:bg-[#fffdf6]">Forecast</TabsTrigger>
              <TabsTrigger value="heatmap" className="text-xs data-[state=active]:bg-[#fffdf6]">Monthly Heatmap</TabsTrigger>
            </TabsList>

            {/* ── Overview tab (original desk) ── */}
            <TabsContent value="overview" className="mt-0 flex flex-col gap-4">
              <div className="grid grid-cols-4 gap-2">
                {tiles.map(([label, value, color]) => (
                  <div key={label} className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6] px-2 py-1.5">
                    <p className="text-[10px] uppercase tracking-wide text-[#b39a76]">{label}</p>
                    <p className="font-mono text-sm font-semibold" style={{ color }}>{value}</p>
                  </div>
                ))}
              </div>

              {stats && stats.drawdown.length > 0 && (
                <div>
                  <p className="mb-1 text-xs text-[#97795a]">Drawdown profile (%) · 3y</p>
                  <div className="h-28 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={stats.drawdown} margin={{ top: 2, right: 4, bottom: 0, left: 4 }}>
                        <defs>
                          <linearGradient id="ddFill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#cf5b54" stopOpacity={0.05} />
                            <stop offset="100%" stopColor="#cf5b54" stopOpacity={0.4} />
                          </linearGradient>
                        </defs>
                        <YAxis hide domain={['dataMin', 0]} />
                        <Tooltip contentStyle={TIP_STYLE} labelFormatter={(l) => String(l)}
                          formatter={(v) => [`${Number(v).toFixed(2)}%`, 'Drawdown']} />
                        <Area type="monotone" dataKey="dd_pct" stroke="#cf5b54" strokeWidth={1.4}
                          fill="url(#ddFill)" isAnimationActive={false} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {risk?.risk && (
                <div className="flex items-start gap-2 rounded-lg border border-[#eed9b4] bg-[#fdf3dc] px-3 py-2">
                  <ShieldAlert className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#c98a2e]" />
                  <p className="text-[11px] leading-relaxed text-[#8a6a3a]">
                    1-day {Math.round(risk.risk.confidence * 100)}% VaR{' '}
                    <span className="font-mono font-semibold">${risk.risk.var_hist_usd.toLocaleString()}</span> ·
                    CVaR <span className="font-mono font-semibold">${risk.risk.cvar_hist_usd.toLocaleString()}</span>{' '}
                    on a ${risk.risk.position_value.toLocaleString()} position (historical,{' '}
                    {risk.risk.observations} obs).
                  </p>
                </div>
              )}
            </TabsContent>

            {/* ── Trend Charts tab ── */}
            <TabsContent value="charts" className="mt-0 flex flex-col gap-5">
              {!pack && !state?.packError && <Skeleton className="h-40 w-full bg-[#efdfbc]" />}
              {state?.packError && !pack && (
                <p className="text-xs text-[#a14d3c]">Chart pack unavailable — {state.packError}</p>
              )}
              {pack && (
                <>
                  <div>
                    <ChartTitle>Price with 20/50/200-day moving averages · since {pack.start}</ChartTitle>
                    <PriceMAs pack={pack} />
                    <Interpretation text={pack.price.interpretation} />
                  </div>

                  <div>
                    <ChartTitle>
                      Rolling 21-day volatility (annualised %) — now {pack.volatility.now_pct}%, typical{' '}
                      {pack.volatility.median_pct}%
                    </ChartTitle>
                    <VolChart pack={pack} />
                    <Interpretation text={pack.volatility.interpretation} />
                  </div>

                  <div>
                    <ChartTitle>Full-history drawdown — current {pack.drawdown.current}%, worst {pack.drawdown.max}%</ChartTitle>
                    <LongDrawdown pack={pack} />
                    <Interpretation text={pack.drawdown.interpretation} />
                  </div>

                  <div>
                    <ChartTitle>Average return by calendar month (%)</ChartTitle>
                    <SeasonBars pack={pack} />
                    <Interpretation
                      text={`Best month on record: ${pack.seasonality.best_month_ever}; worst: ${pack.seasonality.worst_month_ever}. ${pack.seasonality.best_month} has been the strongest month on average and ${pack.seasonality.worst_month} the weakest — time bigger entries and profit-taking around this rhythm.`}
                    />
                  </div>

                  <div className="grid grid-cols-5 gap-2 text-[11px]">
                    {Object.entries(pack.performance).map(([k, v]) => (
                      <div key={k} className="rounded bg-[#fdf8ec] px-2 py-1 text-center">
                        <p className="text-[9px] uppercase text-[#b39a76]">{k}</p>
                        <p className={`font-mono font-semibold ${v >= 0 ? 'text-[#3f8a6e]' : 'text-[#c9553f]'}`}>
                          {v >= 0 ? '+' : ''}{v}%
                        </p>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </TabsContent>

            {/* ── Momentum & Volatility tab ── */}
            <TabsContent value="momentum" className="mt-0 flex flex-col gap-5">
              {!pack && <Skeleton className="h-40 w-full bg-[#efdfbc]" />}
              {pack?.bollinger && (
                <div>
                  <ChartTitle>Bollinger bands (20, 2σ) — %B now {pack.bollinger.pct_b}, bands {pack.bollinger.lower_now} – {pack.bollinger.upper_now}</ChartTitle>
                  <BollingerChart pack={pack.bollinger} />
                  <Interpretation text={pack.bollinger.interpretation} />
                </div>
              )}
              {pack?.macd && (
                <div>
                  <ChartTitle>MACD (12, 26, 9) — line {pack.macd.macd_now}, signal {pack.macd.signal_now}, histogram {pack.macd.hist_now}</ChartTitle>
                  <MacdChart pack={pack.macd} />
                  <Interpretation text={pack.macd.interpretation} />
                </div>
              )}
              {pack && (
                <div>
                  <ChartTitle>RSI-14 momentum — now {pack.rsi.now}</ChartTitle>
                  <RsiChart pack={pack} />
                  <Interpretation text={pack.rsi.interpretation} />
                </div>
              )}
              {pack?.stochastic && (
                <div>
                  <ChartTitle>Stochastic oscillator (14, 3, 3) — %K {pack.stochastic.k_now}, %D {pack.stochastic.d_now}</ChartTitle>
                  <StochChart pack={pack.stochastic} />
                  <Interpretation text={pack.stochastic.interpretation} />
                </div>
              )}
              {pack?.atr && (
                <div>
                  <ChartTitle>ATR-14 as % of price — now {pack.atr.now_pct}% (the daily swing budget)</ChartTitle>
                  <AtrChart pack={pack.atr} />
                  <Interpretation text={pack.atr.interpretation} />
                </div>
              )}
              {!pack && state?.packError && (
                <p className="text-xs text-[#a14d3c]">Chart pack unavailable — {state.packError}</p>
              )}
            </TabsContent>

            {/* ── Volume & Memory tab ── */}
            <TabsContent value="memory" className="mt-0 flex flex-col gap-5">
              {!pack && <Skeleton className="h-40 w-full bg-[#efdfbc]" />}
              {pack?.obv && (
                <div>
                  <ChartTitle>On-Balance Volume (rebased) — 20-day trend {pack.obv.trend_20d}</ChartTitle>
                  <ObvChart pack={pack.obv} />
                  <Interpretation text={pack.obv.interpretation} />
                </div>
              )}
              {pack?.rolling_sharpe && (
                <div>
                  <ChartTitle>Rolling 63-day Sharpe — now {pack.rolling_sharpe.now}</ChartTitle>
                  <RollingSharpeChart pack={pack.rolling_sharpe} />
                  <Interpretation text={pack.rolling_sharpe.interpretation} />
                </div>
              )}
              {pack?.distribution && (
                <div>
                  <ChartTitle>Distribution of daily returns (in σ units) — 1-day 95% VaR {pack.distribution.var95_daily_pct}%, worst day {pack.distribution.worst_day_pct}%</ChartTitle>
                  <DistHistogram pack={pack.distribution} />
                  <Interpretation text={pack.distribution.interpretation} />
                </div>
              )}
              {pack?.memory && (
                <div>
                  <ChartTitle>
                    Autocorrelation of daily returns (lags 1–10) · Hurst {pack.memory.hurst} →{' '}
                    <span className={pack.memory.regime === 'trending' ? 'text-[#3f8a6e]' : pack.memory.regime === 'mean-reverting' ? 'text-[#c9553f]' : 'text-[#c98a2e]'}>
                      {pack.memory.regime} regime
                    </span>
                  </ChartTitle>
                  <AcfBars pack={pack.memory} />
                  <Interpretation text={pack.memory.interpretation} />
                </div>
              )}
              {!pack && state?.packError && (
                <p className="text-xs text-[#a14d3c]">Chart pack unavailable — {state.packError}</p>
              )}
            </TabsContent>

            {/* ── Correlations tab ── */}
            <TabsContent value="correlations" className="mt-0 flex flex-col gap-4">
              {!pack && <Skeleton className="h-40 w-full bg-[#efdfbc]" />}
              {pack?.correlations ? (
                <>
                  <div>
                    <ChartTitle>Correlation of daily returns · past year ({pack.correlations.observation_days} obs) · THIS = {symbol}</ChartTitle>
                    <CorrMatrix pack={pack.correlations} />
                  </div>
                  <CorrBars pack={pack.correlations} />
                  <Interpretation text={pack.correlations.interpretation} />
                </>
              ) : pack ? (
                <p className="text-xs text-[#97795a]">
                  Cross-asset correlations need ~1 year of overlapping daily data for this symbol plus the
                  benchmark set — not available right now.
                </p>
              ) : null}
            </TabsContent>

            {/* ── Forecast tab — predictions from observed behaviour ── */}
            <TabsContent value="forecast" className="mt-0 flex flex-col gap-5">
              {!pack && !fc && <Skeleton className="h-40 w-full bg-[#efdfbc]" />}
              {fc && (
                <>
                  <div className="rounded-lg border border-[#eed9b4] bg-gradient-to-r from-[#fdf3dc] to-[#fbead0] px-3 py-2.5">
                    <p className="flex items-center gap-2 text-xs font-semibold text-[#5c4327]">
                      {fc.signal.score >= 15 ? <TrendingUp className="h-4 w-4 text-[#3f8a6e]" />
                        : fc.signal.score <= -15 ? <TrendingDown className="h-4 w-4 text-[#c9553f]" />
                        : <MoveRight className="h-4 w-4 text-[#c98a2e]" />}
                      Behaviour forecast — {symbol}
                    </p>
                    <p className="mt-1 text-[11px] leading-relaxed text-[#7c5a2e]">{fc.signal.headline}</p>
                    <div className="mt-2">
                      <SignalGauge score={fc.signal.score} label={fc.signal.label} />
                    </div>
                  </div>

                  {/* pillar grid */}
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {fc.signal.pillars.map((p) => (
                      <div key={p.name} className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6] px-2 py-1.5">
                        <p className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-[#97795a]">
                          {stanceIcon(p.stance)}{p.name}
                        </p>
                        <p className="mt-0.5 text-[11px] leading-snug text-[#5c4327]">{p.reading}</p>
                      </div>
                    ))}
                  </div>

                  {/* horizons */}
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {fc.horizons.map((h) => (
                      <div key={h.horizon} className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6] p-2.5">
                        <p className="flex items-center justify-between text-xs font-semibold text-[#5c4327]">
                          {h.horizon}
                          <span className={`rounded px-1.5 py-0.5 text-[9px] uppercase ${
                            h.bias === 'up' ? 'bg-[#e8f2e8] text-[#3f8a6e]'
                            : h.bias === 'down' ? 'bg-[#f9e8e4] text-[#c9553f]'
                            : 'bg-[#f7ecd4] text-[#8a6a3a]'}`}>
                            {h.bias === 'n/a' ? 'insufficient history' : `${h.bias} bias`}
                          </span>
                        </p>
                        {h.range_high > 0 && (
                          <p className="mt-1 font-mono text-sm text-[#4a3525]">
                            {h.range_low.toLocaleString()} – {h.range_high.toLocaleString()}
                          </p>
                        )}
                        <p className="mt-1 text-[11px] leading-relaxed text-[#7c5a2e]">{h.note}</p>
                      </div>
                    ))}
                  </div>

                  {/* fan chart */}
                  {fc.mc && (
                    <div>
                      <ChartTitle>
                        Monte-Carlo fan — next {fc.mc.days} trading days, {fc.mc.paths} bootstrap paths (median line,
                        inner 25–75%, outer 5–95% band)
                      </ChartTitle>
                      <FanChart pack={fc.mc} />
                      <Interpretation text={`${fc.mc.method}. Actionable: use the outer band as the honest planning range — anything between ${fc.mc.range_low_1m.toLocaleString()} and ${fc.mc.range_high_1m.toLocaleString()} in a month is normal market behaviour for this asset.`} />
                    </div>
                  )}

                  {/* analog evidence */}
                  {fc.analogs && (
                    <div className="rounded-lg border border-[#e8ddb8] bg-[#fdf8ec] p-3">
                      <p className="text-xs font-semibold text-[#5c4327]">History&rsquo;s verdict — setup analogs</p>
                      <p className="mt-1 text-[11px] leading-relaxed text-[#7c5a2e]">
                        Today&rsquo;s fingerprint: <span className="font-medium">{fc.analogs.description}</span>
                        {' '}— seen {fc.analogs.count}× before.
                      </p>
                      <div className="mt-2 grid grid-cols-3 gap-2 text-[11px]">
                        {(['5d', '10d', '21d'] as const).map((h) => {
                          const e = fc.analogs?.[h];
                          if (!e) return null;
                          return (
                            <div key={h} className="rounded border border-[#f0e4cc] bg-[#fffdf6] px-2 py-1.5 text-center">
                              <p className="text-[9px] uppercase text-[#b39a76]">next {h.replace('d', ' days')}</p>
                              <p className={`font-mono text-sm font-semibold ${e.mean_pct >= 0 ? 'text-[#3f8a6e]' : 'text-[#c9553f]'}`}>
                                {e.mean_pct >= 0 ? '+' : ''}{e.mean_pct}%
                              </p>
                              <p className="text-[10px] text-[#97795a]">{e.hit_rate}% higher · {e.count} obs</p>
                              <p className="text-[9px] text-[#b39a76]">worst {e.worst_pct}% / best +{e.best_pct}%</p>
                            </div>
                          );
                        })}
                      </div>
                      <Interpretation text={fc.analogs.interpretation} />
                    </div>
                  )}

                  {/* key levels */}
                  <div>
                    <ChartTitle>Key levels on the radar</ChartTitle>
                    <div className="grid grid-cols-5 gap-2 text-[11px]">
                      {fc.levels.map((l) => (
                        <div key={l.level} className="rounded bg-[#fdf8ec] px-2 py-1.5 text-center">
                          <p className="text-[9px] uppercase text-[#b39a76]">{l.level}</p>
                          <p className="font-mono font-semibold text-[#4a3525]">{l.value.toLocaleString()}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* bull / bear / invalidation */}
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <div className="rounded-lg border border-[#cfe0cf] bg-[#eff5ee] p-3">
                      <p className="text-xs font-semibold text-[#3f6e4a]">Bull case</p>
                      <p className="mt-1 text-[11px] leading-relaxed text-[#3d5c44]">{fc.bull_case}</p>
                    </div>
                    <div className="rounded-lg border border-[#e8ccc5] bg-[#f9efec] p-3">
                      <p className="text-xs font-semibold text-[#a14d3c]">Bear case</p>
                      <p className="mt-1 text-[11px] leading-relaxed text-[#6e3a30]">{fc.bear_case}</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2 rounded-lg border border-[#eed9b4] bg-[#fdf3dc] px-3 py-2">
                    <ShieldAlert className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#c98a2e]" />
                    <p className="text-[11px] leading-relaxed text-[#8a6a3a]">{fc.invalidation}</p>
                  </div>

                  <Interpretation text={fc.forecast_interpretation} />
                </>
              )}
              {!fc && pack && state?.packError && (
                <p className="text-xs text-[#a14d3c]">Forecast unavailable — {state.packError}</p>
              )}
            </TabsContent>

            {/* ── Monthly heatmap tab ── */}
            <TabsContent value="heatmap" className="mt-0 flex flex-col gap-3">
              {!pack && <Skeleton className="h-40 w-full bg-[#efdfbc]" />}
              {pack && (
                <>
                  <MonthlyHeatmap pack={pack} />
                  <Interpretation text={pack.heatmap.interpretation} />
                  <p className="text-[10px] text-[#b39a76]">
                    Cells show % return per calendar month. Green = positive month, red = negative.
                  </p>
                </>
              )}
            </TabsContent>
          </Tabs>
        )}
      </CardContent>
    </Card>
  );
}
