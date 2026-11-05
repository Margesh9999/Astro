'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { CalendarDays, Download, Lightbulb, MapPin, Sun, Sunset } from 'lucide-react';
import { PLACES, panchangApi } from '@/lib/astro/api-panchang';
import type { MarketCalendar, Panchang, Place } from '@/lib/astro/api-panchang';
import { VerdictBadge } from './cycles-shared';

const TONE: Record<string, { dot: string; cell: string; label: string }> = {
  favourable: { dot: 'bg-[#6f9e5b]', cell: 'border-[#cfe0c2] bg-[#eef5e8]', label: 'No warning marker' },
  mixed: { dot: 'bg-[#d9a23a]', cell: 'border-[#ecd9a8] bg-[#fbf2dc]', label: 'One mild marker' },
  caution: { dot: 'bg-[#c9553f]', cell: 'border-[#eec3b8] bg-[#fbe9e3]', label: 'Traditional stand-aside' },
};

const time = (s: string) => s.slice(11, 16);
const dayLabel = (s: string, ref: string) => (s.slice(0, 10) === ref ? time(s) : `${time(s)} (+1)`);

function Limb({ k, v, until, sub }: { k: string; v: string; until?: string; sub?: string }) {
  return (
    <div className="rounded-md border border-[#f0e4cc] bg-[#fdf8ec]/80 px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-wider text-[#b39a76]">{k}</p>
      <p className="text-sm font-medium text-[#5c4327]">{v}</p>
      {until && <p className="text-[10.5px] text-[#97795a]">until {until}</p>}
      {sub && <p className="text-[10.5px] text-[#97795a]">{sub}</p>}
    </div>
  );
}

