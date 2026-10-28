'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { cyclesApi, shortDate } from '@/lib/astro/api-cycles';
import type { EventsStudy, StudiedEvent } from '@/lib/astro/api-cycles';
import { CalendarDays, ChevronDown, Lightbulb, ScrollText, Target } from 'lucide-react';
import { CyclesEventsTimeline } from './cycles-events-timeline';
import { VerdictBadge } from './cycles-shared';

const FAMILY_STYLE: Record<string, { badge: string; label: string }> = {
  lunation: { badge: 'border-[#d9c9b2] bg-[#f4ecdd] text-[#7a6248]', label: 'moon' },
  eclipse: { badge: 'border-[#c9b3d9] bg-[#efe3f6] text-[#5e3f7f]', label: 'eclipse' },
  station: { badge: 'border-[#e8b3a8] bg-[#fbe7e0] text-[#a34332]', label: 'station' },
  ingress: { badge: 'border-[#cbb8dd] bg-[#efe7f8] text-[#6b4e93]', label: 'ingress' },
  aspect: { badge: 'border-[#e3c68f] bg-[#fbeecb] text-[#96660f]', label: 'aspect' },
  combustion: { badge: 'border-[#eec3a3] bg-[#fbeadd] text-[#a35a22]', label: 'combust' },
};
const IMP_FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'hm', label: 'High + Medium' },
  { id: 'high', label: 'High only' },
] as const;
type ImpFilter = (typeof IMP_FILTERS)[number]['id'];

