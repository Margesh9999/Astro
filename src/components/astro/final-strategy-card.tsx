'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { AlertTriangle, CalendarDays, Compass, Gauge, ListChecks, Orbit, RefreshCw, Target, Wallet } from 'lucide-react';
import { strategyApi, type FinalStrategy } from '@/lib/astro/api-strategy';
import { RATING_STYLE } from './agents-card';
import { HorizonPlans, IncomePlan, NatalToday, Note, Scoreboard, SectionTitle, WeeklyRoutine } from './strategy-sections';

const DEFAULTS = { name: 'Margesh', date: '1994-04-23', time: '06:45', place: 'Vallabh Vidyanagar, Gujarat, India' };

const STANCE_TONE: Record<string, string> = {
  bullish: 'from-[#e2f3e9] to-[#fffdf6] border-[#a8d8bf]',
  bearish: 'from-[#fbe7e0] to-[#fffdf6] border-[#e8b3a8]',
  neutral: 'from-[#fdf3dc] to-[#fffdf6] border-[#d9b46a]',
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex min-w-0 flex-col gap-0.5 text-[10px] uppercase tracking-wide text-[#97795a]">
      {label}
      {children}
    </label>
  );
}

/**
 * FinalStrategyCard — the last section: every signal → one 30/60/90/365-day plan.
 * Props: symbol (selected ticker), symbolName (optional display name).
 */
