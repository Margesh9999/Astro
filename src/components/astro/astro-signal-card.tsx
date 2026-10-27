'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { quantApi, enhanceApi } from '@/lib/astro/api';
import type { AstroSignalResponse, SuriCycles } from '@/lib/astro/types';
import { MoonStar, Sparkles, TrendingUp, CalendarClock, Compass, Lightbulb } from 'lucide-react';

function MoodGauge({ value, label }: { value: number; label: string }) {
  // semicircle gauge 0..100
  const R = 58;
  const cx = 80;
  const cy = 76;
  const angle = Math.PI * (1 - value / 100); // 0 -> right, 100 -> left... mirrored below
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
      <p className="text-xs text-[#97795a]">{label}</p>
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
        <div className="absolute left-1/2 top-0 h-full w-px bg-[#b39a76]/60" />
        <div
          className="absolute top-0 h-full w-1.5 rounded bg-[#4a3525]"
          style={{ left: `calc(${pct}% - 3px)` }}
        />
      </div>
    </div>
  );
}

const KIND_STYLE: Record<string, string> = {
  volatility_window: 'bg-[#fdeaea] text-[#a14d3c] border-[#eecfc7]',
  reversal_window: 'bg-[#fdf3dc] text-[#8a6a3a] border-[#eed9b4]',
};