const sgn = (v?: number, d = 2) => (v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(d)}%`);

function StatStrip({ e }: { e: StudiedEvent }) {
  const h = e.study.h ?? {};
  if (!h['20']) return null;
  return (
    <div className="mt-1.5 space-y-1 text-[10.5px]">
      <div className="grid grid-cols-3 gap-1">
        {(['1', '5', '20'] as const).map((k) => (
          <div key={k} className="min-w-0 rounded bg-[#fdf8ec] px-1.5 py-0.5">
            <span className="text-[#97795a]">{k}d avg </span>
            <span className="font-mono text-[#5c4327]">{sgn(h[k]?.mean_pct)}</span>
            <span className="block text-[9.5px] leading-tight text-[#b39a76]">
              normal {sgn(h[k]?.base_pct)} · up {h[k]?.hit_pct?.toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-[#97795a]">
        First-week volatility <span className="font-mono text-[#5c4327]">{e.study.vol_ratio?.toFixed(2)}×</span> normal (
        {e.study.vol_verdict}) · <span className="font-mono text-[#5c4327]">{e.study.n}</span> past cases since{' '}
        {e.study.first?.slice(0, 4)}
      </p>
    </div>
  );
}

function EventRow({ e, id, highlight }: { e: StudiedEvent; id: string; highlight: boolean }) {
  const [open, setOpen] = useState(false);
  const style = FAMILY_STYLE[e.family] ?? FAMILY_STYLE.lunation;
  const d = new Date(e.date + 'T00:00:00');
  return (
    <div
      id={id}
      className={`flex items-start gap-2.5 rounded-md border px-2.5 py-2 transition-colors ${
        highlight ? 'border-[#c98a2e] bg-[#fdf3dc]' : 'border-[#f0e4cc] bg-[#fdf8ec]/80'
      }`}
    >
      <div className="flex h-10 w-10 flex-shrink-0 flex-col items-center justify-center rounded-md border border-[#e8d5ae] bg-gradient-to-b from-[#fffdf6] to-[#f9efd8]">
        <span className="text-[9px] uppercase text-[#b39a76]">{d.toLocaleString('en-US', { month: 'short' })}</span>
        <span className="font-mono text-sm font-semibold text-[#7c5a2e]">{d.getDate()}</span>
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1">
          <p className="mr-0.5 text-xs font-medium text-[#5c4327]">{e.title}</p>
          <span className={`rounded border px-1.5 py-px text-[9px] uppercase ${style.badge}`}>{style.label}</span>
          {e.importance !== 'Low' && (
            <span
              className={`rounded px-1.5 py-px text-[9px] font-medium ${
                e.importance === 'High' ? 'bg-[#f6ddad] text-[#8a5a12]' : 'bg-[#f4ecdd] text-[#97795a]'
              }`}
            >
              {e.importance.toLowerCase()}
            </span>
          )}
          <VerdictBadge verdict={e.study.verdict} />
          {e.touches_stock && (
            <span className="rounded border border-[#cbb8dd] bg-[#efe7f8] px-1.5 py-px text-[9px] font-medium text-[#6b4e93]">
              your sector ({e.touched_by.join(', ')})
            </span>
          )}
        </div>
        <div className="mt-1 flex items-start gap-1.5 rounded border border-[#e8ddb8] bg-[#fffdf6] px-2 py-1.5">
          <Lightbulb className="mt-0.5 h-3 w-3 flex-shrink-0 text-[#c98a2e]" />
          <p className="text-[11px] leading-snug text-[#7c5a2e]">{e.meaning}</p>
        </div>
        <div className="mt-1 flex items-start gap-1.5 rounded border border-[#e3c68f] bg-[#fdf3dc] px-2 py-1.5">
          <Target className="mt-0.5 h-3 w-3 flex-shrink-0 text-[#b0802f]" />
          <p className="text-[11px] font-medium leading-snug text-[#4a3525]">{e.action}</p>
        </div>
        <StatStrip e={e} />
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="mt-1 flex items-center gap-0.5 text-[10.5px] text-[#97795a] hover:text-[#5c4327]"
          aria-expanded={open}
        >
          <ChevronDown className={`h-3 w-3 transition-transform ${open ? 'rotate-180' : ''}`} /> Classical meaning, sectors & past cases
        </button>
        {open && (
          <div className="mt-1 space-y-1 text-[11px] leading-snug text-[#7c5a2e]">
            <p className="flex items-start gap-1.5">
              <ScrollText className="mt-0.5 h-3 w-3 flex-shrink-0 text-[#97795a]" />
              <span>
                <span className="font-semibold">Classical: </span>
                {e.classical}.
              </span>
            </p>
            {e.sector_rulers.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {e.sector_rulers.map((r) => (
                  <span
                    key={r.planet}
                    className={`rounded border px-1.5 py-px text-[10px] ${
                      e.touched_by.includes(r.planet)
                        ? 'border-[#cbb8dd] bg-[#efe7f8] text-[#6b4e93]'
                        : 'border-[#f0e4cc] bg-[#fffdf6] text-[#97795a]'
                    }`}
                  >
                    {r.planet}: {r.sectors.join(', ')}
                  </span>
                ))}
              </div>
            )}
            {e.study.recent && e.study.recent.length > 0 && (
              <p className="text-[10.5px] text-[#97795a]">
                Last cases ({e.study.label}):{' '}
                {e.study.recent.map((r) => `${shortDate(r.date)} ${r.date.slice(0, 4)} → ${sgn(r.r20_pct, 1)} in 20 sessions`).join(' · ')}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function EventsCard({ symbol }: { symbol: string }) {
  const [state, setState] = useState<{ data?: EventsStudy; error?: string } | null>(null);
  const [imp, setImp] = useState<ImpFilter>('hm');
  const [planet, setPlanet] = useState<string>('all');
  const [horizon, setHorizon] = useState<'1' | '5' | '20'>('5');
  const [selected, setSelected] = useState<number | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    cyclesApi
      .eventsStudy(symbol, 45)
      .then((d) => alive && setState({ data: d }))
      .catch((e) => alive && setState((prev) => (prev?.data?.symbol === symbol ? prev : { error: String(e?.message ?? e) })));
    return () => {
      alive = false;
    };
  }, [symbol]);

  const stale = !!state?.data && state.data.symbol !== symbol;
  const loading = !state || stale;
  const error = state?.error ?? null;
  const data = stale ? null : (state?.data ?? null);

  const events = useMemo(() => {
    const all = data?.events ?? [];
    return all.filter(
      (e) =>
        (imp === 'all' || (imp === 'high' ? e.importance === 'High' : e.importance !== 'Low')) &&
        (planet === 'all' || e.planets.includes(planet)),
    );
  }, [data, imp, planet]);

  const select = (i: number) => {
    setSelected(i);
    const el = listRef.current?.querySelector(`#ev-${i}`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  const today = new Date().toISOString().slice(0, 10);

  return (
    <Card className="vedic-card flex h-full min-w-0 flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <CalendarDays className="h-4 w-4 text-[#c98a2e]" />
            <CardTitle className="font-display text-base tracking-wide">Sky Events × Your Stock — 45 Days</CardTitle>
          </div>
          {data && (
            <Badge variant="outline" className="border-[#dcc08a] bg-[#f9efd8] text-[10px] text-[#8a6a3a]">
              {events.length}/{data.count}
            </Badge>
          )}
        </div>
        <CardDescription className="text-[#97795a]">
          {data
            ? `${data.symbol_name} · trend ${data.context.trend} · volatility ${data.context.vol_state} — each event is checked against ${data.history_days.toLocaleString()} sessions of ${data.symbol_name} history`
            : 'Every upcoming event, tested against how this stock behaved the last times it happened'}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex min-w-0 flex-1 flex-col gap-2.5">
        {loading && (
          <div className="space-y-2">
            <Skeleton className="h-28 w-full bg-[#efdfbc]" />
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full bg-[#efdfbc]" />
            ))}
          </div>
        )}
        {error && !data && (
          <div className="rounded-md border border-[#eecfc7] bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">
            Could not load events: {error}
          </div>
        )}
        {data && (
          <>
            <p className="rounded-md border border-[#e8ddb8] bg-[#fdf8ec] px-2.5 py-1.5 text-[11px] leading-snug text-[#7c5a2e]">
              {data.summary}
            </p>
            {data.demo_data && (
              <p className="rounded border border-[#eecfc7] bg-[#fbeae4] px-2 py-1 text-[10.5px] text-[#a14d3c]">
                Demo mode: synthetic prices — event statistics illustrate the method only.
              </p>
            )}
            <p className="text-[10.5px] text-[#97795a]">
              {data.broad_market
                ? `${data.symbol_name} is a broad market — every planet's sectors are inside it, so it reacts mainly through overall sentiment.`
                : data.sector_planets.length
                  ? `${data.symbol_name} (${data.sector}) is classically ruled by ${data.sector_planets.join(' & ')} — events involving them are flagged “your sector”.`
                  : `No classical sector ruler mapped for ${data.sector}.`}
            </p>

            {/* filters */}
            <div className="flex flex-wrap items-center gap-1">
              {IMP_FILTERS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => { setImp(f.id); setSelected(null); }}
                  className={`rounded-full border px-2 py-0.5 text-[10.5px] ${
                    imp === f.id ? 'border-[#c98a2e] bg-[#fbeecb] text-[#7c5a2e]' : 'border-[#efe2c8] bg-[#fffdf6] text-[#97795a]'
                  }`}
                >
                  {f.label}
                </button>
              ))}
              <span className="mx-1 h-3 w-px bg-[#e3cfa4]" />
              {['all', ...data.planets].map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => { setPlanet(p); setSelected(null); }}
                  className={`rounded-full border px-2 py-0.5 text-[10.5px] ${
                    planet === p ? 'border-[#7e6bb0] bg-[#efe7f8] text-[#5e3f7f]' : 'border-[#efe2c8] bg-[#fffdf6] text-[#97795a]'
                  }`}
                >
                  {p === 'all' ? 'All planets' : p}
                </button>
              ))}
            </div>

            {/* timeline */}
            <div className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6] p-2">
              <div className="mb-1 flex items-center justify-between gap-2">
                <p className="text-[11px] font-medium text-[#5c4327]">Timeline · historical move after each event</p>
                <div className="flex gap-0.5">
                  {(['1', '5', '20'] as const).map((h) => (
                    <button
                      key={h}
                      type="button"
                      onClick={() => setHorizon(h)}
                      className={`rounded px-1.5 py-px font-mono text-[10px] ${
                        horizon === h ? 'bg-[#c98a2e] text-white' : 'bg-[#f4e8cf] text-[#8a6a3a]'
                      }`}
                    >
                      {h}d
                    </button>
                  ))}
                </div>
              </div>
              <CyclesEventsTimeline
                events={events}
                days={data.days}
                horizon={horizon}
                start={today}
                onSelect={select}
                selected={selected}
              />
            </div>

            {events.length === 0 ? (
              <p className="py-6 text-center text-xs text-[#97795a]">No events match the filters.</p>
            ) : (
              <div ref={listRef} className="warm-scroll max-h-[560px] space-y-2 overflow-y-auto pr-1">
                {events.map((e, i) => (
                  <EventRow key={`${e.date}-${e.key}`} e={e} id={`ev-${i}`} highlight={selected === i} />
                ))}
              </div>
            )}
            <p className="text-[10px] leading-snug text-[#b39a76]">
              {data.method} {data.disclaimer}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
