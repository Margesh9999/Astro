'use client';

import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  DEFAULT_BIRTH, DEFAULT_MONEY, jatakaApi, loadBirth, loadMoney, saveBirth, saveMoney,
  type BirthInput, type JatakaReportV13, type MoneyInputs,
} from '@/lib/astro/api-jataka';
import { NorthIndianChart, type KundaliPlanet } from './north-indian-chart';
import { PLANET_META, PLANET_GUIDES, SIGNS } from './planet-meta';
import { Note, Pill } from './jataka-ui';
import { JatakaForm } from './jataka-form';
import { JatakaDashaTab } from './jataka-dasha-tab';
import { JatakaAnalysisTab } from './jataka-analysis-tab';
import { JatakaPlanTab } from './jataka-plan-tab';
import { JatakaLifetimeTab } from './jataka-lifetime-tab';
import { JatakaStockTab } from './jataka-stock-tab';
import { Sparkles, CalendarRange, ScrollText, Lightbulb, AlertTriangle, Gem } from 'lucide-react';

const GRAHA_ORDER = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Rahu', 'Ketu', 'Lagna'];
const TAB_KEY = 'astrotrader.jataka.tab.v1';
const TRIGGER = 'text-xs data-[state=active]:bg-[#fffdf6]';

// ── one-time localStorage snapshot (stable reference for useSyncExternalStore) ──
type Stored = { birth: BirthInput; money: MoneyInputs; tab: string | null };
let storedCache: Stored | null = null;
function readStored(): Stored {
  if (!storedCache) {
    let tab: string | null = null;
    try { tab = window.localStorage.getItem(TAB_KEY); } catch { /* storage blocked */ }
    storedCache = { birth: loadBirth(), money: loadMoney(), tab };
  }
  return storedCache;
}
const noopSubscribe = () => () => {};