export function FinalStrategyCard({ symbol, symbolName }: { symbol: string; symbolName?: string }) {
  const [form, setForm] = useState({ ...DEFAULTS, capital: 50000, target: 500 });
  const [applied, setApplied] = useState(form);
  const [state, setState] = useState<{ key: string; data?: FinalStrategy; error?: string } | null>(null);
  const reqKey = `${symbol}|${JSON.stringify(applied)}`;
  useEffect(() => {
    let alive = true;
    strategyApi
      .finalStrategy({
        symbol,
        name: applied.name,
        date: applied.date,
        time: applied.time,
        place: applied.place,
        capital: applied.capital,
        target_weekly: applied.target,
      })
      .then((d) => alive && setState({ key: reqKey, data: d }))
      .catch((e) => alive && setState({ key: reqKey, error: String(e?.message ?? e) }));
    return () => {
      alive = false;
    };
  }, [symbol, applied, reqKey]);

  const loading = !state || state.key !== reqKey;
  const data = !loading ? state?.data : undefined;
  const error = !loading ? state?.error : undefined;
  const ov = data?.overall;

  return (
    <Card className="vedic-card">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Compass className="h-4 w-4 text-[#c98a2e]" />
            <CardTitle className="font-display text-base tracking-wide">
              Final Strategy — {data?.symbol_name ?? symbolName ?? symbol}
            </CardTitle>
          </div>
          {ov && (
            <span className="rounded border border-[#d9b46a] bg-[#fdf3dc] px-2 py-0.5 text-[11px] font-bold text-[#8a6a3a]">
              <Gauge className="mr-1 inline h-3 w-3" />
              {ov.stance} · {ov.score > 0 ? '+' : ''}
              {ov.score}
            </span>
          )}
        </div>
        <CardDescription className="text-[#97795a]">
          Every signal in AstroTrader — quant, technicals, ML, Suri timing, sky events, the agents&apos; decision, your kundli, dasha and
          today&apos;s transits — combined into one 30 / 60 / 90-day and 1-year plan with an income target.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {/* inputs */}
        <form
          className="grid grid-cols-2 gap-2 rounded-lg border border-[#f0e4cc] bg-[#fffaf0] p-3 md:grid-cols-7"
          onSubmit={(e) => {
            e.preventDefault();
            setApplied(form);
          }}
        >
          <Field label="Name">
            <Input className="h-8 bg-[#fffdf6] text-xs" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <Field label="Birth date">
            <Input type="date" className="h-8 bg-[#fffdf6] text-xs" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
          </Field>
          <Field label="Time">
            <Input type="time" className="h-8 bg-[#fffdf6] text-xs" value={form.time} onChange={(e) => setForm({ ...form, time: e.target.value })} />
          </Field>
          <div className="col-span-2">
            <Field label="Place">
              <Input className="h-8 bg-[#fffdf6] text-xs" value={form.place} onChange={(e) => setForm({ ...form, place: e.target.value })} />
            </Field>
          </div>
          <Field label="Capital £">
            <Input
              type="number"
              min={1000}
              step={1000}
              className="h-8 bg-[#fffdf6] text-xs"
              value={form.capital}
              onChange={(e) => setForm({ ...form, capital: Number(e.target.value) || 0 })}
            />
          </Field>
          <Field label="Target £/week">
            <Input
              type="number"
              min={10}
              step={50}
              className="h-8 bg-[#fffdf6] text-xs"
              value={form.target}
              onChange={(e) => setForm({ ...form, target: Number(e.target.value) || 0 })}
            />
          </Field>
          <div className="col-span-2 flex items-center justify-between gap-2 md:col-span-7">
            <p className="text-[10px] text-[#b39a76]">
              {data?.birth?.name ? `Chart: ${data.birth.name} · ${data.birth.date} ${data.birth.time} · ${data.birth.place}` : 'Defaults to the app’s native (Margesh).'}
            </p>
            <Button type="submit" size="sm" className="h-7 bg-[#c98a2e] text-xs text-white hover:bg-[#b07a26]">
              <RefreshCw className="mr-1 h-3 w-3" /> Recalculate
            </Button>
          </div>
        </form>

        {loading && (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full bg-[#efdfbc]" />
            ))}
          </div>
        )}
        {error && (
          <div className="rounded-md border border-[#eecfc7] bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">Final strategy unavailable — {error}</div>
        )}

        {data && ov && (
          <>
            {/* bottom line hero */}
            <div className={`rounded-xl border bg-gradient-to-r p-4 ${STANCE_TONE[ov.signal] ?? STANCE_TONE.neutral}`}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-display text-lg font-bold text-[#5c4327]">{ov.stance}</span>
                <span className="text-xs text-[#97795a]">overall {ov.score > 0 ? '+' : ''}{ov.score}/100 from {ov.available} live signals</span>
                {data.agents_decision && (
                  <span className={`rounded border px-1.5 text-[10px] font-semibold ${RATING_STYLE[data.agents_decision.rating]}`}>
                    Agents: {data.agents_decision.rating} {data.agents_decision.confidence}%
                  </span>
                )}
                {data.dasha?.md && (
                  <span className="rounded border border-[#e3cde0] bg-[#f6ecf4] px-1.5 text-[10px] text-[#8a4f78]">
                    Dasha {data.dasha.md}/{data.dasha.ad}/{data.dasha.pd ?? '-'}
                  </span>
                )}
              </div>
              <p className="mt-2 text-[10px] font-semibold uppercase tracking-wide text-[#8a6a3a]">Bottom line</p>
              <p className="mt-0.5 text-xs leading-relaxed text-[#5c4327]">{data.bottom_line}</p>
            </div>

            <section>
              <SectionTitle icon={Gauge}>Signal scoreboard</SectionTitle>
              <Scoreboard rows={data.scoreboard} overall={ov} />
            </section>

            <section>
              <SectionTitle icon={Orbit}>Your kundli vs today&apos;s planets</SectionTitle>
              {data.natal_vs_today ? (
                <NatalToday nvt={data.natal_vs_today} />
              ) : (
                <Note>Natal/transit comparison is unavailable right now ({data.inputs_status.jataka ?? data.inputs_status.transits}).</Note>
              )}
            </section>

            <section>
              <SectionTitle icon={Target}>30 / 60 / 90-day &amp; 1-year plan</SectionTitle>
              <HorizonPlans plans={data.plans} />
            </section>

            <section>
              <SectionTitle icon={Wallet}>Income plan — {`£${data.income.target_weekly.toLocaleString('en-GB')}`}/week target</SectionTitle>
              <IncomePlan income={data.income} />
            </section>

            <section>
              <SectionTitle icon={ListChecks}>Weekly routine</SectionTitle>
              <WeeklyRoutine items={data.weekly_routine} />
            </section>

            <section>
              <SectionTitle icon={CalendarDays}>All key dates (next 12 months)</SectionTitle>
              <div className="max-h-56 overflow-y-auto rounded-lg border border-[#f0e4cc] bg-[#fffdf6]/80">
                <ul className="divide-y divide-[#f3e8d2]">
                  {data.key_dates.map((d) => (
                    <li key={d.date + d.title} className="flex gap-2 px-3 py-1 text-[10.5px] text-[#7c5a2e]">
                      <span className="w-[74px] shrink-0 font-semibold tabular-nums">{d.date}</span>
                      <span className="min-w-0 break-words">
                        {d.title} <span className="text-[#b39a76]">· {d.kind}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </section>

            <div className="flex gap-2 rounded-lg border border-[#eecfc7] bg-[#fbeae4] px-3 py-2 text-[11px] leading-relaxed text-[#a14d3c]">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{data.risk_warning}</span>
            </div>
            <p className="text-[10px] text-[#b39a76]">
              As of {data.as_of} · inputs:{' '}
              {Object.entries(data.inputs_status)
                .map(([k, v]) => `${k} ${v}`)
                .join(' · ')}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
