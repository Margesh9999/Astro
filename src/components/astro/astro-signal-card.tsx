'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cyclesApi, shortDate } from '@/lib/astro/api-cycles';
import type { CycleStats, CyclesInsight, SuriComposite, SuriRange } from '@/lib/astro/api-cycles';
import { MoonStar, Sparkles, TrendingUp, CalendarClock, Compass, Lightbulb } from 'lucide-react';
import { CyclesReading } from './cycles-reading';
import { CyclesClock } from './cycles-clock';
import { CyclesStatsPanel } from './cycles-stats';
import { ExplainedMetric, VerdictBadge } from './cycles-shared';

function MoodGauge({ value, label }: { value: number; label: string }) {
  // semicircle gauge 0..100
  const R = 58;
  const cx = 80;
  const cy = 76;
  const angle = Math.PI * (1 - value / 100);
  const nx = cx + R * Math.cos(angle);
  const ny = cy - R * Math.sin(angle);
  const arc = (from: number, to: number) => {
    const a1 = Math.PI * (1 - from / 100);
    const a2 = Math.PI * (1 - to / 100);
    const x1 = cx + R * Math.cos(a1);
    const y1 = cy - R * Math.sin(a1);
    const x2 = cx + R * Math.cos(a2);
    const y2 = cy - R * Math.sin(a2);
    return `M ${x1} ${y1} A ${R} ${R} 0 0 1 ${x2} ${y2}`;
  };
  const color = value >= 70 ? '#4a9a7e' : value >= 45 ? '#c98a2e' : '#cf5b54';

  return (
    <div className="flex flex-col items-center">
      <svg width="160" height="92" viewBox="0 0 160 92">
        <path d={arc(0, 30)} stroke="#eecfc7" strokeWidth="10" fill="none" strokeLinecap="round" />
        <path d={arc(30, 70)} stroke="#f3dfae" strokeWidth="10" fill="none" />
        <path d={arc(70, 100)} stroke="#cfe8dd" strokeWidth="10" fill="none" strokeLinecap="round" />
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke={color} strokeWidth="3" strokeLinecap="round" />
        <circle cx={cx} cy={cy} r="5" fill={color} />
        <text x={cx} y={90} textAnchor="middle" className="fill-[#97795a]" fontSize="9">
          0 · Fear — Euphoria · 100
        </text>
      </svg>
      <p className="-mt-1 font-mono text-2xl font-semibold" style={{ color }}>
        {value.toFixed(1)}
      </p>
      <p className="text-xs text-[#97795a]">Sky-mood · {label}</p>
    </div>
  );
}

function SignalBar({ composite, zone }: { composite: number; zone: string }) {
  const pct = ((Math.max(-100, Math.min(100, composite)) + 100) / 200) * 100;
  const pos = composite >= 0;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-[11px] text-[#97795a]">
        <span>−100 Sell</span>
        <span className={`font-semibold ${pos ? 'text-[#3f8a6e]' : 'text-[#c9553f]'}`}>
          {composite.toFixed(1)} · {zone}
        </span>
        <span>Buy +100</span>
      </div>
      <div className="relative h-3 overflow-hidden rounded-full bg-gradient-to-r from-[#f6d7cd] via-[#f3e6c4] to-[#d3e8dd]">
        <div className="absolute left-[42.5%] top-0 h-full w-px bg-[#b39a76]/50" />
        <div className="absolute left-1/2 top-0 h-full w-px bg-[#b39a76]/80" />
        <div className="absolute left-[57.5%] top-0 h-full w-px bg-[#b39a76]/50" />
        <div className="absolute top-0 h-full w-1.5 rounded bg-[#4a3525]" style={{ left: `calc(${pct}% - 3px)` }} />
      </div>
      <p className="mt-0.5 text-center text-[10px] text-[#b39a76]">thin lines at −15 / 0 / +15 mark the Sell · Neutral · Buy zones</p>
    </div>
  );
}

const KIND_STYLE: Record<string, string> = {
  volatility_window: 'bg-[#fdeaea] text-[#a14d3c] border-[#eecfc7]',
  reversal_window: 'bg-[#fdf3dc] text-[#8a6a3a] border-[#eed9b4]',
};
const KIND_PLAIN: Record<string, string> = {
  volatility_window: 'Bigger-swing window — trade smaller, widen stops',
  reversal_window: 'Possible turning point — don’t chase, protect profits',
};

