'use client';

import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import type { PlanetaryResponse } from '@/lib/astro/types';
import { PLANET_META, SIGN_GLYPHS, fmtDeg } from './planet-meta';
import { NorthIndianChart, type KundaliPlanet } from './north-indian-chart';
import { LocateFixed, MapPin, Orbit, Star } from 'lucide-react';
import { jatakaApi, loadBirth, type JatakaPlaceV13, type PlanetaryResponseV13 } from '@/lib/astro/api-jataka';

// ── Sky Today observer: birth place (default) → browser location if already permitted → Ujjain ──
type Observer = { kind: 'birth' | 'geo' | 'ujjain' | 'city'; label: string; lat?: number; lon?: number; place?: string };
const UJJAIN: Observer = { kind: 'ujjain', label: 'Ujjain (traditional meridian)', place: 'Ujjain' };
const OBS_KEY = 'astrotrader.sky.observer.v1';
let birthObsCache: Observer | null = null;
function birthObserver(): Observer {
  if (!birthObsCache) {
    const b = loadBirth();
    birthObsCache = b.lat != null && b.lon != null
      ? { kind: 'birth', label: `Birth place · ${b.place.split(',')[0]}`, lat: b.lat, lon: b.lon, place: b.place }
      : { kind: 'birth', label: `Birth place · ${b.place.split(',')[0]}`, place: b.place };
  }
  return birthObsCache;
}
let savedObsCache: Observer | null | undefined;
function savedObserver(): Observer | null {
  if (savedObsCache === undefined) {
    try {
      const raw = window.localStorage.getItem(OBS_KEY);
      savedObsCache = raw ? (JSON.parse(raw) as Observer) : null;
    } catch {
      savedObsCache = null;
    }
  }
  return savedObsCache;
}
const noopSub = () => () => {};
const fmtLat = (v: number) => `${Math.abs(v).toFixed(2)}°${v >= 0 ? 'N' : 'S'}`;
const fmtLon = (v: number) => `${Math.abs(v).toFixed(2)}°${v >= 0 ? 'E' : 'W'}`;

