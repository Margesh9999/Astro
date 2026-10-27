'use client';

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import type { PlanetaryResponse } from '@/lib/astro/types';
import { PLANET_META, SIGN_GLYPHS, fmtDeg } from './planet-meta';
import { NorthIndianChart, type KundaliPlanet } from './north-indian-chart';
import { Orbit, Star } from 'lucide-react';

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
    }));

  return (
    <div className="flex flex-col items-center gap-1">
      <NorthIndianChart
        lagnaSignNumber={lagnaSign}
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
          {data && vedic && (
            <Badge variant="outline" className="border-[#dcc08a] bg-[#f9efd8] text-[10px] text-[#8a6a3a]">
              Ayanamsa {data.ayanamsa?.toFixed(4)}°
            </Badge>
          )}
        </div>
        <CardDescription className="text-[#97795a]">
          {vedic
            ? 'Sidereal longitudes via Swiss Ephemeris + Lahiri ayanamsa, incl. Rahu/Ketu & the day’s Lagna (noon · Ujjain meridian)'
            : 'Geocentric tropical longitudes via Swiss Ephemeris'}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col">
        {loading && !data ? (
          <div className="flex flex-1 items-center justify-center py-10">
            <Skeleton className="h-64 w-64 rounded-full bg-[#efdfbc]" />
          </div>
        ) : !data ? (
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
                Aspects ({data.aspects.length})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="chart" className="mt-0">
              {vedic ? <VedicKundali data={data} /> : <ZodiacWheel data={data} vedic={vedic} />}
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
                    {Object.entries(data.planetary_positions).map(([name, p]) => (
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
                {data.aspects.length === 0 ? (
                  <p className="py-8 text-center text-xs text-[#97795a]">
                    No major aspects within orb today.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {data.aspects
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