export function PanchangCard({ symbol }: { symbol: string }) {
  const [place, setPlace] = useState<Place>(PLACES[0]);
  const [sel, setSel] = useState<string | null>(null);
  // results are tagged with the inputs they were fetched for, so stale ones simply read as "loading"
  const key = `${place.label}|${symbol}|${sel ?? ''}`;
  const [pRes, setPRes] = useState<{ key: string; data?: Panchang; err?: string } | null>(null);
  const [calRes, setCalRes] = useState<{ key: string; data: MarketCalendar | null } | null>(null);

  useEffect(() => {
    let live = true;
    panchangApi
      .today(place, sel ?? undefined, symbol)
      .then((data) => live && setPRes({ key, data }))
      .catch((e) => live && setPRes({ key, err: String(e?.message ?? e) }));
    return () => {
      live = false;
    };
  }, [place, symbol, sel, key]);

  useEffect(() => {
    let live = true;
    panchangApi
      .calendar(place, 30)
      .then((data) => live && setCalRes({ key: place.label, data }))
      .catch(() => live && setCalRes({ key: place.label, data: null }));
    return () => {
      live = false;
    };
  }, [place]);

  const p = pRes?.key === key ? (pRes.data ?? null) : null;
  const err = pRes?.key === key ? (pRes.err ?? null) : null;
  const cal = calRes?.key === place.label ? calRes.data : null;
  const ctx = p?.symbol_context;
  return (
    <Card className="border-[#ecdec2] bg-[#fffdf6]/90 shadow-sm">
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle className="font-display flex items-center gap-2 text-base text-[#5c4327]">
              <CalendarDays className="h-4 w-4 text-[#c98a2e]" /> Panchang &amp; Market Weather
            </CardTitle>
            <CardDescription className="text-xs text-[#97795a]">
              The five limbs of the Vedic almanac for the trading day, Rahu Kaal, and a 30-day calendar of
              lunar days and sky events. Sidereal · Lahiri, sunrise-based.
            </CardDescription>
          </div>
          <label className="flex items-center gap-1.5 text-xs text-[#7c5a2e]">
            <MapPin className="h-3.5 w-3.5 text-[#c98a2e]" />
            <select
              aria-label="Location"
              className="rounded-md border border-[#ecdec2] bg-[#fffdf6] px-2 py-1 text-xs"
              value={place.label}
              onChange={(e) => setPlace(PLACES.find((x) => x.label === e.target.value) ?? PLACES[0])}
            >
              {PLACES.map((x) => (
                <option key={x.label}>{x.label}</option>
              ))}
            </select>
          </label>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {err && <p className="rounded-md bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">Panchang unavailable: {err}</p>}
        {!p && !err && <Skeleton className="h-40 w-full bg-[#f3e6cc]" />}
        {p && (
          <>
            <div className="flex flex-wrap items-center gap-2 text-xs text-[#7c5a2e]">
              <span className="font-medium">
                {p.vara.weekday} {p.date} · {p.vara.name} (ruled by {p.vara.lord})
              </span>
              <span className="flex items-center gap-1">
                <Sun className="h-3.5 w-3.5 text-[#d98324]" /> {time(p.sunrise)}
              </span>
              <span className="flex items-center gap-1">
                <Sunset className="h-3.5 w-3.5 text-[#b0763a]" /> {time(p.sunset)}
              </span>
              <span className={`flex items-center gap-1 rounded-full border px-2 py-0.5 ${TONE[p.tone].cell}`}>
                <span className={`h-2 w-2 rounded-full ${TONE[p.tone].dot}`} /> {TONE[p.tone].label}
              </span>
              {sel && (
                <button className="underline" onClick={() => setSel(null)}>
                  back to today
                </button>
              )}
            </div>

            <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
              <Limb k="Tithi" v={p.tithi.label} until={dayLabel(p.tithi.ends, p.date)} />
              <Limb
                k="Nakshatra"
                v={`${p.nakshatra.name} · pada ${p.nakshatra.pada}`}
                until={dayLabel(p.nakshatra.ends, p.date)}
                sub={`lord ${p.nakshatra.lord}`}
              />
              <Limb
                k="Yoga"
                v={p.yoga.name}
                until={dayLabel(p.yoga.ends, p.date)}
                sub={p.yoga.auspicious ? 'auspicious' : 'traditionally avoided'}
              />
              <Limb k="Karana" v={p.karana.name} until={dayLabel(p.karana.ends, p.date)} />
              <Limb k="Moon / Sun" v={`${p.moon_sign} / ${p.sun_sign}`} sub="sidereal signs" />
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
              {(
                [
                  ['Rahu Kaal', p.rahu_kaal, 'text-[#a14d3c]'],
                  ['Yamaganda', p.yamaganda, 'text-[#a35a22]'],
                  ['Gulika', p.gulika, 'text-[#8a6a3a]'],
                  ['Abhijit muhurta', p.abhijit, 'text-[#4f7a3f]'],
                ] as const
              ).map(([k, s, c]) => (
                <div key={k} className="rounded-md border border-[#f0e4cc] bg-[#fffdf6] px-2.5 py-1.5">
                  <span className="text-[#97795a]">{k} </span>
                  <span className={`font-mono font-medium ${c}`}>
                    {s.start}–{s.end}
                  </span>
                </div>
              ))}
            </div>

            <div className="rounded-md border border-[#eed9b4] bg-gradient-to-r from-[#fdf3dc] to-[#fbead0] px-3 py-2">
              <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-[#7c4a12]">
                <Lightbulb className="h-3.5 w-3.5" /> In plain English
              </p>
              <p className="text-xs leading-relaxed text-[#6b4f2e]">{p.plain_english}</p>
              {p.notes.map((n) => (
                <p key={n} className="mt-1 text-xs leading-relaxed text-[#6b4f2e]">
                  • {n}
                </p>
              ))}
            </div>

            {ctx?.nakshatra && (
              <div className="rounded-md border border-[#e3d6ee] bg-[#f8f1fb] px-3 py-2 text-xs text-[#5e3f7f]">
                <p className="mb-1 flex flex-wrap items-center gap-2 font-semibold">
                  What history says for {ctx.name}
                  <VerdictBadge verdict={ctx.nakshatra.verdict} />
                </p>
                <p className="leading-relaxed">{ctx.plain_english}</p>
                {ctx.paksha && (
                  <p className="mt-1 leading-relaxed">
                    {ctx.paksha.label}: up on {ctx.paksha.hit_pct.toFixed(0)}% of days, average{' '}
                    {ctx.paksha.mean_pct >= 0 ? '+' : ''}
                    {ctx.paksha.mean_pct.toFixed(3)}% a day ({ctx.paksha.n.toLocaleString()} days).
                  </p>
                )}
                <p className="mt-1 text-[10.5px] text-[#8a6aa3]">Source: {ctx.data_source}{/illustrative/i.test(ctx.data_source) ? '' : ' · illustrative only'}.</p>
              </div>
            )}
          </>
        )}

        <div>
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#97795a]">Next 30 days</p>
            <a
              href={panchangApi.icsUrl(place, 30)}
              className="flex items-center gap-1 rounded-md border border-[#ecdec2] bg-[#fffdf6] px-2 py-1 text-xs text-[#7c5a2e] hover:border-[#d9b46a]"
            >
              <Download className="h-3.5 w-3.5" /> Add to calendar (.ics)
            </a>
          </div>
          {!cal && <Skeleton className="h-24 w-full bg-[#f3e6cc]" />}
          {cal && (
            <>
              <div className="grid grid-cols-5 gap-1 sm:grid-cols-10">
                {cal.rows.map((r) => (
                  <button
                    key={r.date}
                    onClick={() => setSel(r.date)}
                    title={`${r.weekday} ${r.date}\n${r.tithi} · ${r.nakshatra}\nYoga ${r.yoga}, karana ${r.karana}\nRahu Kaal ${r.rahu_kaal}${r.flags.length ? `\nFlags: ${r.flags.join(', ')}` : ''}`}
                    className={`rounded border px-1 py-1 text-left transition-transform hover:scale-[1.03] ${TONE[r.tone].cell} ${
                      r.is_weekend ? 'opacity-50' : ''
                    } ${p?.date === r.date ? 'ring-2 ring-[#c98a2e]' : ''}`}
                  >
                    <span className="block text-[9px] uppercase text-[#97795a]">{r.weekday.slice(0, 3)}</span>
                    <span className="block font-mono text-xs font-semibold text-[#5c4327]">{r.date.slice(8)}</span>
                    <span className="block truncate text-[9px] text-[#7c5a2e]">{r.tithi.split(' ')[1]}</span>
                  </button>
                ))}
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-[#97795a]">
                Weekdays ahead: {cal.weekday_tone_counts.favourable} clear, {cal.weekday_tone_counts.mixed} mixed,{' '}
                {cal.weekday_tone_counts.caution} stand-aside. Tap a day to see its full panchang. {cal.how_to_read}
              </p>
              {cal.events.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {cal.events.map((e) => (
                    <li key={e.when + e.title} className="text-xs text-[#5c4327]">
                      <span className="font-mono text-[#97795a]">{e.when.slice(5)}</span> ·{' '}
                      <span className="font-medium">{e.title}</span>
                      <span className="text-[#97795a]"> — {e.meaning}</span>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