function ZodiacWheel({ data, vedic }: { data: PlanetaryResponse; vedic: boolean }) {
  const CX = 170, CY = 170;
  const R_OUT = 160, R_IN = 126, R_PLANET = 104;

  const entries = Object.entries(data.planetary_positions).filter(([name]) => PLANET_META[name]);
  // de-collision: group planets within 7 degrees on the wheel ring
  const placed = entries
    .map(([name, p]) => ({ name, lon: p.longitude % 360 }))
    .sort((a, b) => a.lon - b.lon);
  for (let pass = 0; pass < 3; pass++) {
    for (let i = 0; i < placed.length; i++) {
      const a = placed[i];
      const b = placed[(i + 1) % placed.length];
      let gap = (b.lon - a.lon + 360) % 360;
      if (gap < 7 && gap > 0.01) {
        const push = (7 - gap) / 2;
        placed[i].lon = (a.lon - push + 360) % 360;
        placed[(i + 1) % placed.length].lon = (b.lon + push) % 360;
      }
    }
  }

  return (
    <div className="flex justify-center">
      <svg viewBox="0 0 340 340" className="h-[320px] w-[320px] sm:h-[340px] sm:w-[340px]" role="img" aria-label="Zodiac wheel">
        <defs>
          <radialGradient id="wheelCenter" cx="50%" cy="45%" r="60%">
            <stop offset="0%" stopColor="#fffdf6" />
            <stop offset="100%" stopColor="#f8eed6" />
          </radialGradient>
        </defs>
        <circle cx={CX} cy={CY} r={R_OUT} fill="url(#wheelCenter)" stroke="#d9b46a" strokeWidth="1.6" />
        <circle cx={CX} cy={CY} r={R_OUT - 3} fill="none" stroke="#e8d5ae" strokeWidth="0.8" />
        <circle cx={CX} cy={CY} r={R_IN} fill="none" stroke="#cfa96a" strokeWidth="0.75" strokeDasharray="3 3" />
        <circle cx={CX} cy={CY} r={R_PLANET - 22} fill="none" stroke="#e8d5ae" strokeWidth="0.75" />

        {/* sign sectors */}
        {SIGN_GLYPHS.map((glyph, i) => {
          const a0 = (i * 30 - 90 - 15) * (Math.PI / 180);
          const a1 = (i * 30 - 90 + 15) * (Math.PI / 180);
          const x0 = CX + R_OUT * Math.cos(a0), y0 = CY + R_OUT * Math.sin(a0);
          const x1 = CX + R_IN * Math.cos(a0), y1 = CY + R_IN * Math.sin(a0);
          const x2 = CX + R_IN * Math.cos(a1), y2 = CY + R_IN * Math.sin(a1);
          const x3 = CX + R_OUT * Math.cos(a1), y3 = CY + R_OUT * Math.sin(a1);
          const mid = (i * 30 - 90) * (Math.PI / 180);
          const gx = CX + (R_OUT + R_IN) / 2 * Math.cos(mid);
          const gy = CY + (R_OUT + R_IN) / 2 * Math.sin(mid);
          return (
            <g key={i}>
              <path
                d={`M ${x0} ${y0} L ${x1} ${y1} L ${x2} ${y2} L ${x3} ${y3} Z`}
                fill={i % 2 === 0 ? 'rgba(232, 144, 45, 0.08)' : 'rgba(232, 120, 138, 0.05)'}
                stroke="#dcc08a"
                strokeWidth="0.5"
              />
              <text
                x={gx} y={gy} textAnchor="middle" dominantBaseline="central"
                fill="#b0763a" fontSize="13"
              >
                {glyph}
              </text>
            </g>
          );
        })}

        {/* planets */}
        {placed.map(({ name, lon }) => {
          const meta = PLANET_META[name];
          const actual = entries.find(([n]) => n === name)?.[1];
          const a = (lon - 90) * (Math.PI / 180);
          const x = CX + R_PLANET * Math.cos(a);
          const y = CY + R_PLANET * Math.sin(a);
          return (
            <g key={name}>
              <circle cx={x} cy={y} r="12.5" fill="#fffdf6" stroke={meta.color} strokeWidth="1.2" opacity="0.95" />
              <text x={x} y={y} textAnchor="middle" dominantBaseline="central" fontSize="11" fill={meta.color}>
                {meta.glyph}
              </text>
              <text
                x={CX + (R_PLANET + 21) * Math.cos(a)}
                y={CY + (R_PLANET + 21) * Math.sin(a)}
                textAnchor="middle" dominantBaseline="central"
                fontSize="7.5" fill="#97795a"
              >
                {fmtDeg(actual?.degree_within_sign ?? 0).replace("'", '')}
              </text>
              {actual?.is_retrograde && name !== 'Ketu' && (
                <circle cx={x + 10} cy={y - 10} r="2" fill="#cf5b54" />
              )}
            </g>
          );
        })}

        <text x={CX} y={CY - 8} textAnchor="middle" fill="#97795a" fontSize="9" letterSpacing="2">
          {vedic ? 'SIDEREAL · LAHIRI' : 'TROPICAL'}
        </text>
        <text x={CX} y={CY + 10} textAnchor="middle" fill="#b0763a" fontSize="10" fontWeight="600">
          {data.date}
        </text>
      </svg>
    </div>
  );
}

function VedicKundali({ data }: { data: PlanetaryResponse }) {
  const positions = data.planetary_positions;
  const lagna = positions['Lagna'];
  const lagnaSign = lagna?.sign_number ?? 0;
  const planets: KundaliPlanet[] = Object.entries(positions)
    .filter(([name]) => name !== 'Lagna' && name !== 'Ascendant')
    .map(([name, p]) => ({
      name,
      signNumber: p.sign_number,
      degree: p.degree_within_sign,
      retrograde: p.is_retrograde && name !== 'Rahu' && name !== 'Ketu',
      house: p.house,
      dignity: p.dignity,
      nakshatra: p.nakshatra,
      pada: p.pada,
      combust: (p as { combust?: boolean }).combust,
    }));

  return (
    <div className="flex flex-col items-center gap-1">
      <NorthIndianChart
        lagnaSignNumber={lagnaSign}
        lagnaDegree={lagna?.degree_within_sign}
        planets={planets}
        size={352}
        title="Kundali · North Indian"
      />
    </div>
  );
}

