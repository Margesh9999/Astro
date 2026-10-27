'use client';

import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { enhanceApi } from '@/lib/astro/api';
import type { JatakaPlace, JatakaReport } from '@/lib/astro/types';
import { NorthIndianChart, type KundaliPlanet } from './north-indian-chart';
import { PLANET_META, PLANET_GUIDES, SIGNS } from './planet-meta';
import { Sparkles, IndianRupee, CalendarRange, LineChart as LineChartIcon, ScrollText, Wallet, Lightbulb, Scale, Grid3X3, Compass, Hourglass, Scroll, Stars, TrendingUp, AlertTriangle, Gem } from 'lucide-react';
import { Area, AreaChart, Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

const GRAHA_ORDER = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Rahu', 'Ketu', 'Lagna'];

/** Margesh defaults — the chart is configurable, Margesh is the default native */
const DEFAULTS = {
  name: 'Margesh',
  date: '1994-04-23',
  time: '06:45',
  place: 'Vallabh Vidyanagar, Gujarat, India',
};

function Pill({ children, tone = 'gold' }: { children: ReactNode; tone?: 'gold' | 'green' | 'rose' | 'lav' }) {
  const tones = {
    gold: 'border-[#dcc08a] bg-[#f9efd8] text-[#8a6a3a]',
    green: 'border-[#a8d8bf] bg-[#e2f3e9] text-[#2f7357]',
    rose: 'border-[#e8b3a8] bg-[#fbe7e0] text-[#a34332]',
    lav: 'border-[#cbb8dd] bg-[#efe7f8] text-[#6b4e93]',
  };
  return <span className={`rounded border px-1.5 py-px text-[10px] font-medium ${tones[tone]}`}>{children}</span>;
}

function Note({ text, icon }: { text: string; icon?: ReactNode }) {
  return (
    <div className="flex items-start gap-1.5 rounded-lg border border-[#e8ddb8] bg-[#fdf8ec] px-2.5 py-2">
      {icon ?? <Lightbulb className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-[#c98a2e]" />}
      <p className="text-[11px] leading-relaxed text-[#7c5a2e]">{text}</p>
    </div>
  );
}

/** A collapsible concept section used inside the Trading Blueprint tab */
function Concept({ icon, title, subtitle, children, open = false }: {
  icon: ReactNode; title: string; subtitle: string; children: ReactNode; open?: boolean;
}) {
  return (
    <details open={open} className="group rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/80">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2.5">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-[#eccf9d] bg-[#fdf3dc]">{icon}</span>
        <span className="flex-1">
          <span className="block text-xs font-semibold text-[#5c4327]">{title}</span>
          <span className="block text-[10px] text-[#b39a76]">{subtitle}</span>
        </span>
        <span className="text-[10px] text-[#c98a2e] group-open:hidden">open ▾</span>
        <span className="hidden text-[10px] text-[#c98a2e] group-open:inline">close ▴</span>
      </summary>
      <div className="border-t border-[#f4ead2] px-3 py-3">{children}</div>
    </details>
  );
}

/* ═════════════════ Merged: Janma Kundli & Wealth Blueprint (configurable, default Margesh) ═════════════════ */
export function JatakaCard({ symbol, symbolName }: { symbol: string; symbolName?: string }) {
  const [report, setReport] = useState<JatakaReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState('kundali');

  // configurable birth data — pre-filled with the default native (Margesh)
  const [name, setName] = useState(DEFAULTS.name);
  const [date, setDate] = useState(DEFAULTS.date);
  const [time, setTime] = useState(DEFAULTS.time);
  const [place, setPlace] = useState(DEFAULTS.place);
  const [capital, setCapital] = useState(50000);
  const [targetWeekly, setTargetWeekly] = useState(500);
  const [places, setPlaces] = useState<JatakaPlace[]>([]);
  const [showPlaces, setShowPlaces] = useState(false);
  const seqRef = useRef(0);

  const load = useCallback(async () => {
    const seq = ++seqRef.current;
    setLoading(true);
    setError(null);
    try {
      const r = await enhanceApi.jatakaReport({
        symbol,
        name: name || undefined,
        date: date || undefined,
        time: time || undefined,
        place: place || undefined,
        capital,
        target_weekly: targetWeekly,
      });
      if (seq !== seqRef.current) return;
      setReport(r);
    } catch (e) {
      if (seq !== seqRef.current) return;
      setError(String((e as Error)?.message ?? e));
    } finally {
      if (seq === seqRef.current) setLoading(false);
    }
  }, [symbol, name, date, time, place, capital, targetWeekly]);

  useEffect(() => {
    load();
  }, [load]);

  // place search (debounced)
  useEffect(() => {
    const t = setTimeout(() => {
      enhanceApi
        .jatakaPlaces(place)
        .then((r) => setPlaces(r.places ?? []))
        .catch(() => setPlaces([]));
    }, 250);
    return () => clearTimeout(t);
  }, [place]);

  const lagnaSign = report?.lagna_sign ?? 0;
  const kundaliPlanets: KundaliPlanet[] = report
    ? GRAHA_ORDER.filter((n) => report.positions[n] && n !== 'Lagna').map((n) => ({
        name: n,
        signNumber: report.positions[n].sign_number,
        degree: report.positions[n].degree_within_sign,
        retrograde: report.positions[n].is_retrograde && n !== 'Rahu' && n !== 'Ketu',
        house: report.positions[n].house,
        dignity: report.positions[n].dignity,
        nakshatra: report.positions[n].nakshatra,
        pada: report.positions[n].pada,
      }))
    : [];

  const lifeData = report
    ? report.lifetime_wealth.stages.map((s) => ({
        age: (s.age_from + s.age_to) / 2,
        index: s.wealth_index,
        lord: s.lord,
      }))
    : [];

  const cur = report?.current_dasha;
  const aa = report?.astro_analysis;
  const pn = report?.planetary_notes ?? {};
  const savData = aa
    ? aa.ashtakvarga.sav.map((bindus, i) => ({ sign: SIGNS[i], bindus }))
    : [];
  const wealthHouses = aa
    ? Object.entries(aa.ashtakvarga.wealth).map(([k, v]) => ({
        house: Number(k.replace('house_', '')),
        ...v,
      })).sort((a, b) => a.house - b.house)
    : [];

  return (
    <Card className="vedic-card">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-[#c98a2e]" />
            <CardTitle className="font-display text-base tracking-wide">
              Janma Kundli &amp; Wealth Blueprint — <span className="text-[#a5698f]">{report?.birth.name || 'Margesh'}</span>
            </CardTitle>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Pill>Vedic · Lahiri{report?.ayanamsa != null ? ` · ${report.ayanamsa.toFixed(2)}°` : ''}</Pill>
            {cur?.mahadasha && <Pill tone="lav">MD {cur.mahadasha} / AD {cur.antardasha}</Pill>}
            {aa?.yogini?.current && <Pill tone="green">Yogini {aa.yogini.current.yogini}</Pill>}
          </div>
        </div>
        <CardDescription className="text-[#97795a]">
          One merged birth-chart suite — computed live from the configurable form below (defaults to Margesh · 23 Apr
          1994 · 06:45 IST · Vallabh Vidyanagar) · drikpanchang-standard Vimshottari · income &amp; lifetime wealth plan ·
          correlated with {symbolName || symbol}
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {/* ── configurable birth bar ── */}
        <div className="grid grid-cols-2 gap-2 rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/80 p-3 md:grid-cols-6">
          <label className="col-span-1 text-[10px] uppercase tracking-wide text-[#b39a76] md:col-span-2">
            Name
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Margesh (default)"
                   className="mt-1 h-8 border-[#ecdec2] bg-white text-xs" />
          </label>
          <label className="text-[10px] uppercase tracking-wide text-[#b39a76]">
            Birth date
            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)}
                   className="mt-1 h-8 border-[#ecdec2] bg-white text-xs" />
          </label>
          <label className="text-[10px] uppercase tracking-wide text-[#b39a76]">
            Birth time
            <Input type="time" value={time} onChange={(e) => setTime(e.target.value)}
                   className="mt-1 h-8 border-[#ecdec2] bg-white text-xs" />
          </label>
          <label className="relative col-span-1 text-[10px] uppercase tracking-wide text-[#b39a76] md:col-span-2">
            Birth place
            <Input value={place} onChange={(e) => { setPlace(e.target.value); setShowPlaces(true); }}
                   onFocus={() => setShowPlaces(true)}
                   placeholder="Vallabh Vidyanagar, Gujarat (default)"
                   className="mt-1 h-8 border-[#ecdec2] bg-white text-xs" />
            {showPlaces && places.length > 0 && (
              <div className="warm-scroll absolute z-30 mt-1 max-h-40 w-full overflow-y-auto rounded-md border border-[#ecdec2] bg-[#fffdf6] shadow-lg">
                {places.map((p) => (
                  <button
                    key={p.name}
                    className="block w-full px-2 py-1.5 text-left text-xs text-[#5c4327] hover:bg-[#f9efd8]"
                    onClick={() => { setPlace(p.name); setShowPlaces(false); }}
                  >
                    {p.name}
                  </button>
                ))}
              </div>
            )}
          </label>
          <label className="text-[10px] uppercase tracking-wide text-[#b39a76]">
            Capital (GBP)
            <Input type="number" min={1000} step={1000} value={capital}
                   onChange={(e) => setCapital(Math.max(0, Number(e.target.value)))}
                   className="mt-1 h-8 border-[#ecdec2] bg-white text-xs" />
          </label>
          <label className="text-[10px] uppercase tracking-wide text-[#b39a76]">
            Target £/week
            <Input type="number" min={0} step={50} value={targetWeekly}
                   onChange={(e) => setTargetWeekly(Math.max(0, Number(e.target.value)))}
                   className="mt-1 h-8 border-[#ecdec2] bg-white text-xs" />
          </label>
          <div className="flex items-end">
            <Button size="sm" onClick={load} disabled={loading}
                    className="h-8 w-full border-[#d9b46a] bg-gradient-to-b from-[#fbe3bd] to-[#f6d194] text-xs text-[#7c4a12] hover:from-[#f6d194] hover:to-[#eec27f]">
              Recalculate
            </Button>
          </div>
        </div>

        {loading && !report && (
          <div className="space-y-2">
            <Skeleton className="h-64 w-full bg-[#efdfbc]" />
          </div>
        )}
        {error && !report && (
          <div className="rounded-md border border-[#eecfc7] bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">
            Jataka engine unavailable — {error}
          </div>
        )}

        {report && (
          <Tabs value={tab} onValueChange={setTab} className="mt-0">
            <TabsList className="flex-wrap bg-[#f4e8cf]">
              <TabsTrigger value="kundali" className="text-xs data-[state=active]:bg-[#fffdf6]">Kundali</TabsTrigger>
              <TabsTrigger value="dasha" className="text-xs data-[state=active]:bg-[#fffdf6]">Dasha Tree</TabsTrigger>
              <TabsTrigger value="analysis" className="text-xs data-[state=active]:bg-[#fffdf6]">Astro Analysis</TabsTrigger>
              <TabsTrigger value="blueprint" className="text-xs data-[state=active]:bg-[#fffdf6]">✦ Trading Blueprint</TabsTrigger>
              <TabsTrigger value="money" className="text-xs data-[state=active]:bg-[#fffdf6]">Money Plan</TabsTrigger>
              <TabsTrigger value="lifetime" className="text-xs data-[state=active]:bg-[#fffdf6]">Lifetime</TabsTrigger>
              <TabsTrigger value="synthesis" className="text-xs data-[state=active]:bg-[#fffdf6]">Synthesis</TabsTrigger>
            </TabsList>

            {/* ── KUNDALI tab (merged: chart + verdict + graha table + dynamic notes) ── */}
            <TabsContent value="kundali" className="mt-3">
              {report.verdict && (
                <div className="mb-3 rounded-lg border border-[#e4d0b4] bg-gradient-to-r from-[#fdf3dc] via-[#f9e9d2] to-[#f6e3c4] p-3">
                  <p className="font-display text-[10px] uppercase tracking-[0.18em] text-[#a8701a]">
                    Trading suitability verdict
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-[#6b4f2e]">
                    <span className="font-semibold text-[#a8701a]">{report.verdict.headline}</span> — score{' '}
                    {report.verdict.score}/100. {report.verdict.plain}
                  </p>
                </div>
              )}
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <div className="flex flex-col items-center rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/70 p-3">
                  <NorthIndianChart
                    lagnaSignNumber={lagnaSign}
                    planets={kundaliPlanets}
                    size={340}
                    title={`Rasi Chart · Lagna ${SIGNS[lagnaSign]}`}
                  />
                  <p className="mt-1 text-center text-[10px] text-[#b39a76]">
                    {report.birth.name} · {report.birth.date} {report.birth.time} · {report.birth.place}
                  </p>
                </div>
                <div className="warm-scroll max-h-[420px] overflow-y-auto rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/70 p-3">
                  <p className="mb-2 text-xs font-medium text-[#5c4327]">Graha positions (tap chart glyphs for meaning)</p>
                  <table className="w-full text-left text-[11px]">
                    <thead>
                      <tr className="text-[10px] uppercase tracking-wide text-[#b39a76]">
                        <th className="py-1">Graha</th><th>Sign</th><th>Degree</th><th>Nakshatra</th><th>House</th><th>Strength</th>
                      </tr>
                    </thead>
                    <tbody>
                      {GRAHA_ORDER.filter((n) => report.positions[n]).map((n) => {
                        const p = report.positions[n];
                        return (
                          <tr key={n} className="border-t border-[#f4ead2]" title={PLANET_GUIDES[n]?.meaning}>
                            <td className="py-1.5">
                              <span style={{ color: PLANET_META[n]?.color }} className="mr-1 font-semibold">
                                {PLANET_META[n]?.glyph} {n}
                              </span>
                              {p.is_retrograde && n !== 'Rahu' && n !== 'Ketu' && <span className="text-[#cf5b54]">℞</span>}
                            </td>
                            <td className="font-mono">{p.sign}</td>
                            <td className="font-mono">{Math.floor(p.degree_within_sign)}°{String(Math.round((p.degree_within_sign % 1) * 60)).padStart(2, '0')}&apos;</td>
                            <td>{p.nakshatra} {p.pada}</td>
                            <td className="font-mono">{p.house}</td>
                            <td>
                              <Pill tone={p.dignity_score >= 0.7 ? 'green' : p.dignity_score <= 0.3 ? 'rose' : 'gold'}>
                                {p.dignity}
                              </Pill>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
              {/* dynamic per-graha money notes (generated for ANY chart) */}
              <div className="warm-scroll mt-3 max-h-[240px] space-y-2 overflow-y-auto pr-1">
                {GRAHA_ORDER.filter((n) => pn[n]).map((n) => (
                  <div key={n} className="rounded-md border border-[#f0e4cc] bg-[#fdf8ec]/80 px-3 py-2">
                    <p className="text-xs font-medium text-[#5c4327]">
                      <span className="mr-1.5" style={{ color: PLANET_META[n]?.color ?? '#b0763a' }}>
                        {PLANET_META[n]?.glyph ?? '•'}
                      </span>
                      {n} — {report.positions[n].sign} {Math.floor(report.positions[n].degree_within_sign)}°, house {report.positions[n].house}
                    </p>
                    <p className="mt-0.5 text-[11px] leading-relaxed text-[#97795a]">{pn[n]}</p>
                  </div>
                ))}
              </div>
            </TabsContent>

            {/* ── DASHA tab (T12⑥ corrected logic) ── */}
            <TabsContent value="dasha" className="mt-3">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <Pill tone="lav">Moon nakshatra #{report.dasha_tree.moon_nakshatra_index + 1} · pada {report.dasha_tree.pada}</Pill>
                <Pill>First lord {report.dasha_tree.first_lord} · balance {report.dasha_tree.balance_years.toFixed(2)}y</Pill>
                {cur?.interpretation && <Pill tone="green">Now: {cur.interpretation.headline}</Pill>}
              </div>
              {cur?.interpretation && <Note text={cur.interpretation.detail} />}
              <div className="mt-3 space-y-2">
                {report.dasha_tree.mahadashas.map((md) => {
                  const isCurrent = cur?.mahadasha === md.lord && cur?.md_start === md.start;
                  return (
                    <details
                      key={md.lord + md.start}
                      open={isCurrent}
                      className={`rounded-lg border px-3 py-2 ${isCurrent ? 'border-[#d9b46a] bg-[#fdf3dc]' : 'border-[#f0e4cc] bg-[#fffdf6]/70'}`}
                    >
                      <summary className="cursor-pointer list-none">
                        <span className="font-display text-sm font-semibold text-[#5c4327]">
                          {md.glyph} {md.lord} Mahadasha
                        </span>
                        <span className="ml-2 font-mono text-[11px] text-[#97795a]">
                          {md.start} → {md.end} · {md.years}y
                        </span>
                        {isCurrent && <Badge className="ml-2 bg-[#e8a04c] text-[10px] text-white">current</Badge>}
                      </summary>
                      <div className="mt-2 grid grid-cols-1 gap-1 sm:grid-cols-3">
                        {md.antardashas.map((ad) => {
                          const adCurrent = isCurrent && cur?.antardasha === ad.lord && cur?.ad_start === ad.start;
                          return (
                            <div key={ad.lord + ad.start}
                                 className={`rounded border px-2 py-1 text-[11px] ${adCurrent ? 'border-[#c9553f] bg-[#fbe7e0] font-medium' : 'border-[#f0e4cc] bg-[#fdf8ec]'}`}>
                              <span className="text-[#5c4327]">{ad.glyph} {ad.lord}</span>
                              <span className="ml-1 font-mono text-[10px] text-[#97795a]">{ad.start.slice(0, 7)}–{ad.end.slice(0, 7)}</span>
                            </div>
                          );
                        })}
                      </div>
                    </details>
                  );
                })}
              </div>
              <p className="mt-2 text-[10px] text-[#b39a76]">
                Antardasha logic: every mahadasha starts with its own lord as the first antardasha, then the
                nine sub-periods run in Vimshottari order and sum exactly to the mahadasha length
                (year = 365.2425 days) — matching drikpanchang.
              </p>
            </TabsContent>

            {/* ── ANALYSIS tab ── */}
            <TabsContent value="analysis" className="mt-3 flex flex-col gap-3">
              <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                {report.strengths.ranked.map(([g, s], i) => (
                  <div key={g} className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6]/80 px-3 py-2">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-semibold text-[#5c4327]">
                        <span className="mr-1" style={{ color: PLANET_META[g]?.color }}>{PLANET_META[g]?.glyph}</span>
                        #{i + 1} {g}
                      </p>
                      <span className="font-mono text-xs text-[#8a6a3a]">{s}/100</span>
                    </div>
                    <div className="my-1 h-1.5 overflow-hidden rounded-full bg-[#f4ead2]">
                      <div className="h-full rounded-full bg-gradient-to-r from-[#e8a04c] to-[#c9553f]"
                           style={{ width: `${s}%` }} />
                    </div>
                    <p className="text-[11px] leading-snug text-[#7c5a2e]">{report.strengths.notes[g]}</p>
                    <p className="mt-1 text-[10px] text-[#b39a76]">Markets: {PLANET_GUIDES[g]?.market}</p>
                  </div>
                ))}
              </div>
              <Note text={report.market_recommendations.rationale} />
            </TabsContent>

            {/* ── TRADING BLUEPRINT tab — every concept of the Astro Analysis guide, plain English ── */}
            <TabsContent value="blueprint" className="mt-3 flex flex-col gap-3">
              {!aa || !aa.verdict || !aa.blueprint ? (
                <Note text="Astro Analysis engine unavailable for this chart — the rest of the suite still works." />
              ) : (
                <>
                  {/* hero verdict */}
                  <div className="rounded-xl border border-[#d9b46a] bg-gradient-to-r from-[#fdf3dc] via-[#fffdf6] to-[#f2f5ec] p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="flex items-center gap-1.5 font-display text-sm font-semibold text-[#8a6a3a]">
                        <Gem className="h-4 w-4" /> Trading &amp; Money Blueprint · {report.birth.name}
                      </p>
                      <Pill tone={aa.verdict.score >= 60 ? 'green' : aa.verdict.score >= 40 ? 'gold' : 'rose'}>
                        {aa.verdict.score}/100
                      </Pill>
                    </div>
                    <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-[#f4ead2]">
                      <div className="h-full rounded-full bg-gradient-to-r from-[#8bb5a3] via-[#e8a04c] to-[#c9553f]"
                           style={{ width: `${aa.verdict.score}%` }} />
                    </div>
                    <p className="mt-2 text-xs font-semibold text-[#5c4327]">{aa.verdict.headline}</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {aa.verdict.reasons.map((r, i) => <Pill key={i} tone="green">✓ {r}</Pill>)}
                      {aa.verdict.risks.map((r, i) => <Pill key={i} tone="rose">⚠ {r}</Pill>)}
                    </div>
                    <p className="mt-2 text-[11px] leading-relaxed text-[#7c5a2e]">{aa.blueprint.plain}</p>
                  </div>

                  {/* 30/60/90/365 plan */}
                  <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                    {aa.blueprint.plan.map((p) => (
                      <div key={p.window} className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6]/80 px-3 py-2">
                        <p className="text-xs font-semibold text-[#8a6a3a]">
                          <CalendarRange className="mr-1 inline h-3.5 w-3.5" />{p.window}
                        </p>
                        <p className="mt-0.5 text-[11px] leading-relaxed text-[#5c4327]">{p.action}</p>
                      </div>
                    ))}
                  </div>

                  {/* income strip */}
                  <div className="rounded-xl border border-[#eed9b4] bg-gradient-to-r from-[#fdf3dc] to-[#fbead0] p-3">
                    <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-[#8a6a3a]">
                      <IndianRupee className="h-3.5 w-3.5" /> Income plan · {report.income_forecast.strategy}
                    </p>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      {([['Weekly', aa.blueprint.income.weekly], ['Monthly', aa.blueprint.income.monthly], ['Annual', aa.blueprint.income.annual]] as const).map(([label, band]) => (
                        <div key={label} className="rounded-lg bg-[#fffdf6]/90 px-2 py-1.5">
                          <p className="text-[10px] uppercase tracking-wide text-[#b39a76]">{label}</p>
                          <p className="font-mono text-sm font-semibold text-[#3f8a6e]">
                            £{band.low.toLocaleString()}–£{band.high.toLocaleString()}
                          </p>
                        </div>
                      ))}
                    </div>
                    <p className="mt-1.5 text-[10px] text-[#97795a]">
                      Modelled bands at £{aa.blueprint.income.capital.toLocaleString()} capital · target
                      £{aa.blueprint.income.target_weekly.toLocaleString()}/week is{' '}
                      {aa.blueprint.income.target_feasible ? 'feasible at this capital' : `needs ~£${aa.blueprint.income.capital_needed.at_mid_yield.toLocaleString()} at mid yield`} ·
                      not guarantees.
                    </p>
                  </div>

                  {/* ── concept sections ── */}
                  <Concept icon={<Grid3X3 className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Vargas — the 16 divisional charts (BPHS)"
                           subtitle={aa.vargas.info.D9.title + ' · ' + aa.vargas.info.D10.title} open>
                    <Note text={aa.vargas.plain} />
                    <Note text={aa.vargas.navamsa_focus} icon={<Stars className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-[#c98a2e]" />} />
                    <Note text={aa.vargas.dasamsa_focus} icon={<TrendingUp className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-[#c98a2e]" />} />
                    <div className="mt-2 overflow-x-auto">
                      <table className="w-full text-left text-[10px]">
                        <thead>
                          <tr className="text-[#b39a76]">
                            <th className="py-1 pr-2">Graha</th>
                            {(['D2', 'D3', 'D9', 'D10', 'D12', 'D60'] as const).map((v) => (
                              <th key={v} className="py-1 pr-2" title={aa.vargas.info[v]?.meaning}>{v}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {GRAHA_ORDER.filter((n) => aa.vargas.planets[n]).map((n) => (
                            <tr key={n} className="border-t border-[#f4ead2]">
                              <td className="py-1 pr-2 font-medium" style={{ color: PLANET_META[n]?.color }}>
                                {PLANET_META[n]?.glyph} {n}
                              </td>
                              {(['D2', 'D3', 'D9', 'D10', 'D12', 'D60'] as const).map((v) => {
                                const cell = aa.vargas.planets[n].vargas[v];
                                const good = ['exalted', 'own', 'moolatrikona'].includes(cell.dignity);
                                const bad = cell.dignity === 'debilitated';
                                return (
                                  <td key={v} className={`py-1 pr-2 ${good ? 'text-[#2f7357] font-medium' : bad ? 'text-[#a34332]' : 'text-[#7c5a2e]'}`}>
                                    {cell.sign}
                                  </td>
                                );
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Concept>

                  <Concept icon={<Compass className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Jaimini — chara karakas, Arudha Lagna & Karakamsa"
                           subtitle={`Soul planet ${aa.jaimini.atmakaraka} · Karakamsa ${aa.jaimini.karakamsa_sign}`}>
                    <Note text={aa.jaimini.plain} />
                    <div className="mt-2 grid grid-cols-1 gap-1.5 md:grid-cols-2">
                      {aa.jaimini.karakas.map((k) => (
                        <div key={k.key} className="rounded-lg border border-[#f0e4cc] bg-[#fdf8ec] px-2.5 py-1.5">
                          <p className="text-[11px] font-semibold text-[#5c4327]">
                            <Pill tone="lav">{k.key}</Pill> {k.label} —{' '}
                            <span style={{ color: PLANET_META[k.planet]?.color }}>
                              {PLANET_META[k.planet]?.glyph} {k.planet}
                            </span>{' '}
                            <span className="font-normal text-[#97795a]">{k.sign}, house {k.house}</span>
                          </p>
                          <p className="text-[10px] leading-snug text-[#7c5a2e]">{k.money_meaning}</p>
                        </div>
                      ))}
                    </div>
                  </Concept>

                  <Concept icon={<Hourglass className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Avasthas — planetary ages (BPHS states)"
                           subtitle="Which grahas are in their delivery prime">
                    <Note text={aa.avasthas.plain} />
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {Object.entries(aa.avasthas.planets).map(([n, r]) => (
                        <Pill key={n} tone={r.state.startsWith('Yuva') ? 'green' : r.state.startsWith('Mrita') || r.state.startsWith('Vriddha') ? 'rose' : 'gold'}>
                          {PLANET_META[n]?.glyph} {n}: {r.state}
                        </Pill>
                      ))}
                    </div>
                  </Concept>

                  <Concept icon={<Stars className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Yogas — planetary combinations"
                           subtitle={`${aa.yogas.found.length} classical combination(s) detected`}>
                    <Note text={aa.yogas.plain} />
                    <div className="mt-2 space-y-1.5">
                      {aa.yogas.found.map((y, i) => (
                        <div key={i} className="rounded-lg border border-[#f0e4cc] bg-[#fdf8ec] px-2.5 py-1.5">
                          <p className="text-[11px] font-semibold text-[#5c4327]">
                            {y.name} <Pill tone={y.strength === 'strong' ? 'green' : 'gold'}>{y.category}</Pill>
                            {y.planets.length > 0 && <span className="ml-1 text-[10px] text-[#97795a]">({y.planets.join(' + ')})</span>}
                          </p>
                          <p className="text-[10px] leading-snug text-[#7c5a2e]">{y.meaning}</p>
                        </div>
                      ))}
                    </div>
                  </Concept>

                  <Concept icon={<Scale className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Shadbala — six-fold planetary strength"
                           subtitle={`Ranking in Rupas · day lord ${aa.shadbala.day_lord} · hora lord ${aa.shadbala.hora_lord}`}>
                    <Note text={aa.shadbala.plain} />
                    <div className="mt-2 space-y-1.5">
                      {aa.shadbala.ranked.map(([n, rupas]) => {
                        const req = aa.shadbala.planets[n].required;
                        const pct = Math.min(100, (rupas / 10) * 100);
                        const reqPct = (req / 10) * 100;
                        return (
                          <div key={n}>
                            <div className="flex items-center justify-between text-[11px]">
                              <span className="text-[#5c4327]">{PLANET_META[n]?.glyph} {n}</span>
                              <span className="font-mono text-[#8a6a3a]">
                                {rupas.toFixed(2)} <span className="text-[10px] text-[#b39a76]">/ {req.toFixed(2)} needed</span>
                              </span>
                            </div>
                            <div className="relative h-1.5 overflow-hidden rounded-full bg-[#f4ead2]">
                              <div className="h-full rounded-full bg-gradient-to-r from-[#8bb5a3] to-[#4a9a7e]" style={{ width: `${pct}%` }} />
                              <div className="absolute top-0 h-full w-px bg-[#c9553f]" style={{ left: `${reqPct}%` }} />
                            </div>
                            <p className="mt-0.5 text-[10px] text-[#97795a]">{aa.shadbala.planets[n].verdict}</p>
                          </div>
                        );
                      })}
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-1 md:grid-cols-4">
                      {Object.entries(aa.shadbala.planets).flatMap(([n, r]) =>
                        Object.entries(r.components).map(([c, v]) => (
                          <div key={n + c} className="rounded border border-[#f0e4cc] bg-[#fffdf6]/80 px-1.5 py-1 text-[9px]">
                            <p className="font-medium text-[#5c4327]">{n} · {c.split(' ')[0]}</p>
                            <p className="font-mono text-[#8a6a3a]">{v}</p>
                          </div>
                        )),
                      )}
                    </div>
                  </Concept>

                  <Concept icon={<Scale className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Bhavabala — house strength"
                           subtitle={`Strongest: house ${aa.bhavabala.strongest_house.house} (${aa.bhavabala.strongest_house.sign})`}>
                    <Note text={aa.bhavabala.plain} />
                    <div className="mt-2 grid grid-cols-2 gap-1.5 md:grid-cols-4">
                      {aa.bhavabala.houses.map((h) => (
                        <div key={h.house} className={`rounded-lg border px-2 py-1.5 ${h.wealth_flag ? 'border-[#d9b46a] bg-[#fdf3dc]' : 'border-[#f0e4cc] bg-[#fffdf6]/80'}`}>
                          <div className="flex items-center justify-between text-[10px]">
                            <span className="font-semibold text-[#5c4327]">H{h.house} {h.sign}</span>
                            <span className="font-mono text-[#8a6a3a]">{h.score}</span>
                          </div>
                          <div className="mt-1 h-1 overflow-hidden rounded-full bg-[#f4ead2]">
                            <div className="h-full rounded-full bg-gradient-to-r from-[#e8a04c] to-[#c9553f]" style={{ width: `${h.score}%` }} />
                          </div>
                          {h.wealth_flag && <p className="mt-0.5 text-[9px] text-[#a8701a]">wealth house</p>}
                        </div>
                      ))}
                    </div>
                  </Concept>

                  <Concept icon={<Grid3X3 className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Ashtakvarga — bindu point system"
                           subtitle={`Sarvashtakavarga ${aa.ashtakvarga.sav_total} bindus · prastara ${aa.ashtakvarga.prastara_total}`}>
                    <Note text={aa.ashtakvarga.plain} />
                    <div className="mt-2 h-40 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={savData} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
                          <XAxis dataKey="sign" tick={{ fontSize: 9, fill: '#97795a' }} interval={0} angle={-35} textAnchor="end" height={44} />
                          <YAxis domain={[0, 40]} tick={{ fontSize: 9, fill: '#97795a' }} />
                          <Tooltip
                            contentStyle={{ background: '#fffdf6', border: '1px solid #ecdec2', borderRadius: 8, fontSize: 11 }}
                            formatter={(v) => [`${v} bindus`, 'SAV']}
                          />
                          <Bar dataKey="bindus" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                            {savData.map((d, i) => (
                              <Cell key={i} fill={d.bindus >= 29 ? '#4a9a7e' : d.bindus >= 25 ? '#c9962e' : '#c9553f'} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-1.5 md:grid-cols-3">
                      {wealthHouses.map((h) => (
                        <div key={h.house} className="rounded border border-[#f0e4cc] bg-[#fdf8ec] px-2 py-1 text-[10px]">
                          <span className="font-semibold text-[#5c4327]">House {h.house} ({h.sign})</span>
                          <span className="ml-1 font-mono text-[#8a6a3a]">{h.bindus} bindus</span>
                          <span className="ml-1 text-[9px] text-[#97795a]">{h.status}</span>
                        </div>
                      ))}
                    </div>
                  </Concept>

                  <Concept icon={<Compass className="h-3.5 w-3.5 text-[#c98a2e]" />} title="KP system — star & sub lords (Krishnamurti Paddhati)"
                           subtitle={`Ruling planets: ${aa.kp.ruling_planets.join(', ')} · day lord ${aa.kp.day_lord}`}>
                    <Note text={aa.kp.plain} />
                    <div className="mt-2 overflow-x-auto">
                      <table className="w-full text-left text-[10px]">
                        <thead>
                          <tr className="text-[#b39a76]">
                            <th className="py-1 pr-2">Cusp</th><th className="pr-2">Sign</th><th className="pr-2">Degree</th><th className="pr-2">Star lord</th><th className="pr-2">Sub lord</th>
                          </tr>
                        </thead>
                        <tbody>
                          {aa.kp.cusps.map((c) => (
                            <tr key={c.cusp} className={`border-t border-[#f4ead2] ${[2, 6, 10, 11].includes(c.cusp) ? 'bg-[#fdf3dc]/70' : ''}`}>
                              <td className="py-1 pr-2 font-medium text-[#5c4327]">
                                {c.cusp}{c.cusp_name ? ` · ${c.cusp_name}` : ''}
                              </td>
                              <td className="pr-2 text-[#7c5a2e]">{c.sign}</td>
                              <td className="pr-2 font-mono text-[#7c5a2e]">{c.degree.toFixed(1)}°</td>
                              <td className="pr-2 text-[#97795a]">{c.star_lord}</td>
                              <td className="pr-2 font-medium text-[#6b4e93]">{c.sub_lord}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Concept>

                  <Concept icon={<Hourglass className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Yogini dasha — the fast 36-year timer"
                           subtitle={`Now: ${aa.yogini.current.yogini} (${aa.yogini.current.lord}) · ${aa.yogini.direction} cycle`}>
                    <Note text={aa.yogini.plain} />
                    <div className="mt-2 space-y-1">
                      {aa.yogini.periods.map((p, i) => (
                        <div key={i} className="flex flex-wrap items-center justify-between rounded border border-[#f0e4cc] bg-[#fdf8ec] px-2 py-1 text-[10px]">
                          <span className="font-medium text-[#5c4327]">{p.yogini} ({p.lord})</span>
                          <span className="font-mono text-[#97795a]">{p.start} → {p.end} · {p.years}y</span>
                        </div>
                      ))}
                    </div>
                  </Concept>

                  <Concept icon={<Scroll className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Karma Vipaka — nakshatra karmic lens"
                           subtitle={`${aa.karma_vipaka.nakshatra} · deity ${aa.karma_vipaka.deity}`}>
                    <Note text={aa.karma_vipaka.plain} icon={<Scroll className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-[#c98a2e]" />} />
                  </Concept>

                  <Concept icon={<TrendingUp className="h-3.5 w-3.5 text-[#c98a2e]" />} title="Transits × Ashtakvarga — is the ground fertile?"
                           subtitle="Saturn / Jupiter / Rahu / Ketu against your bindu map">
                    <Note text={aa.transits.plain} />
                    <div className="mt-2 space-y-1.5">
                      {aa.transits.rows.map((t, i) => (
                        <div key={i} className="rounded-lg border border-[#f0e4cc] bg-[#fdf8ec] px-2.5 py-1.5">
                          <p className="text-[11px] font-semibold text-[#5c4327]">
                            {PLANET_META[t.planet]?.glyph} {t.planet} → {t.sign} (house {t.house})
                            <Pill tone={t.sav_bindus >= 28 ? 'green' : t.sav_bindus >= 25 ? 'gold' : 'rose'}>
                              {t.sav_bindus} SAV bindus
                            </Pill>
                            {t.own_bindus != null && <Pill>own {t.own_bindus}</Pill>}
                          </p>
                          <p className="text-[10px] leading-snug text-[#7c5a2e]">{t.plain}</p>
                        </div>
                      ))}
                    </div>
                  </Concept>

                  <Concept icon={<ScrollText className="h-3.5 w-3.5 text-[#c98a2e]" />} title="House-by-house synthesis — all 12 bhavas"
                           subtitle="Every house read for its money promise">
                    <div className="space-y-1.5">
                      {aa.houses.map((h) => (
                        <div key={h.house} className={`rounded-lg border px-2.5 py-1.5 ${h.wealth_flag ? 'border-[#d9b46a] bg-[#fdf3dc]/80' : 'border-[#f0e4cc] bg-[#fffdf6]/80'}`}>
                          <p className="text-[11px] font-semibold text-[#5c4327]">
                            House {h.house} · {h.sign} {h.wealth_flag && <Pill tone="gold">wealth</Pill>}
                            <span className="ml-1 font-mono text-[10px] text-[#97795a]">score {h.score} · {h.bindus} bindus</span>
                          </p>
                          <p className="text-[10px] leading-snug text-[#7c5a2e]">{h.plain}</p>
                        </div>
                      ))}
                    </div>
                  </Concept>

                  {/* risks & remedies */}
                  <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                    <div className="rounded-lg border border-[#eecfc7] bg-[#fbeae4]/70 px-3 py-2">
                      <p className="flex items-center gap-1 text-xs font-semibold text-[#a14d3c]">
                        <AlertTriangle className="h-3.5 w-3.5" /> Risk flags
                      </p>
                      {aa.blueprint.risk_flags.length === 0
                        ? <p className="mt-1 text-[11px] text-[#7c5a2e]">No blocking flags — keep standard discipline.</p>
                        : (
                          <ul className="mt-1 space-y-1">
                            {aa.blueprint.risk_flags.map((r, i) => (
                              <li key={i} className="text-[11px] leading-snug text-[#7c5a2e]">• {r}</li>
                            ))}
                          </ul>
                        )}
                    </div>
                    <div className="rounded-lg border border-[#a8d8bf] bg-[#e2f3e9]/60 px-3 py-2">
                      <p className="flex items-center gap-1 text-xs font-semibold text-[#2f7357]">
                        <Lightbulb className="h-3.5 w-3.5" /> Constructive remedies
                      </p>
                      <ul className="mt-1 space-y-1">
                        {aa.blueprint.remedies.map((r, i) => (
                          <li key={i} className="text-[11px] leading-snug text-[#2f7357]">
                            • <span className="font-medium">{r.planet}:</span> {r.practice}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  <p className="text-[10px] leading-snug text-[#b39a76]">
                    Every card above is computed live from the birth data in the form (change it and Recalculate).
                    Interpretations follow BPHS / Jaimini / KP conventions translated into plain English for money
                    decisions — educational guidance, not financial advice.
                  </p>
                </>
              )}
            </TabsContent>

            {/* ── MONEY PLAN tab (T12②③) ── */}
            <TabsContent value="money" className="mt-3 flex flex-col gap-4">
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
                <div className="rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/80 p-3">
                  <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-[#5c4327]">
                    <Wallet className="h-3.5 w-3.5 text-[#c98a2e]" /> Recommended markets
                  </p>
                  {report.market_recommendations.allocation.map((a) => (
                    <div key={a.market} className="mb-1.5">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-[#5c4327]">{a.market}</span>
                        <span className="font-mono text-[#8a6a3a]">{a.weight_pct}%</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-[#f4ead2]">
                        <div className="h-full rounded-full bg-gradient-to-r from-[#8bb5a3] to-[#4a9a7e]" style={{ width: `${a.weight_pct}%` }} />
                      </div>
                      <p className="mt-0.5 text-[10px] text-[#b39a76]">driven by {a.driven_by}</p>
                    </div>
                  ))}
                </div>

                <div className="rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/80 p-3">
                  <p className="mb-1.5 text-xs font-semibold text-[#5c4327]">Favourable sectors</p>
                  <div className="flex flex-wrap gap-1">
                    {report.market_recommendations.sectors.map((s) => (
                      <Pill key={s.sector} tone={s.weight_pct >= 10 ? 'green' : 'gold'}>
                        {s.sector} · {s.weight_pct}%
                      </Pill>
                    ))}
                  </div>
                  <p className="mt-2 text-[10px] leading-snug text-[#b39a76]">
                    Sector weights come from your strongest grahas — Sun rules energy & PSU names,
                    Mercury rules IT & trade, Jupiter rules banking, and so on.
                  </p>
                </div>

                <div className="rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/80 p-3">
                  <p className="mb-1.5 text-xs font-semibold text-[#5c4327]">Matching strategies</p>
                  {report.market_recommendations.strategies.map((s, i) => (
                    <div key={s.key} className="mb-2 rounded-lg border border-[#f0e4cc] bg-[#fdf8ec] px-2 py-1.5">
                      <div className="flex items-center justify-between">
                        <p className="text-[11px] font-semibold text-[#5c4327]">
                          {i === 0 ? '★ ' : ''}{s.label}
                        </p>
                        <span className="font-mono text-[10px] text-[#8a6a3a]">{s.fit_score}%</span>
                      </div>
                      <p className="text-[10px] leading-snug text-[#7c5a2e]">{s.desc}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* income forecast (T12③) */}
              <div className="rounded-xl border border-[#eed9b4] bg-gradient-to-r from-[#fdf3dc] to-[#fbead0] p-4">
                <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-[#8a6a3a]">
                  <IndianRupee className="h-4 w-4" /> Income forecast · {report.income_forecast.strategy}
                </p>
                <div className="grid grid-cols-3 gap-2 text-center">
                  {([['Weekly', report.income_forecast.weekly], ['Monthly', report.income_forecast.monthly], ['Annual', report.income_forecast.annual]] as const).map(([label, band]) => (
                    <div key={label} className="rounded-lg bg-[#fffdf6]/90 px-2 py-2">
                      <p className="text-[10px] uppercase tracking-wide text-[#b39a76]">{label}</p>
                      <p className="font-mono text-sm font-semibold text-[#3f8a6e]">
                        £{band.low.toLocaleString()}–£{band.high.toLocaleString()}
                      </p>
                      <p className="text-[10px] text-[#97795a]">mid £{band.mid.toLocaleString()}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <Pill tone={report.income_forecast.target_feasible ? 'green' : 'rose'}>
                    £{report.income_forecast.target_weekly}/week target:{' '}
                    {report.income_forecast.target_feasible
                      ? 'feasible at this capital'
                      : `needs ~£${report.income_forecast.target_capital_needed.at_mid_yield.toLocaleString()} at mid yield`}
                  </Pill>
                  <Pill tone="lav">dasha factor ×{report.income_forecast.dasha_factor.toFixed(2)}</Pill>
                  <Pill>capital £{report.income_forecast.capital.toLocaleString()}</Pill>
                </div>
                <p className="mt-2 text-[11px] leading-relaxed text-[#8a6a3a]">{report.income_forecast.honesty}</p>
              </div>
            </TabsContent>

            {/* ── LIFETIME tab (T12④) ── */}
            <TabsContent value="lifetime" className="mt-3 flex flex-col gap-3">
              <div className="rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/80 p-3">
                <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-[#5c4327]">
                  <LineChartIcon className="h-3.5 w-3.5 text-[#c98a2e]" /> Wealth-accumulation index across life
                </p>
                <div className="h-52 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={lifeData} margin={{ top: 6, right: 10, bottom: 0, left: 0 }}>
                      <defs>
                        <linearGradient id="lifeFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#c9962e" stopOpacity={0.4} />
                          <stop offset="100%" stopColor="#c9962e" stopOpacity={0.04} />
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="age" tick={{ fontSize: 10, fill: '#97795a' }} unit="y" />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#97795a' }} width={28} />
                      <Tooltip
                        contentStyle={{ background: '#fffdf6', border: '1px solid #ecdec2', borderRadius: 8, fontSize: 11 }}
                        formatter={(v) => [`${v}`, 'wealth index']}
                        labelFormatter={(l) => `age ≈ ${Math.round(Number(l))}`}
                      />
                      <Area type="monotone" dataKey="index" stroke="#c9962e" strokeWidth={1.8} fill="url(#lifeFill)" isAnimationActive={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
                <p className="mt-1 text-center text-[10px] text-[#b39a76]">
                  Peaks in {report.lifetime_wealth.peak.lord} dasha · index is relative potential, not money
                </p>
              </div>
              <p className="font-display text-sm text-[#5c4327]">{report.lifetime_wealth.headline}</p>
              <div className="space-y-1.5">
                {report.lifetime_wealth.stages.map((s) => (
                  <div key={s.lord + s.start} className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6]/70 px-3 py-2">
                    <div className="flex flex-wrap items-center justify-between gap-1">
                      <p className="text-xs font-semibold text-[#5c4327]">
                        {s.lord} · age {s.age_from}–{s.age_to} ({s.start}–{s.end})
                      </p>
                      <div className="flex items-center gap-1.5">
                        <Pill tone="lav">{s.phase}</Pill>
                        <span className="font-mono text-[11px] text-[#8a6a3a]">{s.wealth_index}</span>
                      </div>
                    </div>
                    <p className="mt-0.5 text-[11px] leading-snug text-[#7c5a2e]">{s.note}</p>
                  </div>
                ))}
              </div>
            </TabsContent>

            {/* ── SYNTHESIS tab (T13) ── */}
            <TabsContent value="synthesis" className="mt-3 flex flex-col gap-3">
              <div className="rounded-xl border border-[#d9b46a] bg-gradient-to-r from-[#fdf3dc] via-[#fffdf6] to-[#f2f5ec] p-4">
                <p className="flex items-center gap-1.5 font-display text-sm font-semibold text-[#8a6a3a]">
                  <ScrollText className="h-4 w-4" /> Final synthesis · {symbolName || symbol}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-[#5c4327]">{report.synthesis.natal_headline}</p>
                {cur?.interpretation && (
                  <p className="mt-1 text-xs leading-relaxed text-[#5c4327]">
                    <span className="font-semibold">Dasha now:</span> {cur.interpretation.headline} — {cur.interpretation.detail}
                  </p>
                )}
              </div>

              {report.synthesis.transit_activations.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-semibold text-[#5c4327]">Today&apos;s transits touching your chart</p>
                  {report.synthesis.transit_activations.map((a, i) => (
                    <div key={i} className="mb-1 rounded border border-[#efe7f8] bg-[#f8f4fc] px-2.5 py-1.5 text-[11px] text-[#5c4327]">
                      {a.meaning} <span className="font-mono text-[10px] text-[#97795a]">({a.separation}°)</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                {report.synthesis.plan.map((p) => (
                  <div key={p.window} className="rounded-lg border border-[#f0e4cc] bg-[#fffdf6]/80 px-3 py-2">
                    <p className="text-xs font-semibold text-[#8a6a3a]">
                      <CalendarRange className="mr-1 inline h-3.5 w-3.5" />{p.window}
                    </p>
                    <p className="mt-0.5 text-[11px] leading-relaxed text-[#5c4327]">{p.action}</p>
                  </div>
                ))}
              </div>

              <Note text={report.synthesis.bottom_line} />
              <p className="text-[10px] leading-snug text-[#b39a76]">
                All income figures are modelled bands from historical strategy behaviour, scaled by dasha
                factors — not guarantees. Markets can and will differ.
              </p>
            </TabsContent>
          </Tabs>
        )}
      </CardContent>
    </Card>
  );
}
