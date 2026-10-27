'use client';

import { useState } from 'react';
import { PLANET_META, SIGNS, fmtDeg, PLANET_GUIDES, HOUSE_GUIDES, DIGNITY_GUIDES } from './planet-meta';

export interface KundaliPlanet {
  name: string;
  /** 0-11, Aries = 0 */
  signNumber: number;
  /** degrees within the sign */
  degree: number;
  retrograde?: boolean;
  /** optional T6 popup context */
  house?: number;
  dignity?: string;
  nakshatra?: string;
  pada?: number;
}

interface HouseGeom {
  /** polygon vertices (SVG points string) */
  poly: string;
  /** anchor for the rasi number */
  num: [number, number];
  /** anchor for the planet cluster */
  planet: [number, number];
}

/*
 * North Indian kundali geometry — fixed houses, rotating signs.
 * Square 10..390, midpoints T(200,10) R(390,200) B(200,390) L(10,200),
 * centre C(200,200), diagonal/diamond crossings at (105,105),(295,105),
 * (105,295),(295,295).
 *
 *   H2  H1  H12
 *  H3  ╱╲  H11
 *  H4 ╱  ╲ H10      (H1 top diamond, H4 left diamond,
 *  H5 ╲  ╱ H 9       H7 bottom diamond, H10 right diamond)
 *   H6  H7  H8
 */
const HOUSES: HouseGeom[] = [
  // H1 — top centre diamond (Lagna)
  { poly: '200,10 105,105 200,200 295,105', num: [200, 180], planet: [200, 92] },
  // H2 — top-left triangle
  { poly: '10,10 200,10 105,105', num: [105, 90], planet: [105, 44] },
  // H3 — left-top triangle
  { poly: '10,10 105,105 10,200', num: [88, 105], planet: [44, 105] },
  // H4 — left centre diamond
  { poly: '10,200 105,105 200,200 105,295', num: [182, 200], planet: [108, 200] },
  // H5 — left-bottom triangle
  { poly: '10,200 105,295 10,390', num: [88, 295], planet: [44, 295] },
  // H6 — bottom-left triangle
  { poly: '10,390 105,295 200,390', num: [105, 314], planet: [105, 358] },
  // H7 — bottom centre diamond
  { poly: '200,390 105,295 200,200 295,295', num: [200, 224], planet: [200, 310] },
  // H8 — bottom-right triangle
  { poly: '200,390 295,295 390,390', num: [295, 314], planet: [295, 358] },
  // H9 — right-bottom triangle
  { poly: '390,390 295,295 390,200', num: [312, 295], planet: [356, 295] },
  // H10 — right centre diamond
  { poly: '390,200 295,105 200,200 295,295', num: [218, 200], planet: [292, 200] },
  // H11 — right-top triangle
  { poly: '390,200 295,105 390,10', num: [312, 105], planet: [356, 105] },
  // H12 — top-right triangle
  { poly: '390,10 200,10 295,105', num: [295, 90], planet: [295, 44] },
];

