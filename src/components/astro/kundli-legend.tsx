'use client';

import { Info } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { HOUSE_GUIDES, PLANET_GUIDES, PLANET_META, SIGNS, SIGN_GLYPHS } from './planet-meta';

/** Money/market angle per house, in plain words (complements HOUSE_GUIDES' life themes). */
export const HOUSE_MONEY: Record<number, string> = {
  1: 'your trading temperament & health',
  2: 'savings, bank balance, value investing',
  3: 'courage for short-term trades, effort',
  4: 'property, vehicles, peace of mind',
  5: 'speculation — trading, options, bets',
  6: 'debt, competition, daily grind',
  7: 'partners, clients, deal-making',
  8: "sudden gains/losses, leverage, others' money",
  9: 'luck, long-term investing, mentors',
  10: 'career income, reputation',
  11: 'profits, income streams, networks',
  12: 'expenses, losses, foreign markets',
};

export const DIGNITY_COLOURS: { key: string; colour: string; label: string; plain: string }[] = [
  { key: 'strong', colour: '#3f9a72', label: 'Exalted / own sign / moolatrikona', plain: 'planet is at full strength — its themes deliver' },
  { key: 'ok', colour: '#d0a040', label: 'Friendly / neutral sign', plain: 'average strength — results depend on dasha & transits' },
  { key: 'weak', colour: '#c9553f', label: 'Debilitated', plain: 'weakened — results come with effort; double-check its sectors' },
];

export function dignityColour(dignity?: string) {
  if (!dignity) return null;
  if (['exalted', 'own sign', 'moolatrikona'].includes(dignity)) return DIGNITY_COLOURS[0].colour;
  if (dignity === 'debilitated') return DIGNITY_COLOURS[2].colour;
  if (dignity === 'reference') return null;
  return DIGNITY_COLOURS[1].colour;
}

const GLYPH_ROWS = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Rahu', 'Ketu', 'Uranus', 'Neptune', 'Pluto'];

function H({ children }: { children: React.ReactNode }) {
  return <p className="mb-1 mt-3 font-display text-[10px] uppercase tracking-[0.16em] text-[#a8701a] first:mt-0">{children}</p>;
}

/** "ⓘ What do these symbols mean?" — always-available legend for any North Indian chart. */
export function KundliLegend({ compact = false }: { compact?: boolean }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-full border border-[#dcc08a] bg-[#fdf3dc] px-2.5 py-1 text-[11px] font-medium text-[#8a6a3a] shadow-sm hover:bg-[#f9e7c3] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#d9b46a]"
          aria-label="What do these chart symbols mean?"
        >
          <Info className="h-3.5 w-3.5" />
          {compact ? 'Symbols' : 'What do these symbols mean?'}
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="center"
        collisionPadding={8}
        className="warm-scroll max-h-[min(70vh,560px)] w-[min(92vw,400px)] overflow-y-auto border-[#e3cfa4] bg-[#fffdf6] p-3 text-[#5c4327]"
      >
        <p className="font-display text-sm font-semibold text-[#8a6a3a]">How to read this kundli</p>
        <p className="mt-1 text-[11px] leading-snug text-[#7c5a2e]">
          A snapshot of the sky from one place and moment. The 12 boxes are <b>houses</b> (areas of life), the
          small numbers are <b>zodiac signs</b>, and the symbols are <b>planets</b> (grahas). Tap any planet in the
          chart for its personal meaning.
        </p>

        <H>Planet symbols</H>
        <div className="space-y-1">
          {GLYPH_ROWS.map((n) => (
            <div key={n} className="flex items-start gap-2 text-[11px] leading-snug">
              <span className="w-5 flex-shrink-0 text-center text-base leading-none" style={{ color: PLANET_META[n].color }}>
                {PLANET_META[n].glyph}
              </span>
              <span>
                <b>{n}</b>
                {n === 'Rahu' && ' (north lunar node)'}
                {n === 'Ketu' && ' (south lunar node)'}
                {['Uranus', 'Neptune', 'Pluto'].includes(n) && ' (outer planet — shown only on Sky Today)'} —{' '}
                {PLANET_GUIDES[n].meaning} <span className="text-[#97795a]">Markets: {PLANET_GUIDES[n].market}</span>
              </span>
            </div>
          ))}
        </div>

        <H>Marks next to a planet</H>
        <ul className="space-y-1 text-[11px] leading-snug">
          <li><span className="font-mono">17°</span> — degree of the planet inside its sign (0–29°). Near 0° or 29° = the planet is about to change sign.</li>
          <li><span className="font-bold text-[#cf5b54]">℞</span> — <b>retrograde</b>: the planet looks like it moves backwards. Its themes get reviewed/delayed — re-check, don’t rush.</li>
          <li><span className="font-bold text-[#e07b2a]">c</span> — <b>combust</b>: too close to the Sun, so its signal is “burnt out”; it acts weaker than it looks.</li>
          <li><b>Coloured dot</b> under a planet = its strength (dignity):</li>
          {DIGNITY_COLOURS.map((d) => (
            <li key={d.key} className="ml-3 flex items-start gap-1.5">
              <span className="mt-1 inline-block h-2 w-2 flex-shrink-0 rounded-full" style={{ background: d.colour }} />
              <span><b>{d.label}</b> — {d.plain}</span>
            </li>
          ))}
          <li><b>Rahu ☊ / Ketu ☋</b> are always retrograde in Vedic astrology, so ℞ is not shown for them.</li>
        </ul>

        <H>The numbers 1–12 in the boxes</H>
        <p className="text-[11px] leading-snug">
          Each box shows the <b>zodiac sign</b> sitting in that house, as a number: {SIGNS.map((s, i) => `${i + 1} ${SIGN_GLYPHS[i]} ${s}`).join(' · ')}.
          The houses never move — the signs rotate depending on your rising sign.
        </p>

        <H>Houses — where each box is and what it means</H>
        <p className="mb-1 text-[11px] leading-snug">
          The <b>top-centre diamond is house 1</b> (the <b>Lagna / Asc</b>, your rising sign, marked “Asc” and shaded gold).
          Houses then run <b>anticlockwise</b>: 2 is the top-left triangle, 4 the left diamond, 7 the bottom diamond, 10 the right diamond.
        </p>
        <div className="grid grid-cols-1 gap-0.5 text-[11px] leading-snug">
          {Array.from({ length: 12 }, (_, i) => i + 1).map((h) => (
            <div key={h} className={[2, 5, 8, 9, 11].includes(h) ? 'rounded bg-[#fdf3dc] px-1' : 'px-1'}>
              <b>House {h}</b> — {HOUSE_GUIDES[h]}. <span className="text-[#97795a]">Money: {HOUSE_MONEY[h]}.</span>
            </div>
          ))}
        </div>
        <p className="mt-1 text-[10px] text-[#b39a76]">Highlighted = classic wealth houses (2, 5, 8, 9, 11).</p>

        <H>Reading it in one line</H>
        <p className="text-[11px] leading-snug">
          “Jupiter ♃ with a green dot in house 11” = a strong planet of growth sitting in the house of gains —
          a supportive sign for steady profits. A red dot or <span className="text-[#e07b2a]">c</span> in a money house says: go slower there.
        </p>
        <p className="mt-2 text-[9px] uppercase tracking-widest text-[#b39a76]">Educational — not financial advice</p>
      </PopoverContent>
    </Popover>
  );
}