/* ═════════════ Janma Kundli & Wealth Blueprint — configurable, default native Margesh ═════════════ */
export function JatakaCard({ symbol, symbolName }: { symbol: string; symbolName?: string }) {
  // last-used birth details / tab are restored from localStorage (client only, no effect needed)
  const stored = useSyncExternalStore(noopSubscribe, readStored, () => null);
  const [override, setOverride] = useState<{ birth: BirthInput; money: MoneyInputs; nonce: number } | null>(null);
  const [tabOverride, setTabOverride] = useState<string | null>(null);
  const birth = override?.birth ?? stored?.birth ?? DEFAULT_BIRTH;
  const money = override?.money ?? stored?.money ?? DEFAULT_MONEY;
  const tab = tabOverride ?? stored?.tab ?? 'kundali';
  const ready = stored !== null;
  const reqKey = `${symbol}|${JSON.stringify(birth)}|${JSON.stringify(money)}|${override?.nonce ?? 0}`;

  const [res, setRes] = useState<{ key: string; report: JatakaReportV13 | null; error: string | null } | null>(null);
  const [lastGood, setLastGood] = useState<JatakaReportV13 | null>(null);
  const seqRef = useRef(0);

  useEffect(() => {
    if (!ready) return;
    const seq = ++seqRef.current;
    jatakaApi
      .report(symbol, birth, money)
      .then((r) => {
        if (seq !== seqRef.current) return;
        setRes({ key: reqKey, report: r, error: null });
        setLastGood(r);
      })
      .catch((e) => {
        if (seq !== seqRef.current) return;
        setRes({ key: reqKey, report: null, error: String((e as Error)?.message ?? e) });
      });
  }, [ready, reqKey, symbol, birth, money]);

  const loading = res?.key !== reqKey;
  const error = !loading ? res?.error ?? null : null;
  const report = (!loading ? res?.report : null) ?? lastGood;

  const apply = (b: BirthInput, m: MoneyInputs) => {
    setOverride((o) => ({ birth: b, money: m, nonce: (o?.nonce ?? 0) + 1 }));
    saveBirth(b);
    saveMoney(m);
  };
  const onTab = (t: string) => {
    setTabOverride(t);
    try { window.localStorage.setItem(TAB_KEY, t); } catch { /* ignore */ }
  };

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
        combust: report.positions[n].combust,
      }))
    : [];

  const cur = report?.current_dasha;
  const aa = report?.astro_analysis;
  const pn = report?.planetary_notes ?? {};
  const st = report?.settings;
  const zodiacLabel = st?.ayanamsa === 'tropical' ? 'Tropical' : `Vedic · ${report?.ayanamsa_mode?.split(' ')[0] ?? 'Lahiri'}`;

  return (
    <Card className="vedic-card">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-[#c98a2e]" />
            <CardTitle className="font-display text-base tracking-wide">
              Janma Kundli &amp; Wealth Blueprint — <span className="text-[#a5698f]">{report?.birth.name || birth.name || 'Margesh'}</span>
            </CardTitle>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Pill>{zodiacLabel}{report?.ayanamsa ? ` · ${report.ayanamsa.toFixed(2)}°` : ''} · {st?.node ?? 'mean'} node</Pill>
            {cur?.mahadasha && <Pill tone="lav">MD {cur.mahadasha} / AD {cur.antardasha} / PD {cur.pratyantardasha}</Pill>}
            {aa?.yogini?.current && <Pill tone="green">Yogini {aa.yogini.current.yogini}</Pill>}
          </div>
        </div>
        <CardDescription className="text-[#97795a]">
          Your birth chart is included by default (Margesh · 23 Apr 1994 · 06:45 IST · Vallabh Vidyanagar) and fully
          configurable below — place-aware Lagna, DST-correct time zones, drikpanchang-standard Vimshottari, wealth
          analysis, and a data-backed fit with {symbolName || symbol}.
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <JatakaForm key={reqKey} birth={birth} money={money} onApply={apply} loading={loading} resolved={report?.birth ?? null} />

        {loading && !report && <Skeleton className="h-64 w-full bg-[#efdfbc]" />}
        {error && (
          <div className="rounded-md border border-[#eecfc7] bg-[#fbeae4] px-3 py-2 text-xs text-[#a14d3c]">
            Jataka engine unavailable — {error}
          </div>
        )}

        {report && (
          <Tabs value={tab} onValueChange={onTab} className="mt-0">
            <TabsList className="h-auto flex-wrap justify-start bg-[#f4e8cf]">
              <TabsTrigger value="kundali" className={TRIGGER}>Kundali</TabsTrigger>
              <TabsTrigger value="dasha" className={TRIGGER}>Dasha Tree</TabsTrigger>
              <TabsTrigger value="analysis" className={TRIGGER}>Astro Analysis</TabsTrigger>
              <TabsTrigger value="money" className={TRIGGER}>Markets &amp; Income</TabsTrigger>
              <TabsTrigger value="lifetime" className={TRIGGER}>Lifetime Wealth</TabsTrigger>
              <TabsTrigger value="stock" className={TRIGGER}>Stock × Kundli</TabsTrigger>
              <TabsTrigger value="blueprint" className={TRIGGER}>✦ Blueprint</TabsTrigger>
              <TabsTrigger value="synthesis" className={TRIGGER}>Synthesis</TabsTrigger>
            </TabsList>

            {/* ── KUNDALI ── */}
            <TabsContent value="kundali" className="mt-3">
              {report.verdict && (
                <div className="mb-3 rounded-lg border border-[#e4d0b4] bg-gradient-to-r from-[#fdf3dc] via-[#f9e9d2] to-[#f6e3c4] p-3">
                  <p className="font-display text-[10px] uppercase tracking-[0.18em] text-[#a8701a]">
                    Trading suitability verdict
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-[#6b4f2e]">
                    {report.verdict.plain}
                  </p>
                </div>
              )}
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <div className="flex flex-col items-center rounded-xl border border-[#f0e4cc] bg-[#fffdf6]/70 p-3">
                  <NorthIndianChart
                    lagnaSignNumber={lagnaSign}
                    lagnaDegree={report.positions.Lagna?.degree_within_sign}
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
                              {p.combust && <span className="ml-0.5 font-bold text-[#e07b2a]" title="combust">c</span>}
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
            {/* ── DASHA ── */}
            <TabsContent value="dasha" className="mt-3"><JatakaDashaTab report={report} /></TabsContent>

            {/* ── ASTRO ANALYSIS ── */}
            <TabsContent value="analysis" className="mt-3"><JatakaAnalysisTab report={report} /></TabsContent>

            {/* ── MARKETS, SECTORS, STRATEGIES & INCOME ── */}
            <TabsContent value="money" className="mt-3"><JatakaPlanTab plan={report.plan} /></TabsContent>

            {/* ── LIFETIME ── */}
            <TabsContent value="lifetime" className="mt-3">
              <JatakaLifetimeTab plan={report.plan} stages={report.lifetime_wealth.stages} headline={report.lifetime_wealth.headline} />
            </TabsContent>

            {/* ── STOCK × KUNDLI (lazy: only fetched while the tab is open) ── */}
            <TabsContent value="stock" className="mt-3">
              {tab === 'stock' && <JatakaStockTab symbol={symbol} symbolName={symbolName} birth={birth} />}
            </TabsContent>

            {/* ── BLUEPRINT ── */}
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
                  <p className="text-[10px] leading-snug text-[#b39a76]">
                    The deep concept pack (vargas, Jaimini, shadbala, ashtakvarga, KP, Yogini…) lives in the Astro
                    Analysis tab. Educational guidance, not financial advice.
                  </p>
                </>
              )}
            </TabsContent>

            {/* ── SYNTHESIS ── */}
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