export function PlanetaryCard({
  data,
  loading,
  vedic,
}: {
  data: PlanetaryResponse | null;
  loading: boolean;
  vedic: boolean;
}) {
  const [tab, setTab] = useState('chart');

  // observer location (client-only snapshot of saved choice / birth place)
  const initialObs = useSyncExternalStore(noopSub, () => savedObserver() ?? birthObserver(), () => null);
  const [obsOverride, setObsOverride] = useState<Observer | null>(null);
  const observer = obsOverride ?? initialObs;
  const [sky, setSky] = useState<{ key: string; data: PlanetaryResponseV13 } | null>(null);
  const [tick, setTick] = useState(0);
  const [geoErr, setGeoErr] = useState<string | null>(null);
  const [cityQ, setCityQ] = useState('');
  const [cities, setCities] = useState<JatakaPlaceV13[]>([]);
  const seq = useRef(0);
  const obsKey = observer ? `${observer.kind}|${observer.lat}|${observer.lon}|${observer.place}|${tick}` : '';

  const chooseObserver = (o: Observer) => {
    setObsOverride(o);
    try { window.localStorage.setItem(OBS_KEY, JSON.stringify(o)); } catch { /* ignore */ }
  };
  const requestMyLocation = () => {
    if (!('geolocation' in navigator)) { setGeoErr('Location not available in this browser'); return; }
    navigator.geolocation.getCurrentPosition(
      (pos) => { setGeoErr(null); chooseObserver({ kind: 'geo', label: 'My location', lat: pos.coords.latitude, lon: pos.coords.longitude }); },
      () => setGeoErr('Location permission denied — using the selected place'),
      { maximumAge: 600000, timeout: 8000 },
    );
  };

  // if the browser already granted geolocation and the user hasn't chosen otherwise, use it silently
  useEffect(() => {
    if (!vedic || obsOverride || savedObserver()) return;
    const perms = (navigator as Navigator & { permissions?: Permissions }).permissions;
    perms?.query({ name: 'geolocation' as PermissionName }).then((st) => {
      if (st.state === 'granted') {
        navigator.geolocation.getCurrentPosition((pos) =>
          setObsOverride({ kind: 'geo', label: 'My location', lat: pos.coords.latitude, lon: pos.coords.longitude }));
      }
    }).catch(() => { /* permissions API unsupported */ });
  }, [vedic, obsOverride]);

  // fetch "now" for the observer; refresh every 5 minutes
  useEffect(() => {
    if (!vedic || !observer) return;
    const s = ++seq.current;
    jatakaApi
      .skyNow({ lat: observer.lat, lon: observer.lon, place: observer.lat == null ? observer.place : observer.label })
      .then((d) => { if (s === seq.current) setSky({ key: obsKey, data: d }); })
      .catch(() => { /* keep the dashboard's copy */ });
    const t = setTimeout(() => setTick((x) => x + 1), 5 * 60 * 1000);
    return () => clearTimeout(t);
  }, [vedic, obsKey, observer]);

  useEffect(() => {
    if (cityQ.trim().length < 2) return;
    const t = setTimeout(() => {
      jatakaApi.places(cityQ).then((r) => setCities(r.places ?? [])).catch(() => setCities([]));
    }, 220);
    return () => clearTimeout(t);
  }, [cityQ]);

  const shown: PlanetaryResponseV13 | null = (vedic && sky?.data) || data;
  const obsInfo = (shown as PlanetaryResponseV13 | null)?.observer;
  const utc = obsInfo?.utc ? new Date(obsInfo.utc) : null;

  return (
    <Card className="vedic-card flex h-full flex-col">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            {vedic ? (
              <Star className="h-4 w-4 text-[#c98a2e]" />
            ) : (
              <Orbit className="h-4 w-4 text-[#c98a2e]" />
            )}
            <CardTitle className="font-display text-base tracking-wide">
              Sky Today — Real Positions
            </CardTitle>
          </div>
          {shown && vedic && (
            <Badge variant="outline" className="border-[#dcc08a] bg-[#f9efd8] text-[10px] text-[#8a6a3a]">
              Ayanamsa {shown.ayanamsa?.toFixed(4)}°
            </Badge>
          )}
        </div>
        <CardDescription className="text-[#97795a]">
          {vedic
            ? 'Sidereal (Lahiri) positions right now via Swiss Ephemeris, incl. Rahu/Ketu, with the Lagna rising over the place you choose'
            : 'Geocentric tropical longitudes via Swiss Ephemeris'}
        </CardDescription>
        {vedic && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <MapPin className="h-3.5 w-3.5 text-[#c98a2e]" />
            <select
              aria-label="Observer location for the Lagna"
              className="h-7 max-w-[60vw] rounded-md border border-[#ecdec2] bg-white px-1.5 text-[11px] text-[#5c4327]"
              value={observer?.kind === 'city' ? 'city' : observer?.kind ?? 'birth'}
              onChange={(e) => {
                const k = e.target.value;
                if (k === 'birth') chooseObserver(birthObserver());
                else if (k === 'ujjain') chooseObserver(UJJAIN);
                else if (k === 'geo') requestMyLocation();
              }}
            >
              <option value="birth">{birthObserver().label}</option>
              <option value="geo">My location (browser)</option>
              <option value="ujjain">Ujjain (traditional)</option>
              {observer?.kind === 'city' && <option value="city">{observer.label}</option>}
            </select>
            <div className="relative">
              <input
                value={cityQ}
                onChange={(e) => setCityQ(e.target.value)}
                placeholder="other city…"
                aria-label="Search another city"
                className="h-7 w-28 rounded-md border border-[#ecdec2] bg-white px-1.5 text-[11px] text-[#5c4327]"
              />
              {cityQ.trim().length >= 2 && cities.length > 0 && (
                <div className="warm-scroll absolute right-0 z-30 mt-1 max-h-44 w-56 overflow-y-auto rounded-md border border-[#ecdec2] bg-[#fffdf6] shadow-lg">
                  {cities.map((c) => (
                    <button key={c.name} type="button"
                            className="block w-full px-2 py-1 text-left text-[11px] text-[#5c4327] hover:bg-[#f9efd8]"
                            onClick={() => { chooseObserver({ kind: 'city', label: c.name.split(',')[0], lat: c.lat, lon: c.lon, place: c.name }); setCityQ(''); setCities([]); }}>
                      {c.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button type="button" onClick={requestMyLocation} title="Use my location"
                    className="rounded-md border border-[#ecdec2] bg-[#fffdf6] p-1 text-[#8a6a3a] hover:bg-[#f9efd8]">
              <LocateFixed className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
        {vedic && obsInfo && utc && (
          <p className="mt-1 text-[10px] leading-snug text-[#97795a]">
            Sky at <b>{utc.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</b> your time
            ({obsInfo.utc.slice(11, 16)} UTC, {obsInfo.utc.slice(0, 10)}) · Lagna rising over <b>{obsInfo.place}</b>{' '}
            ({fmtLat(obsInfo.lat)}, {fmtLon(obsInfo.lon)}) · {obsInfo.ayanamsa}, {obsInfo.node} node · refreshes every 5 min.
            The Lagna changes sign about every 2 hours and depends on place; the planets don’t.
            {geoErr && <span className="text-[#a34332]"> {geoErr}.</span>}
          </p>
        )}
      </CardHeader>
      <CardContent className="flex flex-1 flex-col">
        {loading && !shown ? (
          <div className="flex flex-1 items-center justify-center py-10">
            <Skeleton className="h-64 w-64 rounded-full bg-[#efdfbc]" />
          </div>
        ) : !shown ? (
          <div className="flex flex-1 items-center justify-center py-10 text-sm text-[#97795a]">
            Ephemeris data unavailable.
          </div>
        ) : (
          <Tabs value={tab} onValueChange={setTab} className="flex flex-1 flex-col">
            <TabsList className="mb-3 grid w-full grid-cols-3 bg-[#f4ead4]">
              <TabsTrigger value="chart" className="text-xs data-[state=active]:bg-[#fffdf6]">
                {vedic ? 'Kundali' : 'Wheel'}
              </TabsTrigger>
              <TabsTrigger value="positions" className="text-xs data-[state=active]:bg-[#fffdf6]">
                Positions
              </TabsTrigger>
              <TabsTrigger value="aspects" className="text-xs data-[state=active]:bg-[#fffdf6]">
                Aspects ({shown.aspects.length})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="chart" className="mt-0">
              {vedic ? <VedicKundali data={shown} /> : <ZodiacWheel data={shown} vedic={vedic} />}
            </TabsContent>

            <TabsContent value="positions" className="mt-0">
              <ScrollArea className="warm-scroll h-[300px] rounded-md border border-[#f0e4cc] bg-[#fffdf6]/60">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-[#f7ecd4]/95 backdrop-blur">
                    <tr className="text-left text-[#97795a]">
                      <th className="px-3 py-2 font-medium">Graha</th>
                      <th className="px-3 py-2 font-medium">Rasi</th>
                      <th className="px-3 py-2 font-medium">Degree</th>
                      {vedic && <th className="px-3 py-2 font-medium">Nakshatra</th>}
                      {vedic && <th className="px-3 py-2 font-medium">Pada</th>}
                      {vedic && <th className="px-3 py-2 font-medium text-right">Bhava</th>}
                      <th className="px-3 py-2 font-medium text-right">Motion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(shown.planetary_positions).map(([name, p]) => (
                      <tr key={name} className="border-t border-[#f0e4cc] hover:bg-[#f9f1de]/70">
                        <td className="px-3 py-2">
                          <span style={{ color: PLANET_META[name]?.color ?? '#7a6a58' }} className="mr-1.5">
                            {PLANET_META[name]?.glyph ?? '•'}
                          </span>
                          <span className="font-medium text-[#5c4327]">{name}</span>
                        </td>
                        <td className="px-3 py-2 text-[#7c5a2e]">{p.sign}</td>
                        <td className="px-3 py-2 font-mono text-[#7c5a2e]">{fmtDeg(p.degree_within_sign)}</td>
                        {vedic && <td className="px-3 py-2 text-[#97795a]">{p.nakshatra ?? '—'}</td>}
                        {vedic && <td className="px-3 py-2 text-[#97795a]">{p.pada ?? '—'}</td>}
                        {vedic && (
                          <td className="px-3 py-2 text-right font-mono text-[#b0763a]">{p.house ?? '—'}</td>
                        )}
                        <td className="px-3 py-2 text-right">
                          {p.is_retrograde ? (
                            <span className="text-[#cf5b54]">℞ retro</span>
                          ) : (
                            <span className="text-[#4a9a7e]">direct</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="aspects" className="mt-0">
              <ScrollArea className="warm-scroll h-[300px] rounded-md border border-[#f0e4cc] bg-[#fffdf6]/60 p-3">
                {shown.aspects.length === 0 ? (
                  <p className="py-8 text-center text-xs text-[#97795a]">
                    No major aspects within orb today.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {shown.aspects
                      .slice()
                      .sort((a, b) => a.orb_used - b.orb_used)
                      .map((a, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between rounded-md border border-[#f0e4cc] bg-[#fdf8ec]/80 px-3 py-2"
                        >
                          <div className="flex items-center gap-2 text-xs">
                            <span style={{ color: PLANET_META[a.planet1]?.color }} className="font-medium">
                              {a.planet1}
                            </span>
                            <span className="rounded bg-[#f7e8cd] px-1.5 py-0.5 font-mono text-[10px] text-[#a8701a]">
                              {a.aspect} {Math.round(a.angle_exact)}°
                            </span>
                            <span style={{ color: PLANET_META[a.planet2]?.color }} className="font-medium">
                              {a.planet2}
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-[10px] text-[#97795a]">
                              orb {a.orb_used.toFixed(2)}°
                            </span>
                            <div className="h-1.5 w-16 overflow-hidden rounded-full bg-[#efdfbc]">
                              <div
                                className="h-full rounded-full bg-gradient-to-r from-[#e8a04c] to-[#d98324]"
                                style={{ width: `${Math.round(a.strength * 100)}%` }}
                              />
                            </div>
                          </div>
                        </div>
                      ))}
                  </div>
                )}
              </ScrollArea>
            </TabsContent>
          </Tabs>
        )}
      </CardContent>
    </Card>
  );
}