export function AstroSignalCard({ symbol, spot }: { symbol: string; spot?: number }) {
  const [state, setState] = useState<{ data?: AstroSignalResponse; error?: string } | null>(null);
  const [cycles, setCycles] = useState<SuriCycles | null>(null);

  useEffect(() => {
    let alive = true;
    quantApi
      .astroSignal(symbol)
      .then((d) => alive && setState({ data: d }))
      .catch((e) => alive && setState((prev) => (prev?.data?.symbol === symbol ? prev : { error: String(e?.message ?? e) })));
    // T2: detailed & actionable cycles
    enhanceApi
      .suriCycles(symbol)
      .then((d) => alive && setCycles(d))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [symbol]);

  const stale = !!state?.data && state.data.symbol !== symbol;
  const cyclesStale = !!cycles && cycles.symbol !== symbol;
  const loading = !state || stale;
  const error = state?.error ?? null;
  const data = stale ? null : (state?.data ?? null);
  const cyclesData = cyclesStale ? null : cycles;

  return (
    <Card className="vedic-card flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MoonStar className="h-4 w-4 text-[#c98a2e]" />
            <CardTitle className="font-display text-base tracking-wide">Suri Cycles</CardTitle>
          </div>
          <span className="rounded bg-[#f7ecd4] px-2 py-0.5 font-mono text-[10px] text-[#97795a]">
            {symbol}
          </span>
        </div>
        <CardDescription className="text-[#97795a]">
          Planetary timing · lunar journey · weekly playbook (inspired by Mohnish Suri)
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        {loading && !data ? (
          <div className="space-y-3">
            <Skeleton className="mx-auto h-24 w-40 bg-[#efdfbc]" />
            <Skeleton className="h-3 w-full bg-[#efdfbc]" />
            <Skeleton className="h-16 w-full bg-[#efdfbc]" />
          </div>
        ) : error || !data ? (
          <div className="flex flex-1 items-center justify-center py-8 text-sm text-[#97795a]">
            Astro-signal unavailable — {error ?? 'try refreshing'}
          </div>
        ) : (
          <Tabs defaultValue="now" className="mt-0 flex flex-1 flex-col">
            <TabsList className="mb-3 bg-[#f4e8cf]">
              <TabsTrigger value="now" className="text-xs data-[state=active]:bg-[#fffdf6]">Now</TabsTrigger>
              <TabsTrigger value="plan" className="text-xs data-[state=active]:bg-[#fffdf6]">This Week</TabsTrigger>
              <TabsTrigger value="moon" className="text-xs data-[state=active]:bg-[#fffdf6]">Lunar 30d</TabsTrigger>
            </TabsList>

            {/* ── NOW tab (mood, composite, range, alerts) ── */}
            <TabsContent value="now" className="mt-0 flex flex-1 flex-col gap-4">
              <div className="flex items-center justify-between gap-2">
                <MoodGauge value={data.mood.mood_index} label={data.mood.mood_label} />
                <div className="flex-1 space-y-1 text-xs">
                  <div className="flex justify-between">
                    <span className="text-[#97795a]">Lunar</span>
                    <span className="font-medium text-[#5c4327]">{data.mood.lunar}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#97795a]">Retrogrades</span>
                    <span className="font-mono text-[#5c4327]">{data.mood.retrogrades}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#97795a]">Reversal score</span>
                    <span className="font-mono text-[#5c4327]">{data.reversal.reversal_score}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#97795a]">Vol window</span>
                    <span className="font-mono text-[#5c4327]">{data.volatility.volatility_score}</span>
                  </div>
                </div>
              </div>

              {data.composite && (
                <div>
                  <p className="mb-1.5 flex items-center gap-1.5 text-xs text-[#97795a]">
                    <Sparkles className="h-3.5 w-3.5 text-[#c98a2e]" /> Astro-Technical Composite
                  </p>
                  <SignalBar composite={data.composite.composite} zone={data.composite.zone} />
                  <div className="mt-1.5 grid grid-cols-3 gap-2 text-[11px]">
                    <div className="rounded bg-[#fdf8ec] px-2 py-1">
                      <span className="text-[#97795a]">RSI14 </span>
                      <span className="font-mono text-[#5c4327]">{data.composite.rsi14}</span>
                    </div>
                    <div className="rounded bg-[#fdf8ec] px-2 py-1">
                      <span className="text-[#97795a]">Trend </span>
                      <span className="font-mono text-[#5c4327]">{data.composite.trend_pct}%</span>
                    </div>
                    <div className="rounded bg-[#fdf8ec] px-2 py-1">
                      <span className="text-[#97795a]">Vol </span>
                      <span className="font-mono text-[#5c4327]">
                        {(data.composite.vol20_annualised * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {data.five_day_range?.bands && (
                <div>
                  <p className="mb-1.5 flex items-center gap-1.5 text-xs text-[#97795a]">
                    <TrendingUp className="h-3.5 w-3.5 text-[#c98a2e]" />
                    5-Day Range · σ {data.five_day_range.horizon_sigma.toFixed(4)} × astro{' '}
                    {data.five_day_range.astro_multiplier}
                  </p>
                  <div className="space-y-1 rounded-lg border border-[#f0e4cc] bg-[#fffdf6] p-2 text-[11px]">
                    <div className="flex justify-between font-mono text-[#3f8a6e]">
                      <span>R</span>
                      <span>{data.five_day_range.bands.outer.high.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between font-mono text-[#c98a2e]">
                      <span>inner R</span>
                      <span>{data.five_day_range.bands.inner.high.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between border-y border-[#f0e4cc] font-mono font-semibold text-[#4a3525]">
                      <span>spot</span>
                      <span>{(spot ?? data.five_day_range.spot).toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between font-mono text-[#c98a2e]">
                      <span>inner S</span>
                      <span>{data.five_day_range.bands.inner.low.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between font-mono text-[#c9553f]">
                      <span>S</span>
                      <span>{data.five_day_range.bands.outer.low.toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              )}

              <div className="flex-1">
                <p className="mb-1.5 flex items-center gap-1.5 text-xs text-[#97795a]">
                  <CalendarClock className="h-3.5 w-3.5 text-[#c98a2e]" /> Timing alerts · next 14 days
                </p>
                <div className="warm-scroll max-h-44 space-y-1.5 overflow-y-auto pr-1">
                  {data.timing_alerts.length === 0 && (
                    <p className="rounded bg-[#fdf8ec] px-2 py-2 text-[11px] text-[#97795a]">
                      Quiet window — no classical reversal/volatility triggers in range.
                    </p>
                  )}
                  {data.timing_alerts.slice(0, 10).map((a, i) => (
                    <div
                      key={i}
                      className={`rounded border px-2 py-1.5 text-[11px] ${
                        KIND_STYLE[a.kind] ?? 'bg-[#fdf8ec] text-[#8a6a3a] border-[#eed9b4]'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{a.title}</span>
                        <span className="font-mono opacity-70">{a.date.slice(5)}</span>
                      </div>
                      {a.note && <p className="mt-0.5 opacity-80">{a.note}</p>}
                    </div>
                  ))}
                </div>
              </div>
            </TabsContent>

            {/* ── T2: THIS WEEK playbook + ingresses/stations ── */}
            <TabsContent value="plan" className="mt-0 flex flex-1 flex-col gap-3">
              {!cyclesData && <Skeleton className="h-24 w-full bg-[#efdfbc]" />}
              {cyclesData && (
                <>
                  <div className="rounded-lg border border-[#e8ddb8] bg-gradient-to-r from-[#fdf3dc] to-[#fbead0] p-3">
                    <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-[#8a6a3a]">
                      <Compass className="h-3.5 w-3.5" /> How to trade this week
                    </p>
                    <p className="text-[11px] leading-relaxed text-[#7c5a2e]">{cycles.playbook}</p>
                  </div>
                  <div>
                    <p className="mb-1 text-xs font-medium text-[#5c4327]">Sign ingresses · next 60 days</p>
                    <div className="warm-scroll max-h-32 space-y-1 overflow-y-auto pr-1">
                      {cycles.ingresses.length === 0 && (
                        <p className="rounded bg-[#fdf8ec] px-2 py-1.5 text-[11px] text-[#97795a]">
                          No sign changes in the window.
                        </p>
                      )}
                      {cycles.ingresses.map((ing, i) => (
                        <div key={i} className="flex items-center justify-between rounded border border-[#efe7f8] bg-[#f8f4fc] px-2 py-1 text-[11px]">
                          <span className="font-medium text-[#6b4e93]">{ing.planet} → {ing.into}</span>
                          <span className="font-mono text-[#97795a]">{ing.date.slice(5)}</span>
                        </div>
                      ))}
                    </div>
                    <p className="mt-1 text-[10px] text-[#b39a76]">
                      Ingress = a planet changes sign — market leadership rotates toward themes of the new sign.
                    </p>
                  </div>
                  <div>
                    <p className="mb-1 text-xs font-medium text-[#5c4327]">Retrograde stations · next 45 days</p>
                    {cycles.stations.length === 0 ? (
                      <p className="rounded bg-[#fdf8ec] px-2 py-1.5 text-[11px] text-[#97795a]">
                        None — no planet stations this month.
                      </p>
                    ) : (
                      <div className="space-y-1">
                        {cycles.stations.map((st, i) => (
                          <div key={i} className="rounded border border-[#eecfc7] bg-[#fbeae4] px-2 py-1.5 text-[11px]">
                            <div className="flex items-center justify-between">
                              <span className="font-medium text-[#a14d3c]">{st.planet} {st.event}</span>
                              <span className="font-mono text-[#97795a]">{st.date.slice(5)}</span>
                            </div>
                            <p className="mt-0.5 text-[#7c5a2e]">{st.meaning}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </TabsContent>

            {/* ── T2: 30-day lunar journey ── */}
            <TabsContent value="moon" className="mt-0 flex flex-1 flex-col gap-2">
              {!cyclesData && <Skeleton className="h-40 w-full bg-[#efdfbc]" />}
              {cyclesData && (
                <>
                  <p className="text-[11px] text-[#97795a]">
                    The Moon travels the whole zodiac in ~27 days — each phase biases the crowd mood.
                    Plan entries in the waxing half, profit-taking in the waning half.
                  </p>
                  <div className="warm-scroll max-h-[300px] space-y-1 overflow-y-auto pr-1">
                    {cycles.lunar_journey.map((m, i) => (
                      <div key={i} className="flex items-center gap-2 rounded border border-[#f0e4cc] bg-[#fffdf6] px-2 py-1 text-[11px]">
                        <span className="w-12 flex-shrink-0 font-mono text-[#97795a]">{m.date.slice(5)}</span>
                        <span className="w-28 flex-shrink-0 font-medium text-[#5c4327]">{m.phase}</span>
                        <span className="text-[#7c5a2e]">{m.note}</span>
                      </div>
                    ))}
                  </div>
                  <div className="flex items-start gap-1.5 rounded-lg border border-[#e8ddb8] bg-[#fdf8ec] px-2.5 py-2">
                    <Lightbulb className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-[#c98a2e]" />
                    <p className="text-[11px] leading-relaxed text-[#7c5a2e]">
                      Rule of thumb: accumulate from New Moon to Full Moon (waxing = rising optimism),
                      harvest from Full Moon to New Moon (waning = fading mood). Stack this with the
                      composite above — both agreeing is your strongest signal.
                    </p>
                  </div>
                </>
              )}
            </TabsContent>
          </Tabs>
        )}

        <p className="text-[10px] leading-snug text-[#b39a76]">
          Educational reimplementation of Mohnish Suri&apos;s concepts — no proven predictive value.
        </p>
      </CardContent>
    </Card>
  );
}