function RangeLadder({ rng, spot, explain }: { rng: SuriRange; spot?: number; explain?: string }) {
  const rows: { tag: string; v: number; cls: string; use: string }[] = [
    { tag: 'R', v: rng.bands.outer.high, cls: 'text-[#3f8a6e]', use: 'stretch target · ~16% chance to close above' },
    { tag: 'inner R', v: rng.bands.inner.high, cls: 'text-[#c98a2e]', use: 'first profit target · ~31% above' },
    { tag: 'spot', v: spot ?? rng.spot, cls: 'font-semibold text-[#4a3525]', use: 'last price' },
    { tag: 'inner S', v: rng.bands.inner.low, cls: 'text-[#c98a2e]', use: 'dip-buy zone · ~31% below' },
    { tag: 'S', v: rng.bands.outer.low, cls: 'text-[#c9553f]', use: 'stop-loss area · ~16% chance to close below' },
  ];
  return (
    <div>
      <p className="mb-1.5 flex items-center gap-1.5 text-xs text-[#97795a]">
        <TrendingUp className="h-3.5 w-3.5 text-[#c98a2e]" />
        5-session range ladder (where price is likely to finish within a week)
      </p>
      <div className="space-y-0.5 rounded-lg border border-[#f0e4cc] bg-[#fffdf6] p-2 text-[11px]">
        {rows.map((r) => (
          <div
            key={r.tag}
            className={`grid grid-cols-[3.5rem_minmax(0,1fr)_auto] items-center gap-2 font-mono ${r.cls} ${
              r.tag === 'spot' ? 'border-y border-[#f0e4cc] py-0.5' : ''
            }`}
          >
            <span>{r.tag}</span>
            <span className="truncate font-sans text-[10.5px] text-[#97795a]">{r.use}</span>
            <span>{r.v.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
          </div>
        ))}
      </div>
      {explain && <p className="mt-1 text-[10.5px] leading-snug text-[#97795a]">{explain}</p>}
    </div>
  );
}

export function AstroSignalCard({ symbol, spot }: { symbol: string; spot?: number }) {
  const [state, setState] = useState<{ data?: CyclesInsight; error?: string } | null>(null);
  const [stats, setStats] = useState<{ data?: CycleStats; error?: string } | null>(null);

  useEffect(() => {
    let alive = true;
    cyclesApi
      .insight(symbol)
      .then((d) => alive && setState({ data: d }))
      .catch((e) => alive && setState((prev) => (prev?.data?.symbol === symbol ? prev : { error: String(e?.message ?? e) })));
    cyclesApi
      .stats(symbol)
      .then((d) => alive && setStats({ data: d }))
      .catch((e) => alive && setStats({ error: String(e?.message ?? e) }));
    return () => {
      alive = false;
    };
  }, [symbol]);

  const stale = !!state?.data && state.data.symbol !== symbol;
  const loading = !state || stale;
  const error = state?.error ?? null;
  const data = stale ? null : (state?.data ?? null);
  const statsData = stats?.data && stats.data.symbol === symbol ? stats.data : null;
  const comp = data?.composite && 'composite' in data.composite ? (data.composite as SuriComposite) : null;
  const rng = data?.five_day_range && 'bands' in data.five_day_range ? (data.five_day_range as SuriRange) : null;
  const ex = data?.explain ?? {};

  return (
    <Card className="vedic-card flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MoonStar className="h-4 w-4 text-[#c98a2e]" />
            <CardTitle className="font-display text-base tracking-wide">Suri Cycles</CardTitle>
          </div>
          <span className="rounded bg-[#f7ecd4] px-2 py-0.5 font-mono text-[10px] text-[#97795a]">{symbol}</span>
        </div>
        <CardDescription className="text-[#97795a]">
          Plain-English cycle reading · cycle clock · {data?.name ?? symbol}&apos;s own cycle history (inspired by Mohnish Suri)
        </CardDescription>
      </CardHeader>
      <CardContent className="flex min-w-0 flex-1 flex-col gap-4">
        {loading && !data ? (
          <div className="space-y-3">
            <Skeleton className="h-36 w-full bg-[#efdfbc]" />
            <Skeleton className="mx-auto h-24 w-40 bg-[#efdfbc]" />
            <Skeleton className="h-16 w-full bg-[#efdfbc]" />
          </div>
        ) : error || !data ? (
          <div className="flex flex-1 items-center justify-center py-8 text-sm text-[#97795a]">
            Cycle reading unavailable — {error ?? 'try refreshing'}
          </div>
        ) : (
          <Tabs defaultValue="now" className="mt-0 flex min-w-0 flex-1 flex-col">
            <TabsList className="mb-3 flex h-auto w-full flex-wrap justify-start gap-0.5 bg-[#f4e8cf]">
              <TabsTrigger value="now" className="flex-none text-xs data-[state=active]:bg-[#fffdf6]">Today</TabsTrigger>
              <TabsTrigger value="clock" className="flex-none text-xs data-[state=active]:bg-[#fffdf6]">Cycle clock</TabsTrigger>
              <TabsTrigger value="history" className="flex-none text-xs data-[state=active]:bg-[#fffdf6]">History</TabsTrigger>
              <TabsTrigger value="plan" className="flex-none text-xs data-[state=active]:bg-[#fffdf6]">This week</TabsTrigger>
              <TabsTrigger value="moon" className="flex-none text-xs data-[state=active]:bg-[#fffdf6]">Lunar 30d</TabsTrigger>
            </TabsList>

            {/* ── TODAY: reading + explained metrics ── */}
            <TabsContent value="now" className="mt-0 flex min-w-0 flex-1 flex-col gap-4">
              <CyclesReading insight={data} />

              <div className="grid grid-cols-1 items-start gap-3 md:grid-cols-[auto_minmax(0,1fr)]">
                <MoodGauge value={data.mood.mood_index} label={data.mood.mood_label} />
                <div className="min-w-0 space-y-1.5">
                  <p className="text-[10px] text-[#b39a76]">Tap any metric to see what it means today.</p>
                  <ExplainedMetric label="Sky-mood index" explain={ex.mood}>
                    {data.mood.mood_index.toFixed(0)}/100 · {data.mood.mood_label}
                  </ExplainedMetric>
                  <ExplainedMetric label="Reversal score" explain={ex.reversal}>
                    {data.reversal.reversal_score.toFixed(0)}/100
                  </ExplainedMetric>
                  <ExplainedMetric label="Volatility window" explain={ex.volatility}>
                    {data.volatility.volatility_score.toFixed(0)}/100
                  </ExplainedMetric>
                  <ExplainedMetric
                    label="Planets retrograde"
                    explain={data.clock.items.filter((i) => i.retro).map((i) => i.meaning).join(' ') || 'No planet is retrograde.'}
                  >
                    {data.mood.retrogrades} of 5
                  </ExplainedMetric>
                </div>
              </div>

              {comp && (
                <div className="space-y-1.5">
                  <p className="flex items-center gap-1.5 text-xs text-[#97795a]">
                    <Sparkles className="h-3.5 w-3.5 text-[#c98a2e]" /> Astro-technical composite (55% price + 45% sky)
                  </p>
                  <SignalBar composite={comp.composite} zone={comp.zone} />
                  <ExplainedMetric label="What the composite means" explain={ex.composite} defaultOpen>
                    {comp.composite.toFixed(0)}
                  </ExplainedMetric>
                  <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-3">
                    <ExplainedMetric label="RSI14" explain={ex.rsi}>{comp.rsi14.toFixed(0)}</ExplainedMetric>
                    <ExplainedMetric label="Trend" explain={ex.trend}>{comp.trend_pct.toFixed(2)}%</ExplainedMetric>
                    <ExplainedMetric label="Volatility" explain={ex.vol}>
                      {(comp.vol20_annualised * 100).toFixed(1)}%
                    </ExplainedMetric>
                  </div>
                </div>
              )}

              {rng && <RangeLadder rng={rng} spot={spot} explain={ex.range} />}

              <div className="flex-1">
                <p className="mb-1.5 flex items-center gap-1.5 text-xs text-[#97795a]">
                  <CalendarClock className="h-3.5 w-3.5 text-[#c98a2e]" /> Timing alerts · next 14 days
                </p>
                <div className="warm-scroll max-h-52 space-y-1.5 overflow-y-auto pr-1">
                  {data.timing_alerts.length === 0 && (
                    <p className="rounded bg-[#fdf8ec] px-2 py-2 text-[11px] text-[#97795a]">
                      Quiet window — no classical reversal/volatility triggers in the next 14 days; normal position sizes are fine.
                    </p>
                  )}
                  {data.timing_alerts.slice(0, 10).map((a, i) => (
                    <div
                      key={i}
                      className={`rounded border px-2 py-1.5 text-[11px] ${KIND_STYLE[a.kind] ?? 'border-[#eed9b4] bg-[#fdf8ec] text-[#8a6a3a]'}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{a.title}</span>
                        <span className="whitespace-nowrap font-mono opacity-70">
                          {shortDate(a.date)} · {'●'.repeat(Math.max(1, Math.min(5, a.strength ?? 1)))}
                        </span>
                      </div>
                      <p className="mt-0.5 opacity-80">{KIND_PLAIN[a.kind] ?? a.note}</p>
                    </div>
                  ))}
                </div>
                <p className="mt-1 text-[10px] text-[#b39a76]">● = classical strength 1–5. See “Sky Events × Your Stock” for how {data.name} actually behaved around each.</p>
              </div>
            </TabsContent>

            {/* ── CYCLE CLOCK ── */}
            <TabsContent value="clock" className="mt-0">
              <CyclesClock clock={data.clock} />
            </TabsContent>

            {/* ── HISTORY: full-history cycle stats ── */}
            <TabsContent value="history" className="mt-0 min-w-0">
              {statsData ? (
                <CyclesStatsPanel stats={statsData} />
              ) : stats?.error ? (
                <p className="py-6 text-center text-xs text-[#97795a]">Cycle history unavailable — {stats.error}</p>
              ) : (
                <Skeleton className="h-64 w-full bg-[#efdfbc]" />
              )}
            </TabsContent>

            {/* ── THIS WEEK ── */}
            <TabsContent value="plan" className="mt-0 flex flex-col gap-3">
              <div className="rounded-lg border border-[#e8ddb8] bg-gradient-to-r from-[#fdf3dc] to-[#fbead0] p-3">
                <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-[#8a6a3a]">
                  <Compass className="h-3.5 w-3.5" /> How to trade {data.name} this week
                </p>
                <p className="text-[12px] leading-relaxed text-[#7c5a2e]">{data.week.playbook}</p>
              </div>
              <div className="space-y-1.5">
                {data.week.days.map((d) => (
                  <div
                    key={d.date}
                    className={`rounded-md border px-2.5 py-1.5 text-[11px] ${
                      d.closed ? 'border-[#efe7dc] bg-[#f9f6f0] opacity-75' : 'border-[#f0e4cc] bg-[#fffdf6]'
                    }`}
                  >
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                      <span className="w-14 font-mono font-semibold text-[#5c4327]">
                        {d.weekday} {shortDate(d.date).split(' ')[0]}
                      </span>
                      <span className="text-[#97795a]">
                        {d.phase} · {d.tithi} · Moon in {d.nakshatra}
                      </span>
                      <VerdictBadge verdict={d.verdict} />
                    </div>
                    {d.events.length > 0 && <p className="mt-0.5 text-[#6b4e93]">✦ {d.events.join(' · ')}</p>}
                    {d.carried && d.carried.length > 0 && (
                      <p className="mt-0.5 text-[#6b4e93]">✦ First session after: {d.carried.join(' · ')}</p>
                    )}
                    <p className="mt-0.5 font-medium text-[#4a3525]">→ {d.todo}</p>
                    <p className="text-[10px] text-[#b39a76]">History in this nakshatra: {d.history}</p>
                  </div>
                ))}
              </div>
            </TabsContent>

            {/* ── LUNAR 30d ── */}
            <TabsContent value="moon" className="mt-0 flex flex-col gap-2">
              <div className="flex items-start gap-1.5 rounded-lg border border-[#e8ddb8] bg-[#fdf8ec] px-2.5 py-2">
                <Lightbulb className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-[#c98a2e]" />
                <p className="text-[11px] leading-relaxed text-[#7c5a2e]">{data.lunar.summary}</p>
              </div>
              <div className="warm-scroll max-h-[360px] space-y-1 overflow-y-auto pr-1">
                {data.lunar.days.map((m) => (
                  <div
                    key={m.date}
                    className={`grid grid-cols-[3.2rem_minmax(0,1fr)] gap-x-2 rounded border px-2 py-1 text-[11px] sm:grid-cols-[3.2rem_9rem_minmax(0,1fr)] ${
                      m.tilt > 0
                        ? 'border-[#a8d8bf] bg-[#eef8f2]'
                        : m.tilt < 0
                          ? 'border-[#eecfc7] bg-[#fbefea]'
                          : 'border-[#f0e4cc] bg-[#fffdf6]'
                    } ${m.closed ? 'opacity-60' : ''}`}
                  >
                    <span className="font-mono text-[#97795a]">
                      {m.weekday} {shortDate(m.date).split(' ')[0]}
                    </span>
                    <span className="font-medium text-[#5c4327]">
                      {m.phase}
                      <span className="block text-[10px] font-normal text-[#97795a]">{m.tithi}</span>
                    </span>
                    <span className="col-span-2 text-[#7c5a2e] sm:col-span-1">{m.note}</span>
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-[#b39a76]">
                Green/red rows = nakshatras where {data.name} historically had more/fewer up days (weak or significant only).
                Faded rows = market closed.
              </p>
            </TabsContent>
          </Tabs>
        )}

        <p className="text-[10px] leading-snug text-[#b39a76]">
          Educational reimplementation of Mohnish Suri&apos;s concepts — no proven predictive value. Not financial advice.
          {data ? ` Data: ${data.data_source}.` : ''}
        </p>
      </CardContent>
    </Card>
  );
}
