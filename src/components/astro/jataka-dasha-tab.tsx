'use client';

import type { JatakaReportV13, DashaPeriodNow } from '@/lib/astro/api-jataka';
import { Badge } from '@/components/ui/badge';
import { PLANET_META } from './planet-meta';
import { Note, Pill } from './jataka-ui';
import { Hourglass } from 'lucide-react';

const NAKS = [
  'Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra', 'Punarvasu', 'Pushya', 'Ashlesha',
  'Magha', 'Purva Phalguni', 'Uttara Phalguni', 'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha',
  'Mula', 'Purva Ashadha', 'Uttara Ashadha', 'Shravana', 'Dhanishta', 'Shatabhisha', 'Purva Bhadrapada',
  'Uttara Bhadrapada', 'Revati',
];

/** dd-mm-yyyy → comparable yyyymmdd number */
const key = (d: string) => {
  const [dd, mm, yy] = d.split('-');
  return Number(`${yy}${mm}${dd}`);
};
const short = (d: string) => `${d.slice(3, 5)}/${d.slice(8, 10)}`; // mm/yy
const Glyph = ({ lord }: { lord: string }) => (
  <span className="mr-1 font-semibold" style={{ color: PLANET_META[lord]?.color }}>{PLANET_META[lord]?.glyph}</span>
);

function NowCard({ level, p, tone }: { level: string; p: DashaPeriodNow | null; tone: string }) {
  if (!p) return null;
  return (
    <div className={`rounded-lg border px-3 py-2 ${tone}`}>
      <p className="text-[10px] uppercase tracking-wide text-[#97795a]">{level}</p>
      <p className="text-sm font-semibold text-[#5c4327]"><Glyph lord={p.lord} />{p.lord}</p>
      <p className="font-mono text-[10px] text-[#97795a]">{p.start} → {p.end}</p>
      <p className="mt-1 text-[11px] leading-snug text-[#5c4327]">{p.meaning}</p>
    </div>
  );
}

export function JatakaDashaTab({ report }: { report: JatakaReportV13 }) {
  const cur = report.current_dasha;
  const t = cur.trading;
  const dt = report.dasha_tree;
  const today = (() => {
    const d = new Date();
    return Number(`${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`);
  })();
  const inside = (s: string, e: string) => key(s) <= today && today < key(e);
  const moonNak = NAKS[dt.moon_nakshatra_index] ?? `#${dt.moon_nakshatra_index + 1}`;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone="lav">Moon nakshatra {moonNak} · pada {dt.pada}</Pill>
        <Pill>Birth dasha {dt.first_lord}: {dt.elapsed_years_at_birth?.toFixed(2)}y elapsed · {dt.balance_years.toFixed(2)}y balance</Pill>
        <Pill tone="green">Year = {dt.year_days} days</Pill>
      </div>

      <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
        <NowCard level="Mahadasha (years)" p={t.mahadasha} tone="border-[#d9b46a] bg-[#fdf3dc]" />
        <NowCard level="Antardasha (months–years)" p={t.antardasha} tone="border-[#e8b3a8] bg-[#fbe7e0]/70" />
        <NowCard level="Pratyantardasha (weeks)" p={t.pratyantardasha} tone="border-[#cbb8dd] bg-[#efe7f8]/70" />
      </div>
      {cur.interpretation && <Note text={cur.interpretation.detail} />}

      <div className="space-y-2">
        {dt.mahadashas.map((md) => {
          const mdNow = inside(md.start, md.end);
          return (
            <details key={md.lord + md.start} open={mdNow}
                     className={`rounded-lg border px-3 py-2 ${mdNow ? 'border-[#d9b46a] bg-[#fdf3dc]' : 'border-[#f0e4cc] bg-[#fffdf6]/70'}`}>
              <summary className="cursor-pointer list-none">
                <span className="font-display text-sm font-semibold text-[#5c4327]"><Glyph lord={md.lord} />{md.lord} Mahadasha</span>
                <span className="ml-2 font-mono text-[11px] text-[#97795a]">{md.start} → {md.end} · {md.years}y</span>
                {mdNow && <Badge className="ml-2 bg-[#e8a04c] text-[10px] text-white">current</Badge>}
              </summary>
              <div className="mt-2 space-y-1">
                {md.antardashas.map((ad) => {
                  const adNow = inside(ad.start, ad.end);
                  return (
                    <details key={ad.lord + ad.start} open={adNow}
                             className={`rounded border px-2 py-1 text-[11px] ${adNow ? 'border-[#c9553f] bg-[#fbe7e0]' : 'border-[#f0e4cc] bg-[#fdf8ec]'}`}>
                      <summary className="cursor-pointer list-none">
                        <span className={`text-[#5c4327] ${adNow ? 'font-semibold' : ''}`}><Glyph lord={ad.lord} />{md.lord}/{ad.lord}</span>
                        <span className="ml-1.5 font-mono text-[10px] text-[#97795a]">{ad.start} → {ad.end}</span>
                        {ad.balance_at_birth && <span className="ml-1 text-[9px] text-[#a8701a]">(running at birth)</span>}
                        {adNow && <span className="ml-1.5 rounded bg-[#c9553f] px-1 text-[9px] text-white">now</span>}
                        <span className="ml-1 text-[9px] text-[#c98a2e]">▾ {ad.pratyantardashas.length} PDs</span>
                      </summary>
                      <div className="mt-1 grid grid-cols-2 gap-1 sm:grid-cols-3 lg:grid-cols-5">
                        {ad.pratyantardashas.map((pd) => {
                          const pdNow = inside(pd.start, pd.end);
                          return (
                            <div key={pd.lord + pd.start}
                                 className={`rounded border px-1.5 py-0.5 text-[10px] ${pdNow ? 'border-[#6b4e93] bg-[#efe7f8] font-semibold' : 'border-[#f4ead2] bg-[#fffdf6]'}`}>
                              <Glyph lord={pd.lord} />{pd.lord}
                              <span className="ml-1 font-mono text-[9px] text-[#97795a]">{pd.start.slice(0, 5)}/{pd.start.slice(8)}–{short(pd.end)}</span>
                            </div>
                          );
                        })}
                      </div>
                    </details>
                  );
                })}
              </div>
            </details>
          );
        })}
      </div>
      <p className="flex items-start gap-1 text-[10px] leading-snug text-[#b39a76]">
        <Hourglass className="mt-0.5 h-3 w-3 flex-shrink-0" />
        Drikpanchang convention: the birth mahadasha ({dt.first_lord}) is laid out at its full length from its virtual
        pre-birth start (Moon’s elapsed fraction of {moonNak}) and clipped at birth, so you are born inside a later
        antardasha, not {dt.first_lord}/{dt.first_lord}. Every later mahadasha starts with its own lord; the nine
        antardashas (and nine pratyantardashas inside each) sum exactly to the parent. Dates are in your birth time zone.
      </p>
    </div>
  );
}