export function NorthIndianChart({
  lagnaSignNumber,
  planets,
  size = 360,
  title,
}: {
  lagnaSignNumber: number;
  planets: KundaliPlanet[];
  size?: number;
  title?: string;
}) {
  const [popup, setPopup] = useState<KundaliPlanet | null>(null);

  // house (1..12) -> rasi number (1..12)
  const houseSign = (h: number) => (lagnaSignNumber + h - 1) % 12;

  // bucket planets by house
  const byHouse: Record<number, KundaliPlanet[]> = {};
  for (const p of planets) {
    const h = ((p.signNumber - lagnaSignNumber + 12) % 12) + 1;
    (byHouse[h] ??= []).push(p);
  }
  for (const h of Object.keys(byHouse)) {
    byHouse[Number(h)].sort((a, b) => a.degree - b.degree);
  }

  const CX = 200, CY = 200;

  return (
    <div className="relative flex flex-col items-center">
      <svg
        viewBox="0 0 400 400"
        width={size}
        height={size}
        role="img"
        aria-label={title ?? 'North Indian kundali chart'}
        className="max-w-full"
      >
        <defs>
          <linearGradient id="kundaliFrame" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#c9962e" />
            <stop offset="45%" stopColor="#8f6212" />
            <stop offset="100%" stopColor="#d9a94e" />
          </linearGradient>
          <radialGradient id="kundaliBg" cx="50%" cy="42%" r="75%">
            <stop offset="0%" stopColor="#fffdf6" />
            <stop offset="100%" stopColor="#faf1dc" />
          </radialGradient>
        </defs>

        {/* soft ivory field + double gold frame */}
        <rect x="4" y="4" width="392" height="392" rx="6" fill="url(#kundaliBg)" stroke="url(#kundaliFrame)" strokeWidth="2.5" />
        <rect x="10" y="10" width="380" height="380" fill="none" stroke="#dcc08a" strokeWidth="0.8" />

        {/* Lagna house wash */}
        <polygon points={HOUSES[0].poly} fill="rgba(232, 145, 45, 0.12)" />

        {/* faint pastel wash on the four kendra diamonds */}
        <polygon points={HOUSES[3].poly} fill="rgba(232, 120, 138, 0.07)" />
        <polygon points={HOUSES[6].poly} fill="rgba(69, 167, 154, 0.07)" />
        <polygon points={HOUSES[9].poly} fill="rgba(155, 138, 196, 0.07)" />

        {/* diamond + diagonals */}
        <polygon points="200,10 390,200 200,390 10,200" className="kundali-line" />
        <line x1="10" y1="10" x2="390" y2="390" className="kundali-line" />
        <line x1="390" y1="10" x2="10" y2="390" className="kundali-line" />
        {/* inner frame on the diamond vertices */}
        <polygon points="200,10 390,200 200,390 10,200" fill="none" stroke="#dcc08a" strokeWidth="0.6" transform="translate(200 200) scale(0.985) translate(-200 -200)" />

        {/* centre medallion */}
        <circle cx={CX} cy={CY} r="5.5" fill="#fffdf6" stroke="#c9962e" strokeWidth="1.4" />
        <circle cx={CX} cy={CY} r="1.6" fill="#c9962e" />

        {/* houses: rasi number + planets */}
        {HOUSES.map((geom, i) => {
          const house = i + 1;
          const signNum = houseSign(house) + 1;
          const list = byHouse[house] ?? [];
          // cluster layout: 2 columns × up to 3 rows
          const cols = list.length <= 1 ? 1 : 2;
          const rows = Math.ceil(list.length / cols);
          const dx = 42, dy = 34;
          const [ax, ay] = geom.planet;
          const x0 = ax - ((cols - 1) * dx) / 2;
          const y0 = ay - ((rows - 1) * dy) / 2;

          return (
            <g key={house}>
              <text
                x={geom.num[0]}
                y={geom.num[1]}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize="14"
                className="kundali-sign-num"
                opacity="0.9"
              >
                {signNum}
              </text>
              {list.map((p, idx) => {
                const col = idx % cols;
                const row = Math.floor(idx / cols);
                const px = x0 + col * dx;
                const py = y0 + row * dy;
                const meta = PLANET_META[p.name] ?? { glyph: '•', color: '#7a6a58' };
                return (
                  <g
                    key={p.name}
                    className="cursor-pointer"
                    onClick={() => setPopup(popup?.name === p.name ? null : p)}
                    onMouseEnter={() => setPopup(p)}
                    onMouseLeave={() => setPopup((cur) => (cur?.name === p.name ? null : cur))}
                  >
                    {/* invisible hit area so hover/click is easy */}
                    <circle cx={px} cy={py} r="17" fill="transparent" />
                    <text
                      x={px}
                      y={py}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fontSize="17"
                      fill={meta.color}
                      fontWeight="600"
                      style={{ pointerEvents: 'none' }}
                    >
                      {meta.glyph}
                    </text>
                    <text
                      x={px}
                      y={py + 13}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fontSize="8"
                      className="kundali-degree"
                      style={{ pointerEvents: 'none' }}
                    >
                      {fmtDeg(p.degree, false)}
                      {p.retrograde && (
                        <tspan fill="#cf5b54" fontWeight="700">℞</tspan>
                      )}
                    </text>
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>

      {/* T6: plain-English popup — tap/click any planet glyph to decode it */}
      {popup && (
        <div
          className="pointer-events-none absolute left-1/2 top-2 z-20 w-[92%] max-w-[340px] -translate-x-1/2 rounded-xl border border-[#e3cfa4] bg-[#fffdf6]/97 p-3 text-left shadow-[0_8px_28px_rgba(122,86,26,0.22)] backdrop-blur"
          role="status"
        >
          <div className="flex items-center justify-between gap-2">
            <p className="font-display text-sm font-semibold" style={{ color: PLANET_META[popup.name]?.color ?? '#7c5a2e' }}>
              {PLANET_META[popup.name]?.glyph} {popup.name}
            </p>
            <span className="rounded bg-[#f7ecd4] px-1.5 py-0.5 font-mono text-[10px] text-[#97795a]">
              {SIGNS[popup.signNumber]} {fmtDeg(popup.degree)}
              {popup.retrograde ? ' ℞' : ''}
            </span>
          </div>
          <p className="mt-1 text-[11px] leading-snug text-[#5c4327]">
            {PLANET_GUIDES[popup.name]?.meaning ?? 'A graha of the Vedic sky.'}
          </p>
          <div className="mt-1.5 space-y-1 text-[11px] leading-snug text-[#7c5a2e]">
            {popup.house !== undefined && (
              <p>
                <span className="font-semibold">House {popup.house}:</span> {HOUSE_GUIDES[popup.house]}
              </p>
            )}
            {popup.nakshatra && (
              <p>
                <span className="font-semibold">Nakshatra:</span> {popup.nakshatra}
                {popup.pada ? ` · pada ${popup.pada}` : ''}
              </p>
            )}
            {popup.dignity && (
              <p>
                <span className="font-semibold">Dignity:</span> {popup.dignity} —{' '}
                {DIGNITY_GUIDES[popup.dignity] ?? 'classical strength assessment'}
              </p>
            )}
            <p className="rounded bg-[#fdf8ec] px-1.5 py-1 text-[#8a6a3a]">
              <span className="font-semibold">Markets:</span> {PLANET_GUIDES[popup.name]?.market}
            </p>
            <p className="rounded bg-[#f2f5ec] px-1.5 py-1 text-[#5f7a42]">
              <span className="font-semibold">Action:</span> {PLANET_GUIDES[popup.name]?.action}
            </p>
          </div>
          <p className="mt-1.5 text-center text-[9px] uppercase tracking-widest text-[#b39a76]">
            tap another glyph or outside to dismiss
          </p>
        </div>
      )}

      {title && (
        <p className="mt-1 text-center font-display text-[11px] uppercase tracking-[0.18em] text-[#97795a]">
          {title}
        </p>
      )}
      {planets.length > 0 && (
        <p className="mt-0.5 text-center text-[10px] text-[#b39a76]">
          Lagna · {SIGNS[lagnaSignNumber]} — tap any planet glyph for its meaning
        </p>
      )}
    </div>
  );
}
